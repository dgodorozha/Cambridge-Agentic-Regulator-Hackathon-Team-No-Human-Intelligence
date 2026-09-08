"""One evaluation pipeline for both the command line and the terminal.

`run_battery` simulates every scenario, scores every sentinel, computes the
decision gap with its bootstrap, sets the autonomy gates, scores the
intervention rules, measures RL emergence, renders the three worlds
comparison and the live network frames, and assembles `artefacts`. The
terminal passes hooks to stream progress; the batch path passes none. The
numbers are identical either way because the hooks never touch dynamics.
"""

import time

import numpy as np

from . import provenance
from .attribution import attribute_battery
from .audit import truth_dependence, concentration_sweep
from .autonomy import autonomy_gates, autonomy_public
from .conformal import certify, certifiable
from .evaluate import (ALL_RULES, evaluate_rules, decision_gap, gap_bootstrap,
                       score_row, summarise, best_certifiable, FIDELITY_CONSTRUCTS,
                       DISLOCATION_DD, FALSE_ALERT_BUDGET)
from .frontier import sentinel_frontier, rule_frontier
from .games import game_from_trials
from .appraisal import appraise
from .risk import risk_report
from .rl_supervisor import train_and_evaluate
from .reports import coverage as needs_coverage, RULE_OVERSIGHT
from .question import interpret as interpret_question, direct_answer
from .backtest import backtest_all
from .sentinels import SENTINEL_LABELS
from .ingest import anchoring, observed_window, dataset_summary, stats as _obs_stats
from .personas import registry_snapshot
from .agents import registry_snapshot as agents_snapshot
from .redteam import adversarial_search, injection_suite
from .rules import RULE_LIBRARY
from .sentinels import ALL_SENTINELS, NetworkSentinel
from .simulator import ScenarioSpec, simulate, battery_hash, class_label, FAMILY_NOTES, CUSTOM_NOTES
from .survival import survival_analysis

# Version 3 assurance stages and their default budgets. Tests shrink them.
ASSURANCE = {"attribution_per_family": 1,
             "truth_families": ["herd_high", "herd_mid", "herd_low", "mixed", "evader"],
             "truth_per_family": 1, "truth_n_quiet": 4, "dose_seeds": (0, 1),
             "redteam_budget": 12}

NET_EDGE = 0.5
NET_MAX_LINKS = 900


def network_frames(res, flags, shock):
    """Three correlation network snapshots of one scenario for the NET
    panel: before the shock, as it lands and during the cascade. Nodes carry
    class, ground truth and the sentinel's final flag."""
    T, n = res.flows.shape
    if shock is None:
        wins = [("Window A", 100, 180), ("Window B", 300, 380), ("Window C", 500, 580)]
    else:
        wins = [("Before the shock", shock - 80, shock),
                ("Shock lands", shock, shock + 80),
                ("Cascade", shock + 80, min(T, shock + 160))]
    frames = []
    for title, a, b in wins:
        a, b = max(0, a), min(T, b)
        seg = res.flows[a:b]
        C = np.nan_to_num(np.corrcoef(seg.T), nan=0.0) if b - a > 5 else np.zeros((n, n))
        iu = np.triu_indices(n, k=1)
        w = np.abs(C[iu])
        order = np.argsort(w)[::-1]
        links = []
        for k in order[:NET_MAX_LINKS]:
            if w[k] <= NET_EDGE:
                break
            i, j = int(iu[0][k]), int(iu[1][k])
            links.append({"source": str(i), "target": str(j), "w": round(float(w[k]), 3)})
        deg = np.zeros(n)
        for l in links:
            deg[int(l["source"])] += 1; deg[int(l["target"])] += 1
        # per agent insight for the inspector: mean |corr| with every other
        # agent in the window, correlation of its flow with the market
        # return, and its share of gross order flow
        absC = np.abs(C)
        np.fill_diagonal(absC, np.nan)
        mcorr = np.nanmean(absC, axis=1) if n > 1 else np.zeros(n)
        rseg = res.returns[a:b]
        if b - a > 5 and rseg.std() > 0:
            with np.errstate(invalid="ignore", divide="ignore"):
                mkt = np.array([np.corrcoef(seg[:, i], rseg)[0, 1] for i in range(n)])
            mkt = np.nan_to_num(mkt)
        else:
            mkt = np.zeros(n)
        gross = np.abs(seg).sum(axis=0) if b - a > 0 else np.zeros(n)
        share = gross / max(gross.sum(), 1e-12)
        nodes = [{"id": str(i), "category": class_label(int(res.agent_cluster[i])),
                  "destab": bool(res.destabilising[i]), "flagged": bool(flags[i]),
                  "symbolSize": float(5 + 1.2 * np.sqrt(deg[i])),
                  "degree": int(deg[i]), "mcorr": round(float(mcorr[i]), 3),
                  "mkt": round(float(mkt[i]), 3), "flow_share": round(float(share[i]), 4)}
                 for i in range(n)]
        frames.append({"title": title, "window": [a, b], "nodes": nodes, "links": links,
                       "mean_abs_corr": round(float(w.mean()), 3) if len(w) else 0.0})
    return frames


