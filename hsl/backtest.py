"""Backtesting suite.

Three backtests, each honest about what a real tape can and cannot say.

Episodes. Stress episodes are found in the observed data: rolling windows
whose drawdown exceeds a threshold, with the event step at the largest
drop; or, when the dataset carries an event column, the marked stretches.
Where a label column marks known destabilising participants (an
enforcement finding, a post event report), those labels are attached to
the episode.

Sentinel backtest. Every sentinel runs over each episode window with the
observed flows (or, for a price only tape, over the return path alone,
which timing based sentinels can read). It reports whether the sentinel
alerted, how many steps before or after the event, and its peak stress,
and over the stretches outside episodes the alert workload per 100 steps.
Where participant labels exist, recall on the labelled positives is
reported; precision is not, because the tape does not say who the
negatives were. This is a timing and workload backtest, not an accuracy
certification.

Rule backtest. Each episode becomes a hybrid market: the observed return
path is the news, synthetic agents with the calibrated structure respond,
and every rule is applied. Containment and dislocation probability per
episode say what each rule would have done against that real shock with a
known population.

Walk forward. The certification procedure itself is backtested: over time
ordered folds of the episodes (or seed ordered folds of the synthetic
battery when no episodes exist) the tool certified on the earlier folds is
scored on the next one, and its regret against the best tool on that fold
is reported with how often the certified tool was still the best. A
procedure with low walk forward regret is one whose answers repeat.
"""

import numpy as np

from .calibrate import register_observed
from .ingest import price_series, _log_returns, flow_matrix_with_meta
from .simulator import ScenarioSpec, simulate
from .evaluate import FALSE_ALERT_BUDGET

MAX_EPISODES = 5
CONTEXT = 120           # steps of context before an episode window
EP_WINDOW = 80


