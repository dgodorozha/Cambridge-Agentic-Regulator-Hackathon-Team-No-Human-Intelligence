"""Evaluation harness: decision accuracy, aggregate fidelity, false alerts,
intervention outcomes, uncertainty and the decision gap metric.

Version 2 changes
  * Two declared fidelity constructs. `vol` is the conventional criterion
    (correlation of the stress index with realised rolling volatility) and
    is, by construction, exactly what the volatility trigger computes. The
    `moments` construct averages correlation with three realised moments so
    that no candidate is scored against its own output. Both are reported;
    the gap is computed under each.
  * Bootstrap confidence intervals over scenarios for every headline mean,
    and a bootstrap distribution for the decision gap (P(inversion)).
  * Interventions consume the sentinel's online flag matrix, so a rule can
    only act on flags the sentinel had issued by that step (no lookahead).
  * Containment is measured on post shock drawdown, and a crash probability
    (share of herd scenarios whose post shock drawdown exceeds
    DISLOCATION_DD) is reported before and after treatment.
  * Intervention burden is disaggregated by participant class and by ground
    truth, so the cost of a rule to stabilising agents is visible.
  * A kill switch rule (disconnect flagged agents) joins the two rules.
  * Held out families are scored separately from the calibration battery.
"""

import numpy as np
from scipy.stats import kendalltau

from .simulator import simulate, class_label
from .sentinels import _rolling_vol

DISLOCATION_DD = 0.10     # post shock drawdown above this is a dislocation
FALSE_ALERT_BUDGET = 0.25 # a sentinel above this quiet market alert rate is not certifiable
BURDEN_WINDOW = 150       # steps after the shock over which burden is measured

FIDELITY_CONSTRUCTS = {
    "vol": "correlation of the stress index with realised rolling volatility "
           "(the conventional validation criterion; identical to the "
           "volatility trigger's own output, so that tool scores 1.00 by "
           "construction)",
    "moments": "mean correlation of the stress index with three realised "
               "moments: rolling volatility, rolling absolute return and "
               "rolling mean pairwise flow correlation (no candidate is "
               "scored against its own output)",
}


# ---------- intervention rules ----------

class StaticCircuitBreaker:
    """Halts the whole market for `halt_len` steps when the rolling return
    over `window` exceeds `limit` in magnitude. Not sentinel informed."""
    name = "static_circuit_breaker"
    label = "Market wide circuit breaker"
    targeted = False

    def __init__(self, limit=0.035, window=15, halt_len=20):
        self.limit, self.window, self.halt_len = limit, window, halt_len
        self._halt_until = -1

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._halt_until = -1

        def rule(t, state):
            r = state["returns"]
            if t < self._halt_until:
                return {"halt": True}
            if len(r) > self.window and abs(r[-self.window:].sum()) > self.limit:
                self._halt_until = t + self.halt_len
                return {"halt": True}
            return {}
        return rule


class DynamicThrottle:
    """Scales down the order sizes of sentinel flagged agents when a
    directional cascade is under way (|rolling 10 step return| above limit),
    holding the throttle for a dwell period. Sentinel informed and targeted:
    unflagged agents trade untouched, so price discovery continues.

    Flags come from `flags_online` (T, N): at step t only the agents the
    sentinel had flagged by step t are throttled. A static `sentinel_flags`
    vector is accepted for backward compatibility and marks the rule as
    using lookahead."""
    name = "dynamic_throttle"
    label = "Sentinel informed dynamic throttle"
    targeted = True

    def __init__(self, limit=0.028, window=10, dwell=80, factor=0.1):
        self.limit, self.window = limit, window
        self.dwell, self.factor = dwell, factor
        self._on_until = -1
        self.lookahead = False

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._on_until = -1
        self.lookahead = flags_online is None
        static = sentinel_flags if sentinel_flags is not None \
            else np.zeros(n_agents, dtype=bool)

        def rule(t, state):
            r = state["returns"]
            if len(r) < self.window:
                return {}
            if abs(r[-self.window:].sum()) > self.limit:
                self._on_until = max(self._on_until, t + self.dwell)
            if t < self._on_until:
                flags = flags_online[t] if flags_online is not None else static
                scale = np.ones(n_agents)
                scale[flags] = self.factor
                return {"throttle": scale}
            return {}
        return rule