def _tape_marks(spec, res, outs):
    marks = []
    if spec.shock_time is not None:
        marks.append({"step": spec.shock_time, "kind": "shock", "text": "shock"})
    for name, out in outs.items():
        if out["first_alert"] is not None:
            marks.append({"step": int(out["first_alert"]), "kind": "alert",
                          "sentinel": name, "text": name.split("_")[0]})
    return marks


def run_battery(specs, log, *, sentinel_classes=ALL_SENTINELS, rule_classes=ALL_RULES,
                flags_from=NetworkSentinel, tick_hook=None, progress=None, stop=None,
                question="", bootstrap_B=400, net_scenario="herd_high_0", assurance=None,
                datasets=None):
    """Run the whole evaluation. `tick_hook(spec)` returns an intervention
    style callable that streams prices (or None). `progress(event, **kw)` is
    called at each stage. `assurance` overrides the budgets of the version 3
    stages (None keeps the defaults; {"skip": True} skips them). Returns
    (artefacts, extras)."""
    asr = dict(ASSURANCE, **(assurance or {}))
    t0 = time.time()
    names = [S.name for S in sentinel_classes]
    rows, cache, tapes, net = [], {}, {}, None
    n = len(specs)
    for i, spec in enumerate(specs):
        if progress:
            progress("scenario_start", i=i, n=n, spec=spec)
        res = simulate(spec, intervention=tick_hook(spec) if tick_hook else None, stop=stop)
        outs = {}
        for S in sentinel_classes:
            outs[S.name] = S().run(res)
        for S in sentinel_classes:
            rec = score_row(spec, res, S.name, outs[S.name])
            rows.append(rec)
            log("sentinel_run", **rec)
        cache[spec.name] = {"res": res, "outs": outs}
        tapes[spec.name] = {"prices": np.exp(res.prices).round(5).tolist(),
                            "marks": _tape_marks(spec, res, outs),
                            "family": spec.family, "quiet": spec.quiet,
                            "holdout": spec.holdout, "shock": spec.shock_time,
                            "post_shock_dd": res.post_shock_drawdown(),
                            "pre_shock_vol": res.pre_shock_vol()}
        if spec.name == net_scenario or (net is None and not spec.quiet and i == n - 1):
            net = network_frames(res, outs[flags_from.name]["flags"], spec.shock_time)
        if progress:
            progress("scenario_done", i=i, n=n, spec=spec, res=res, outs=outs,
                     rows=[r for r in rows if r["scenario"] == spec.name],
                     summary=summarise(rows, names, B=50)[0], tape=tapes[spec.name],
                     net=net if spec.name == net_scenario else None)

    summary, holdout = summarise(rows, names, B=bootstrap_B)
    gap = decision_gap(summary, "aggregate_fidelity")
    gap_m = decision_gap(summary, "fidelity_moments")
    gb = gap_bootstrap(rows, names, "fidelity", B=bootstrap_B)
    gb_m = gap_bootstrap(rows, names, "fidelity_moments", B=bootstrap_B, seed=1)
    log("decision_gap_computed", **gap, bootstrap=gb)
    log("decision_gap_computed", **gap_m, bootstrap=gb_m)
    gap_holdout = decision_gap(holdout, "aggregate_fidelity") if holdout else None

    aut = autonomy_gates(rows, names)
    for k, v in autonomy_public(aut).items():
        log("autonomy_gate", sentinel=k, **{kk: vv for kk, vv in v.items()})
    if progress:
        progress("gap", gap=gap, gap_moments=gap_m, gap_bootstrap=gb,
                 gap_bootstrap_moments=gb_m, aut=aut, summary=summary,
                 holdout=holdout, rows=rows)

    # version 3.2: learn the market wide policy on a calibration subset and
    # off policy evaluate every rule from the logged behaviour data before
    # the rules are scored, so the learned policy is scored like the rest
    learned = None
    if asr.get("skip_learned"):
        rule_classes = [R for R in rule_classes if R.name != "learned_policy"]
        log("learned_policy_skipped", profile="demo")
    if not asr.get("skip") and not asr.get("skip_learned"):
        seen, calib = {}, []
        for sp in specs:
            if sp.holdout:
                continue
            key = sp.family
            if seen.get(key, 0) < (2 if sp.quiet else 1):
                calib.append(sp); seen[key] = seen.get(key, 0) + 1
        if progress:
            progress("assurance", stage="learned_policy")
        learned = train_and_evaluate(calib, [R for R in rule_classes if R.name != "learned_policy"],
                                     seed=0, stop=stop)
        log("learned_policy", n_logged=learned["n_logged_trajectories"],
            coverage=learned["model_coverage"], action_share=learned["action_share"],
            ope={k: {kk: vv for kk, vv in v.items()} for k, v in learned["ope"].items()})
    rules = evaluate_rules(specs, rule_classes, cache, flags_from=flags_from.name,
                           log=log, stop=stop, B=bootstrap_B)
    rule_event_times = rules.pop("_event_times", {})
    surv = survival_analysis(specs, cache, rule_event_times, names)
    log("survival_analysis", arms=surv["arms"],
        medians={k: v["median"] for k, v in surv["kaplan_meier"].items()},
        cox_hr=(surv["cox"] or {}).get("hazard_ratio"),
        pre_emption={k: v["pre_emption_probability"] for k, v in surv["sentinel_alerts"].items()})
    log("rules_evaluated", **{k: {kk: vv for kk, vv in v.items() if kk != "burden_by_class"}
                              for k, v in rules.items()})
    if progress:
        progress("rules", rules=rules)

    rl_stats = None
    if any(sp.rl_n > 0 for sp in specs):
        from .rl_agents import get_trained_population, policy_convergence
        rl_n = max(sp.rl_n for sp in specs if sp.rl_n > 0)
        rl_stats = policy_convergence(get_trained_population(rl_n, seed=0))
        rl_stats["sentinel_f1_on_rl_herd"] = {
            sname: round(float(np.mean([r["f1"] for r in rows
                                        if r["family"] == "rl_emergent" and r["sentinel"] == sname])), 2)
            for sname in names if any(r["family"] == "rl_emergent" for r in rows)}
        log("rl_emergence", **rl_stats)

    # three worlds: the same shock in a quiet, a herding and a treated market
    quiet_spec = ScenarioSpec(name="tw_quiet", vendor_rhos=(0.45, 0.25), shock_time=None, seed=7)
    herd_spec = ScenarioSpec(name="tw_herd", vendor_shares=(0.40, 0.15),
                             vendor_rhos=(0.90, 0.30), seed=7)
    if progress:
        progress("three_worlds_start")
    q_res = simulate(quiet_spec, intervention=tick_hook(quiet_spec) if tick_hook else None, stop=stop)
    h_res = simulate(herd_spec, intervention=tick_hook(herd_spec) if tick_hook else None, stop=stop)
    h_out = flags_from().run(h_res)
    from .evaluate import DynamicThrottle
    rule = DynamicThrottle().make(herd_spec.n_agents, flags_online=h_out["flags_online"])
    if tick_hook:
        import dataclasses
        base_rule = rule
        stream = tick_hook(dataclasses.replace(herd_spec, name="tw_treated"))

        def chained(t, state):
            act = base_rule(t, state)
            stream(t, state)
            return act
        t_res = simulate(herd_spec, intervention=chained, stop=stop)
    else:
        t_res = simulate(herd_spec, intervention=rule, stop=stop)
    three = {"shock": herd_spec.shock_time,
             "quiet": np.exp(q_res.prices).round(5).tolist(),
             "herd": np.exp(h_res.prices).round(5).tolist(),
             "treated": np.exp(t_res.prices).round(5).tolist(),
             "post_shock_dd": {"quiet": q_res.post_shock_drawdown(),
                               "herd": h_res.post_shock_drawdown(),
                               "treated": t_res.post_shock_drawdown()},
             "drawdown": {"quiet": q_res.max_drawdown(), "herd": h_res.max_drawdown(),
                          "treated": t_res.max_drawdown()},
             "pre_shock_vol": {"quiet": q_res.pre_shock_vol(), "herd": h_res.pre_shock_vol()}}
    log("three_worlds", **{k: v for k, v in three.items() if k not in ("quiet", "herd", "treated")})

    # ---------- version 3 assurance stages ----------
    cert = certify(rows, names)
    log("conformal_certification", **{k: {kk: vv for kk, vv in v.items()} for k, v in cert.items()})
    fr_s, fr_r = sentinel_frontier(summary), rule_frontier(rules)
    log("cost_frontier", sentinels=fr_s, rules=fr_r)
    # certification is adjudicated by the conformal guarantee (finite sample,
    # exchangeable quiet scenarios), not by the point estimate of the quiet
    # alert rate; the point estimate is the fallback when no guarantee holds
    conf_ok = certifiable(cert, summary)
    if conf_ok:
        certified, certification_basis = conf_ok[0], "conformal"
    elif best_certifiable(summary):
        certified, certification_basis = best_certifiable(summary), "empirical false alert rate"
    else:
        certified, certification_basis = gap["decision_ranking"][0], "decision F1 only (nothing certifiable)"
    attribution = truth = dose = red = game = None
    if not asr.get("skip"):
        if progress:
            progress("assurance", stage="attribution", conformal=cert, frontier={"sentinels": fr_s, "rules": fr_r})
        if not asr.get("skip_attribution"):
            attribution = attribute_battery(specs, cache, names, per_family=asr["attribution_per_family"])
            log("attribution", n_scenarios=attribution["n_scenarios"],
                by_sentinel=attribution["by_sentinel"],
                impact_orderings={e["scenario"]: e["impact_ordering"] for e in attribution["scenarios"]})
        else:
            log("attribution_skipped", profile="demo")
        if progress:
            progress("assurance", stage="truth_audit", attribution=attribution)
        if not asr.get("skip_truth"):
            truth = truth_dependence(specs, sentinel_classes, families=asr["truth_families"],
                                     per_family=asr["truth_per_family"],
                                     n_quiet=asr["truth_n_quiet"], stop=stop)
            log("truth_dependence", comparison=truth["comparison"],
                rank_one=truth["rank_one_under_every_generator"], n_scenarios=truth["n_scenarios"])
        else:
            log("truth_dependence_skipped", profile="demo")
        if progress:
            progress("assurance", stage="concentration", truth=truth)
        if not asr.get("skip_dose"):
            dose = concentration_sweep(seeds=asr["dose_seeds"], stop=stop)
            log("concentration_sweep", curvature=dose["curvature"], convex=dose["convex"],
                threshold_share=dose["dislocation_threshold_share"])
        else:
            log("concentration_sweep_skipped", profile="demo")
        if progress:
            progress("assurance", stage="redteam", dose=dose)
        red = adversarial_search(certified, sentinel_classes, budget=asr["redteam_budget"], stop=stop)
        red["battery_f1_certified"] = float(summary[certified]["decision_f1"])
        red["robustness_margin"] = (None if red["worst_case_f1"] is None else
                                    float(red["battery_f1_certified"] - red["worst_case_f1"]))
        log("adversarial_search", certified=certified, worst_case_f1=red["worst_case_f1"],
            n_dislocating=red["n_dislocating"], budget=red["budget"])
        game = game_from_trials(red, names)
        if game:
            log("matrix_game", maximin=game["maximin_pure"], maximin_value=game["maximin_value"],
                mixed_value=game["mixed_value"], mixture=game["mixture"])
    base_dd = [cache[sp.name]["res"].post_shock_drawdown() for sp in specs
               if not sp.quiet and not sp.holdout and sp.name in cache]
    risk = risk_report(rules, base_dd, B=min(300, bootstrap_B))
    log("risk_report", untreated=risk["untreated"],
        es_reduction={k: v["es_reduction"] for k, v in risk["rules"].items()})
    appraisal = appraise(rules, risk, {"sentinels": fr_s, "rules": fr_r})
    log("options_appraisal", recommended=appraisal["recommended"], n_eligible=appraisal["n_eligible"])

    # version 3.3: observed data brought through quarantine. Anchoring against
    # the battery's quiet family, and the observed window where flows exist.
    data_block = None
    if datasets:
        quiet_res = [cache[sp.name]["res"] for sp in specs if sp.quiet and not sp.holdout and sp.name in cache]
        bq = {}
        if quiet_res:
            import numpy as _np
            qs = [_obs_stats(_np.exp(r.prices)) for r in quiet_res]
            qs = [q for q in qs if q]
            if qs:
                bq = {k: float(_np.mean([q[k] for q in qs])) for k in ("vol", "kurtosis", "abs_autocorr_1",
                                                                      "max_drawdown")}
        entries = []
        for ds in datasets:
            if not ds.get("ok"):
                continue
            e = {"summary": dataset_summary(ds), "anchoring": anchoring(ds, bq) if bq else None,
                 "observed_window": observed_window(ds, sentinel_classes),
                 "calibration": ds.get("calibration")}
            entries.append(e)
            log("dataset_used", name=ds["name"], sha256=ds["sha256"], classification=ds["classification"],
                n_rows=ds["n_rows"], anchoring_within=(e["anchoring"] or {}).get("n_within"),
                observed_ok=e["observed_window"].get("ok"))
        from .calibrate import calibration_shift
        cal_fams = sorted({sp.family for sp in specs if sp.family.startswith("calibrated_")})
        data_block = {"datasets": entries, "battery_quiet": bq, "n_datasets": len(entries),
                      "empirical_family_present": any(sp.family == "empirical" for sp in specs),
                      "calibrated_families": cal_fams,
                      "hybrid_families": sorted({sp.family for sp in specs if sp.family.startswith("hybrid_")}),
                      "calibration_shift": calibration_shift(
                          rows, names, cal_fams,
                          positives_present=any(cache[sp.name]["res"].destabilising.any() for sp in specs
                                                if sp.family in cal_fams and sp.name in cache)) if cal_fams else None}
        if data_block["calibration_shift"]:
            log("calibration_shift", **{k: v for k, v in data_block["calibration_shift"].items()
                                        if k in ("tau", "rank_one_preserved", "families")})
        if progress:
            progress("assurance", stage="data", data=data_block)
    # version 3.9: the backtesting suite (episodes, sentinel timing and workload,
    # rules on hybrid episodes, walk forward validation of the certification)
    bt = None
    if not asr.get("skip"):
        bt = backtest_all(datasets or [], [ds.get("calibration") for ds in (datasets or [])], rows,
                          sentinel_classes, rule_classes, stop=stop)
        log("backtest", n_datasets=bt["n_datasets"], n_episodes=bt["n_episodes"],
            walk_forward={k: v for k, v in (bt["walk_forward"] or {}).items() if k != "folds"})

    battery = {"n_scenarios": len(specs),
               "n_herd": sum(1 for s in specs if not s.quiet and not s.holdout),
               "n_quiet": sum(1 for s in specs if s.quiet and not s.holdout),
               "n_holdout": sum(1 for s in specs if s.holdout),
               "families": sorted({s.family for s in specs}),
               "family_notes": {f: FAMILY_NOTES.get(f) or CUSTOM_NOTES.get(f, "") for f in sorted({s.family for s in specs})},
               "generators": sorted({s.generator for s in specs}),
               "seeds": [s.seed for s in specs],
               "specs": [s.describe() for s in specs]}
    used_personas = {s.persona for s in specs if s.persona_share > 0 and s.persona}
    personas = {k: v for k, v in registry_snapshot().items() if k in used_personas}
    artefacts = {
        "question": question,
        "sentinels": summary,
        "sentinels_holdout": holdout,
        "decision_gap": gap,
        "decision_gap_moments": gap_m,
        "decision_gap_bootstrap": gb,
        "decision_gap_bootstrap_moments": gb_m,
        "decision_gap_holdout": gap_holdout,
        "fidelity_constructs": FIDELITY_CONSTRUCTS,
        "autonomy": autonomy_public(aut),
        "rules": rules,
        "survival": surv,
        "rule_library": {k: v for k, v in RULE_LIBRARY.items() if k in rules},
        "rl_emergence": rl_stats,
        "three_worlds": {k: v for k, v in three.items() if k not in ("quiet", "herd", "treated")},
        "conformal": cert,
        "conformally_certifiable": conf_ok,
        "certified": certified,
        "certification_basis": certification_basis,
        "certification_alpha": FALSE_ALERT_BUDGET,
        "frontier": {"sentinels": fr_s, "rules": fr_r},
        "attribution": attribution,
        "truth_audit": truth,
        "concentration": dose,
        "redteam": {"evasion": red, "injection": None},
        "game": game,
        "risk": risk,
        "appraisal": appraisal,
        "learned_policy": learned,
        "data": data_block,
        "personas": personas,
        "agents": {k: v for k, v in agents_snapshot().items()
                   if any(k == a for s in specs for a, _ in s.custom_agents)},
        "backtest": bt,
        "battery": battery,
        "provenance": dict(provenance(), battery_hash=battery_hash(specs),
                           flags_from=flags_from.name,
                           sentinel_set=names, rule_set=[R.name for R in rule_classes],
                           dislocation_threshold=DISLOCATION_DD,
                           bootstrap_B=bootstrap_B,
                           elapsed_s=round(time.time() - t0, 1)),
    }
    if not asr.get("skip"):
        # the injection suite needs a provisional briefing to test the drafter
        from .briefing import draft_briefing
        provisional = draft_briefing(artefacts, {"ok": True, "n_checks": 0}, {}, "provisional")
        inj = injection_suite(artefacts, provisional)
        artefacts["redteam"]["injection"] = inj
        log("injection_suite", n_cases=inj["n_cases"], n_contained=inj["n_contained"],
            all_contained=inj["all_contained"])
        if progress:
            progress("assurance", stage="done", redteam=artefacts["redteam"])
    artefacts["reports"] = needs_coverage(artefacts)
    for rn, rv in artefacts["rules"].items():
        lvl = RULE_OVERSIGHT.get(rn)
        if lvl:
            rv["human_oversight"] = {"level": lvl[0], "note": lvl[1]}
    parse = interpret_question(question)
    artefacts["question_interpretation"] = {k: parse[k] for k in ("matched", "params", "mechanisms", "rules_of_interest",
                                                                   "sentinels_of_interest", "unmatched", "interpreted")}
    artefacts["direct_answer"] = direct_answer(parse, artefacts, SENTINEL_LABELS)
    log("report_needs", n_answered=artefacts["reports"]["n_answered"], n_partial=artefacts["reports"]["n_partial"],
        n_open=artefacts["reports"]["n_open"])
    artefacts["provenance"]["elapsed_s"] = round(time.time() - t0, 1)
    extras = {"rows": rows, "aut": aut, "tapes": tapes, "three": three, "net": net,
              "cache": cache}
    return artefacts, extras