def find_episodes(ds, threshold=0.05, window=EP_WINDOW, max_episodes=MAX_EPISODES):
    """Stress episodes in the dataset: marked by an event column when
    present, else windows whose drawdown exceeds the threshold."""
    prices = price_series(ds)
    p = np.asarray(prices, dtype=float)
    if len(p) < window + CONTEXT:
        return []
    s = ds["schema"]
    episodes = []
    if s.get("event"):
        marks, seen = [], set()
        for r in ds["rows"]:
            t = r.get(s["time"])
            if t in seen:
                continue
            seen.add(t)
            v = str(r.get(s["event"]) or "").strip().lower()
            marks.append(v in ("1", "true", "yes", "y", "event", "stress"))
        marks = np.array(marks[:len(p)], dtype=bool)
        start = None
        for i, m in enumerate(marks):
            if m and start is None:
                start = i
            if (not m or i == len(marks) - 1) and start is not None:
                end = i if not m else i + 1
                seg = p[start:end]
                if len(seg) >= 5:
                    lr = np.diff(np.log(np.maximum(seg, 1e-9)))
                    ev = start + 1 + int(np.argmin(lr)) if len(lr) else start
                    peak = np.maximum.accumulate(seg)
                    episodes.append({"name": f"marked_{len(episodes)}", "start": int(start), "end": int(end),
                                     "event_step": int(ev), "drawdown": float(np.max((peak - seg) / peak)),
                                     "source": "event column"})
                start = None
    else:
        lr = np.diff(np.log(np.maximum(p, 1e-9)))
        cands = []
        for a in range(CONTEXT, len(p) - window, max(1, window // 4)):
            seg = p[a:a + window]
            peak = np.maximum.accumulate(seg)
            dd = float(np.max((peak - seg) / peak))
            if dd >= threshold:
                cands.append((dd, a))
        cands.sort(reverse=True)
        taken = []
        for dd, a in cands:
            if any(abs(a - b) < window for b in taken):
                continue
            taken.append(a)
            ev = a + 1 + int(np.argmin(lr[a:a + window - 1]))
            episodes.append({"name": f"episode_{len(episodes)}", "start": int(a), "end": int(a + window),
                             "event_step": int(ev), "drawdown": float(dd), "source": f"drawdown above {threshold}"})
            if len(episodes) >= max_episodes:
                break
    episodes.sort(key=lambda e: e["start"])
    labels = participant_labels(ds)
    for e in episodes:
        e["labelled_positives"] = int(sum(labels.values())) if labels else 0
    return episodes


def participant_labels(ds):
    """Known destabilising participants from a label column, keyed by the
    participant's column position (identifiers are never emitted)."""
    s = ds["schema"]
    if not (s.get("participant") and s.get("label")):
        return {}
    order, lab = {}, {}
    for r in ds["rows"]:
        pid = r.get(s["participant"])
        if pid not in order:
            order[pid] = len(order)
        v = str(r.get(s["label"]) or "").strip().lower()
        if v in ("1", "true", "yes", "y"):
            lab[order[pid]] = True
    return {i: lab.get(i, False) for i in order.values()}


class _Obs:
    def __init__(self, flows, returns):
        self.flows = flows
        self.returns = returns
        self.prices = np.cumsum(returns)
        self.agent_cluster = np.full(flows.shape[1], -1)
        self.destabilising = np.zeros(flows.shape[1], dtype=bool)
        self.spec = None


def _observed_result(ds):
    """Flows, returns and the time index of the dataset. Price only tapes get
    a single market column so timing based sentinels can run."""
    F, price, times = flow_matrix_with_meta(ds)
    prices = price_series(ds)
    r = _log_returns(prices)
    if F is None:
        R = np.concatenate([[0.0], r])
        return _Obs(R[:, None], R), False
    T = min(F.shape[0], len(r) + 1)
    R = np.concatenate([[0.0], r])[:T]
    return _Obs(F[:T], R), True


def backtest_sentinels(ds, episodes, sentinel_classes):
    """Timing, workload and (with labels) recall of every sentinel on the
    observed episodes."""
    obs, has_flows = _observed_result(ds)
    labels = participant_labels(ds)
    T = obs.flows.shape[0]
    quiet_mask = np.ones(T, dtype=bool)
    for e in episodes:
        quiet_mask[max(0, e["start"] - 20):e["end"]] = False
    out = {"has_flows": bool(has_flows), "n_steps": int(T), "n_episodes": len(episodes),
           "labelled_positives": int(sum(labels.values())) if labels else 0, "sentinels": {}}
    for S in sentinel_classes:
        if not has_flows and S.name not in ("naive_threshold", "endogeneity"):
            out["sentinels"][S.name] = {"skipped": "needs participant flows"}
            continue
        try:
            res = S().run(obs)
        except Exception as e:  # noqa: BLE001 - a sentinel that cannot read the tape is reported, not fatal
            out["sentinels"][S.name] = {"skipped": f"could not run: {str(e)[:80]}"}
            continue
        stress = res["stress_index"]
        fo = res.get("flags_online")
        rows = []
        for ep in episodes:
            a, b, ev = max(0, ep["start"] - 20), ep["end"], ep["event_step"]
            seg = stress[a:b]
            hits = np.where(seg > 1.0)[0]
            first = int(a + hits[0]) if len(hits) else None
            rec = {"episode": ep["name"], "alerted": first is not None,
                   "lead_steps": (int(ev - first) if first is not None else None),
                   "peak_stress": float(seg.max()) if len(seg) else 0.0}
            if labels and fo is not None and first is not None:
                flags = fo[min(b - 1, T - 1)]
                pos = [i for i, v in labels.items() if v and i < len(flags)]
                rec["recall_on_labelled"] = float(np.mean([flags[i] for i in pos])) if pos else None
                rec["flags_on_unlabelled_share"] = float(np.mean([flags[i] for i in range(len(flags)) if not labels.get(i)])) \
                    if len(flags) else None
            rows.append(rec)
        q = stress[quiet_mask]
        alerts = int(np.sum((q[1:] > 1.0) & (q[:-1] <= 1.0))) if len(q) > 1 else 0
        out["sentinels"][S.name] = {
            "episodes": rows,
            "detection_rate": float(np.mean([r["alerted"] for r in rows])) if rows else None,
            "median_lead": (float(np.median([r["lead_steps"] for r in rows if r["lead_steps"] is not None]))
                            if any(r["lead_steps"] is not None for r in rows) else None),
            "quiet_alerts_per_100_steps": float(100.0 * alerts / max(1, int(quiet_mask.sum()))),
            "mean_recall_on_labelled": (float(np.mean([r["recall_on_labelled"] for r in rows
                                                      if r.get("recall_on_labelled") is not None]))
                                        if any(r.get("recall_on_labelled") is not None for r in rows) else None)}
    return out


def backtest_rules(ds, cal, episodes, rule_classes, stop=None):
    """Each episode as a hybrid market: observed news, calibrated synthetic
    population, every rule applied."""
    if not cal or not episodes:
        return None
    prices = price_series(ds)
    r = _log_returns(prices)
    p = cal["params"]
    out = {"episodes": [], "rules": {}}
    per_rule = {R.name: [] for R in rule_classes}
    for ep in episodes[:MAX_EPISODES]:
        a = max(0, ep["start"] - CONTEXT)
        seg = r[a:ep["end"]]
        if len(seg) < 100:
            continue
        sha = f"{ds.get('sha256', '')[:12]}_{ep['name']}"
        register_observed(sha, seg)
        t_shock = int(min(max(50, ep["event_step"] - a), len(seg) - 30))
        spec = ScenarioSpec(name=f"backtest_{ep['name']}", family="backtest", generator="hybrid", hybrid_sha=sha,
                            t_steps=int(len(seg)), shock_time=t_shock, shock_size=0.0,
                            vendor_shares=tuple(p["vendor_shares"]), vendor_rhos=tuple(p["vendor_rhos"]),
                            frac_fundamental=p["frac_fundamental"], kappa=p["kappa"], sigma=p["sigma"],
                            momentum_window=p["momentum_window"], seed=1500)
        base = simulate(spec, stop=stop)
        dd0 = base.post_shock_drawdown()
        rec = {"episode": ep["name"], "observed_drawdown": ep["drawdown"], "untreated_drawdown": float(dd0), "rules": {}}
        for R in rule_classes:
            treated = simulate(spec, intervention=R().make(spec.n_agents), stop=stop)
            dd1 = treated.post_shock_drawdown()
            cont = float(1.0 - dd1 / max(dd0, 1e-9))
            rec["rules"][R.name] = {"treated_drawdown": float(dd1), "containment": cont,
                                    "halted_steps": int(treated.halted.sum())}
            per_rule[R.name].append(cont)
        out["episodes"].append(rec)
    for name, vals in per_rule.items():
        if vals:
            out["rules"][name] = {"mean_containment": float(np.mean(vals)), "worst_containment": float(np.min(vals)),
                                  "n_episodes": len(vals)}
    return out


def walk_forward(rows, sentinel_names, n_folds=4, budget=FALSE_ALERT_BUDGET):
    """Backtest of the certification procedure over time ordered folds of the
    calibration scenarios: certify on the earlier folds, score on the next."""
    calib = [x for x in rows if not x["holdout"]]
    scen = sorted({x["scenario"] for x in calib})
    if len(scen) < 2 * n_folds:
        n_folds = max(2, len(scen) // 2)
    folds = [scen[i::n_folds] for i in range(n_folds)]     # seed ordered interleaving keeps every family in each fold

    def score(names_in):
        sub = [x for x in calib if x["scenario"] in names_in]
        f1 = {n: float(np.mean([x["f1"] for x in sub if x["sentinel"] == n and not x["quiet"]] or [0.0]))
              for n in sentinel_names}
        fa = {n: float(np.mean([float(x["false_alert"]) for x in sub if x["sentinel"] == n and x["quiet"]] or [0.0]))
              for n in sentinel_names}
        return f1, fa
    results = []
    for k in range(1, n_folds):
        train = [s for f in folds[:k] for s in f]
        test = folds[k]
        f1_tr, fa_tr = score(train)
        ok = [n for n in sentinel_names if fa_tr[n] <= budget + 1e-12]
        certified = max(ok, key=lambda n: f1_tr[n]) if ok else max(f1_tr, key=f1_tr.get)
        f1_te, _ = score(test)
        best = max(f1_te, key=f1_te.get)
        results.append({"fold": k, "n_train": len(train), "n_test": len(test), "certified": certified,
                        "best_on_test": best, "f1_certified_test": f1_te[certified], "f1_best_test": f1_te[best],
                        "regret": float(f1_te[best] - f1_te[certified]), "still_best": bool(certified == best)})
    if not results:
        return None
    return {"folds": results, "mean_regret": float(np.mean([r["regret"] for r in results])),
            "max_regret": float(np.max([r["regret"] for r in results])),
            "p_still_best": float(np.mean([r["still_best"] for r in results])),
            "n_folds": n_folds, "note": "folds interleave the seed ordered scenarios so every family appears in each"}


def backtest_all(datasets, calibrations, rows, sentinel_classes, rule_classes, stop=None):
    names = [S.name for S in sentinel_classes]
    out = {"datasets": [], "walk_forward": walk_forward(rows, names)}
    for ds, cal in zip(datasets or [], calibrations or []):
        if not ds.get("ok"):
            continue
        eps = find_episodes(ds)
        entry = {"name": ds["name"], "sha256": ds["sha256"], "episodes": eps,
                 "sentinels": backtest_sentinels(ds, eps, sentinel_classes) if eps else None,
                 "rules": backtest_rules(ds, cal, eps, rule_classes, stop=stop) if (eps and cal) else None}
        out["datasets"].append(entry)
    out["n_datasets"] = len(out["datasets"])
    out["n_episodes"] = int(sum(len(d["episodes"]) for d in out["datasets"]))
    return out