class KillSwitch(DynamicThrottle):
    """Disconnects sentinel flagged agents entirely for a longer dwell once a
    cascade is under way: the dynamic kill switch protocol of the problem
    statement, expressed as a throttle with factor zero."""
    name = "kill_switch"
    label = "Sentinel informed kill switch"

    def __init__(self, limit=0.028, window=10, dwell=120, factor=0.0):
        super().__init__(limit=limit, window=window, dwell=dwell, factor=factor)


from .rules import LIBRARY_RULES  # noqa: E402
from .rl_supervisor import LearnedPolicyRule  # noqa: E402

CORE_RULES = [StaticCircuitBreaker, DynamicThrottle, KillSwitch]
ALL_RULES = CORE_RULES + LIBRARY_RULES + [LearnedPolicyRule]
# ---------- per sentinel scoring ----------

def decision_scores(res, out):
    """Precision, recall, F1 on destabilising agents; lead time in steps
    before crash onset (positive = the alert preceded the shock)."""
    y, f = res.destabilising, out["flags"]
    tp = int((y & f).sum()); fp = int((~y & f).sum()); fn = int((y & ~f).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    lead = None
    if res.crash_onset is not None and out["first_alert"] is not None:
        lead = res.crash_onset - out["first_alert"]
    return {"precision": prec, "recall": rec, "f1": f1, "lead_time": lead,
            "tp": tp, "fp": fp, "fn": fn}


def _safe_corr(a, b):
    if a.std() < 1e-12 or b.std() < 1e-12:
        return 0.0
    c = np.corrcoef(a, b)[0, 1]
    return float(c) if np.isfinite(c) else 0.0


def _rolling_absret(returns, w=25):
    T = len(returns)
    out = np.zeros(T)
    a = np.abs(returns)
    for t in range(T):
        out[t] = a[max(0, t - w):t + 1].mean()
    return out


def _rolling_mean_corr(flows, w=80, stride=10):
    T, n = flows.shape
    out = np.zeros(T)
    last = 0.0
    for t in range(0, T, stride):
        seg = flows[max(0, t - w):t]
        if seg.shape[0] >= 30:
            C = np.nan_to_num(np.corrcoef(seg.T), nan=0.0)
            iu = np.triu_indices(n, k=1)
            last = float(np.mean(np.abs(C[iu])))
        out[t:t + stride] = last
    return out


def aggregate_fidelity(res, out, construct="vol"):
    """How closely the sentinel's stress index tracks realised aggregate
    conditions. See FIDELITY_CONSTRUCTS for the two declared definitions."""
    s = out["stress_index"]
    if s.std() < 1e-9:
        return 0.0
    # the realised series depend on the scenario alone; they are computed once
    # per result and reused across the eight sentinels and both constructs
    cache = getattr(res, "_fidelity_cache", None)
    if cache is None:
        cache = {}
        try:
            res._fidelity_cache = cache
        except (AttributeError, TypeError):
            pass
    if "vol" not in cache:
        cache["vol"] = _rolling_vol(res.returns)
    c_vol = _safe_corr(s, cache["vol"])
    if construct == "vol":
        return c_vol
    if "absret" not in cache:
        cache["absret"] = _rolling_absret(res.returns)
    if "mean_corr" not in cache:
        cache["mean_corr"] = _rolling_mean_corr(res.flows)
    c_abs = _safe_corr(s, cache["absret"])
    c_mc = _safe_corr(s, cache["mean_corr"])
    return float(np.mean([c_vol, c_abs, c_mc]))


def false_alert(res, out):
    """Did the sentinel raise an alert in a quiet scenario?"""
    return out["first_alert"] is not None


def score_row(spec, res, sentinel_name, out, window_ref=300):
    """One evaluation row: everything the case file, the autonomy gate and
    the critic need about one sentinel on one scenario."""
    win = max(1, spec.shock_time if spec.shock_time is not None else window_ref)
    rec = {"scenario": spec.name, "family": spec.family or spec.name.rsplit("_", 1)[0],
           "sentinel": sentinel_name, "quiet": spec.quiet,
           "holdout": bool(spec.holdout),
           "fidelity": aggregate_fidelity(res, out, "vol"),
           "fidelity_moments": aggregate_fidelity(res, out, "moments"),
           "peak_stress": float(np.max(out["stress_index"][:win])),
           "base_rate": float(np.mean(res.destabilising)),
           "first_alert": out["first_alert"],
           "n_flagged": int(out["flags"].sum()),
           "pre_shock_vol": res.pre_shock_vol()}
    if spec.quiet:
        rec["false_alert"] = false_alert(res, out)
        rec.update({"precision": None, "recall": None, "f1": None,
                    "lead_time": None, "post_shock_dd": None})
    else:
        rec.update(decision_scores(res, out))
        rec["false_alert"] = None
        rec["post_shock_dd"] = res.post_shock_drawdown()
    return rec


# ---------- uncertainty ----------

def bootstrap_ci(values, B=400, seed=0, stat=np.mean):
    """Percentile bootstrap interval for a statistic over scenario level
    values. Degenerate inputs return the point estimate on both sides."""
    v = np.asarray([x for x in values if x is not None], dtype=float)
    if len(v) == 0:
        return [None, None]
    if len(v) == 1:
        return [float(v[0]), float(v[0])]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(B, len(v)))
    boots = stat(v[idx], axis=1)
    return [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


def evidence_grade(n, ci):
    """A: n >= 12 and CI half width < 0.10; B: n >= 6 and half width < 0.20;
    C: otherwise. Grades qualify every headline number in the briefing."""
    if not ci or ci[0] is None:
        return "C"
    hw = (ci[1] - ci[0]) / 2
    if n >= 12 and hw < 0.10:
        return "A"
    if n >= 6 and hw < 0.20:
        return "B"
    return "C"


def _summ_one(r, B=400, seed=0):
    herd = [x for x in r if not x["quiet"]]
    quiet = [x for x in r if x["quiet"]]
    leads = [x["lead_time"] for x in herd if x.get("lead_time") is not None]
    f1s = [x["f1"] for x in herd]
    fids = [x["fidelity"] for x in r]
    fidm = [x["fidelity_moments"] for x in r]
    fas = [float(x["false_alert"]) for x in quiet]
    out = {
        "decision_f1": float(np.mean(f1s)) if herd else 0.0,
        "precision": float(np.mean([x["precision"] for x in herd])) if herd else 0.0,
        "recall": float(np.mean([x["recall"] for x in herd])) if herd else 0.0,
        "aggregate_fidelity": float(np.mean(fids)) if r else 0.0,
        "fidelity_moments": float(np.mean(fidm)) if r else 0.0,
        "mean_lead_time": float(np.mean(leads)) if leads else None,
        "share_alerting": float(np.mean([x["first_alert"] is not None for x in herd])) if herd else 0.0,
        "false_alert_rate": float(np.mean(fas)) if quiet else None,
        "n_herd": len(herd), "n_quiet": len(quiet),
        "ci": {"decision_f1": bootstrap_ci(f1s, B, seed),
               "aggregate_fidelity": bootstrap_ci(fids, B, seed + 1),
               "fidelity_moments": bootstrap_ci(fidm, B, seed + 2),
               "false_alert_rate": bootstrap_ci(fas, B, seed + 3) if quiet else [None, None],
               "mean_lead_time": bootstrap_ci(leads, B, seed + 4) if leads else [None, None]},
    }
    fa = out["false_alert_rate"]
    out["false_alert_budget"] = FALSE_ALERT_BUDGET
    out["within_budget"] = bool(fa is None or fa <= FALSE_ALERT_BUDGET)
    out["grade"] = {"decision_f1": evidence_grade(len(herd), out["ci"]["decision_f1"]),
                    "aggregate_fidelity": evidence_grade(len(r), out["ci"]["aggregate_fidelity"]),
                    "false_alert_rate": evidence_grade(len(quiet), out["ci"]["false_alert_rate"]) if quiet else "C"}
    by_family = {}
    for fam in sorted({x["family"] for x in herd}):
        fr = [x for x in herd if x["family"] == fam]
        by_family[fam] = {"decision_f1": float(np.mean([x["f1"] for x in fr])),
                          "recall": float(np.mean([x["recall"] for x in fr])),
                          "n": len(fr)}
    out["by_family"] = by_family
    return out


def summarise(rows, sentinel_names, B=400, seed=0):
    """Per sentinel means with bootstrap intervals, calibration battery and
    held out families reported separately."""
    summary, holdout = {}, {}
    for name in sentinel_names:
        r = [x for x in rows if x["sentinel"] == name and not x["holdout"]]
        h = [x for x in rows if x["sentinel"] == name and x["holdout"]]
        if r:
            summary[name] = _summ_one(r, B, seed)
        if h:
            holdout[name] = _summ_one(h, B, seed)
    return summary, holdout


def _rank_gap(fid, dec):
    rank_f = np.argsort(np.argsort(fid))
    rank_d = np.argsort(np.argsort(dec))
    tau, _ = kendalltau(rank_f, rank_d)
    tau = float(tau) if tau == tau else 0.0
    return tau, (1 - tau) / 2


def best_certifiable(summary):
    """Highest decision F1 among tools within the false alert budget, or
    None if no tool is within budget."""
    ok = [(v["decision_f1"], n) for n, v in summary.items() if v.get("within_budget")]
    return max(ok)[1] if ok else None


def decision_gap(summary, fidelity_key="aggregate_fidelity"):
    """Rank divergence between aggregate fidelity and decision accuracy over
    the same tools. 0 = identical rankings, 1 = full inversion (Kendall tau
    distance normalised). With k tools tau can take only a small number of
    values, which is why the bootstrap below accompanies it."""
    names = list(summary)
    fid = [summary[n][fidelity_key] for n in names]
    dec = [summary[n]["decision_f1"] for n in names]
    tau, gap = _rank_gap(fid, dec)
    return {"kendall_tau": tau, "decision_gap": gap, "n_tools": len(names),
            "fidelity_construct": fidelity_key,
            "fidelity_ranking": [names[i] for i in np.argsort(fid)[::-1]],
            "decision_ranking": [names[i] for i in np.argsort(dec)[::-1]]}


def gap_bootstrap(rows, sentinel_names, fidelity_key="fidelity", B=400, seed=0):
    """Resample scenarios with replacement, recompute per sentinel means and
    the gap each time. Reports P(rankings invert), P(full inversion) and a
    percentile interval on the gap."""
    rows = [x for x in rows if not x["holdout"]]
    scen = sorted({x["scenario"] for x in rows})
    by = {s: [x for x in rows if x["scenario"] == s] for s in scen}
    rng = np.random.default_rng(seed)
    taus, gaps = [], []
    top_counts = {n: 0 for n in sentinel_names}          # winner stability: P(tool is top by decision)
    pick_counts = {n: 0 for n in sentinel_names}         # P(tool is the within budget pick)
    n_pick = 0
    for _ in range(B):
        pick = rng.choice(scen, size=len(scen), replace=True)
        sample = [x for s in pick for x in by[s]]
        fid, dec, fa = [], [], []
        for n in sentinel_names:
            r = [x for x in sample if x["sentinel"] == n]
            herd = [x for x in r if not x["quiet"]]
            quiet = [x for x in r if x["quiet"]]
            fid.append(np.mean([x[fidelity_key] for x in r]) if r else 0.0)
            dec.append(np.mean([x["f1"] for x in herd]) if herd else 0.0)
            fa.append(np.mean([float(x["false_alert"]) for x in quiet]) if quiet else 0.0)
        tau, gap = _rank_gap(fid, dec)
        taus.append(tau); gaps.append(gap)
        top_counts[sentinel_names[int(np.argmax(dec))]] += 1
        ok = [i for i in range(len(sentinel_names)) if fa[i] <= FALSE_ALERT_BUDGET + 1e-12]
        if ok:
            pick_counts[sentinel_names[max(ok, key=lambda i: dec[i])]] += 1
            n_pick += 1
    taus, gaps = np.array(taus), np.array(gaps)
    return {"p_inversion": float(np.mean(taus < 0)),
            "p_full_inversion": float(np.mean(taus <= -0.999)),
            "gap_ci": [float(np.percentile(gaps, 2.5)), float(np.percentile(gaps, 97.5))],
            "tau_mean": float(taus.mean()), "B": int(B),
            "n_scenarios": len(scen),
            "p_top_decision": {n: float(c / B) for n, c in top_counts.items()},
            "p_within_budget_pick": {n: (float(c / n_pick) if n_pick else None) for n, c in pick_counts.items()},
            "winner_stability": float(max(top_counts.values()) / B)}


# ---------- intervention outcomes ----------

def _burden(treated, res_cluster, destab, shock, T):
    """Share of intended order flow suppressed per class over the burden
    window after the shock (1 = fully halted)."""
    w = slice(shock, min(T, shock + BURDEN_WINDOW))
    scale = treated.throttled[w].copy()
    scale[treated.halted[w], :] = 0.0
    suppressed = 1.0 - scale
    out = {}
    for c in np.unique(res_cluster):
        m = res_cluster == c
        out[class_label(int(c))] = float(suppressed[:, m].mean())
    out["destabilising"] = float(suppressed[:, destab].mean()) if destab.any() else 0.0
    out["non_destabilising"] = float(suppressed[:, ~destab].mean()) if (~destab).any() else 0.0
    return out


def expected_shortfall(x, alpha=0.75):
    """Expected shortfall of a loss sample at level alpha: the mean of the
    worst (1 - alpha) share. Coherent, unlike value at risk (Artzner and
    others 1999; McNeil, Frey and Embrechts 2015, chapter 2)."""
    x = np.sort(np.asarray(x, dtype=float))
    if len(x) == 0:
        return None
    k = max(1, int(np.ceil((1 - alpha) * len(x))))
    return float(x[-k:].mean())


ES_LEVEL = 0.75


def evaluate_rules(specs, rule_classes, cache, flags_from="network_sentinel",
                   log=None, stop=None, B=400, seed=0):
    """Compare candidate intervention rules on post shock containment, crash
    probability, false halts and burden by class. Targeted rules receive the
    sentinel's online flag matrix from the untreated pass: no lookahead in
    time, although the flags are those observed on the untreated path."""
    from .survival import time_to_dislocation
    out = {}
    event_times = {}
    main = [s for s in specs if not s.holdout]
    for R in rule_classes:
        base_post, rule_post, base_whole, rule_whole = [], [], [], []
        base_trough, rule_trough, pre_engaged = [], [], []
        fam_base, fam_rule = {}, {}
        per_scenario = []
        halts_quiet, burdens, lookahead = [], [], False
        event_times[R.name] = {}
        for spec in main:
            base = cache[spec.name]["res"]
            fo = cache[spec.name]["outs"][flags_from]["flags_online"]
            rule_obj = R()
            rule = rule_obj.make(spec.n_agents, flags_online=fo)
            lookahead = lookahead or getattr(rule_obj, "lookahead", False)
            treated = simulate(spec, intervention=rule, stop=stop)
            rec = {"rule": R.name, "scenario": spec.name}
            if spec.quiet:
                fh = bool(treated.halted.any() or (treated.throttled[1:] < 1).any())
                halts_quiet.append(fh)
                rec["false_halt"] = fh
            else:
                bp, rp = base.post_shock_drawdown(), treated.post_shock_drawdown()
                base_post.append(bp); rule_post.append(rp)
                base_whole.append(base.max_drawdown()); rule_whole.append(treated.max_drawdown())
                base_trough.append(base.shock_trough()); rule_trough.append(treated.shock_trough())
                st = spec.shock_time
                pre_engaged.append(bool(treated.halted[1:st].any()
                                        or (treated.throttled[1:st] < 1).any()))
                burdens.append(_burden(treated, base.agent_cluster, base.destabilising,
                                       spec.shock_time, spec.t_steps))
                rec.update({"base_post_dd": bp, "rule_post_dd": rp,
                            "base_dd": base_whole[-1], "rule_dd": rule_whole[-1]})
                fam_base.setdefault(spec.family, []).append(bp)
                fam_rule.setdefault(spec.family, []).append(rp)
                per_scenario.append({"scenario": spec.name, "quiet": False, "base_post_dd": bp,
                                     "rule_post_dd": rp,
                                     "t_cross_base": base.first_crossing(DISLOCATION_DD),
                                     "t_cross_rule": treated.first_crossing(DISLOCATION_DD),
                                     "horizon": int(spec.t_steps - max(0, (spec.shock_time or 1) - 1))})
                event_times[R.name][spec.name] = time_to_dislocation(treated)
            if log is not None:
                log("rule_run", **rec)
        bp, rp = np.array(base_post), np.array(rule_post)
        cont = float(1 - rp.mean() / max(1e-9, bp.mean())) if len(bp) else 0.0
        rng = np.random.default_rng(seed)
        boots = []
        if len(bp) > 1:
            for _ in range(B):
                idx = rng.integers(0, len(bp), size=len(bp))
                boots.append(1 - rp[idx].mean() / max(1e-9, bp[idx].mean()))
        burden_mean = {}
        for k in sorted({k for b in burdens for k in b}):
            vals = [b[k] for b in burdens if k in b]
            burden_mean[k] = float(np.mean(vals))
        out[R.name] = {
            "label": R.label, "targeted": R.targeted,
            "mean_post_shock_dd_untreated": float(bp.mean()) if len(bp) else None,
            "mean_post_shock_dd_treated": float(rp.mean()) if len(rp) else None,
            "containment": cont,
            "containment_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
            if boots else [cont, cont],
            "mean_drawdown_untreated": float(np.mean(base_whole)) if base_whole else None,
            "mean_drawdown_treated": float(np.mean(rule_whole)) if rule_whole else None,
            "containment_whole_path": float(1 - np.mean(rule_whole) / max(1e-9, np.mean(base_whole)))
            if base_whole else None,
            "mean_trough_untreated": float(np.mean(base_trough)) if base_trough else None,
            "mean_trough_treated": float(np.mean(rule_trough)) if rule_trough else None,
            "containment_trough": float(1 - np.mean(rule_trough) / max(1e-9, np.mean(base_trough)))
            if base_trough else None,
            "pre_shock_engagement": float(np.mean(pre_engaged)) if pre_engaged else None,
            "crash_prob_untreated": float(np.mean(bp > DISLOCATION_DD)) if len(bp) else None,
            "crash_prob_treated": float(np.mean(rp > DISLOCATION_DD)) if len(rp) else None,
            "es_post_shock_dd_untreated": expected_shortfall(bp, ES_LEVEL) if len(bp) else None,
            "es_post_shock_dd_treated": expected_shortfall(rp, ES_LEVEL) if len(rp) else None,
            "es_level": ES_LEVEL,
            "tail_containment": (None if not len(bp) or expected_shortfall(bp, ES_LEVEL) in (None, 0)
                                 else float(1.0 - expected_shortfall(rp, ES_LEVEL) / expected_shortfall(bp, ES_LEVEL))),
            "false_halt_rate": float(np.mean(halts_quiet)) if halts_quiet else None,
            "burden_by_class": burden_mean,
            "per_scenario": per_scenario,
            "containment_by_family": {f: float(1 - np.mean(fam_rule[f]) / max(1e-9, np.mean(fam_base[f])))
                                      for f in fam_base},
            "n_herd": int(len(bp)), "n_quiet": len(halts_quiet),
            "flags_from": flags_from if R.targeted else None,
            "lookahead": bool(lookahead),
            "dislocation_threshold": DISLOCATION_DD,
            "burden_window": BURDEN_WINDOW,
        }
        r = out[R.name]
        r["crash_prob_reduction"] = (r["crash_prob_untreated"] - r["crash_prob_treated"]) \
            if r["crash_prob_untreated"] is not None else None
        r["grade"] = evidence_grade(len(bp), r["containment_ci"])
    out["_event_times"] = event_times
    return out
