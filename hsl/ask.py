"""ASK: grounded question answering over one run.

Version 1 built the prompt in the browser and relayed whatever the client
sent to the model. Version 2 moves everything server side. The client
sends a question; the server retrieves context from the run, composes a
deterministic answer for the common supervisory questions directly from
the artefacts, and only then, if a model is configured, asks the model to
phrase an answer from that context under a fixed prompt. The deterministic
answer is always available, so the page is useful offline, and every
question, the sources used and the model (if any) are chained into the
ledger.
"""

import math
import re

from .sentinels import SENTINEL_LABELS
from ._common import nice_name as _nice

GLOSSARY = [
    ("decision gap", "rank divergence between the aggregate fidelity ranking and the "
     "decision accuracy ranking of the same tools; 0 means they agree, 1 means they fully "
     "invert. Reported with a bootstrap probability of inversion because with few tools "
     "Kendall tau takes few values."),
    ("aggregate fidelity", "how well a sentinel's stress index tracks realised aggregate "
     "statistics; the conventional validation criterion, not a decision criterion. Two "
     "constructs are declared: conventional (rolling volatility) and multi moment."),
    ("decision f1", "F1 of the sentinel's flagged agents against the generative ground truth "
     "of destabilising agents on herding scenarios; the score that matches the supervisory "
     "decision."),
    ("false alert rate", "share of quiet scenarios on which the sentinel raised an alert."),
    ("lead time", "steps from the sentinel's first alert to the shock; positive means the "
     "cluster was visible before the shock landed. It is not a forecast of the shock."),
    ("containment", "one minus treated over untreated mean post shock drawdown; the share "
     "of the shock response a rule removed."),
    ("dislocation probability", "share of herding scenarios whose post shock drawdown "
     "exceeds the declared threshold, before and after treatment."),
    ("burden", "share of intended order flow suppressed by a rule after the shock, by "
     "participant class and by ground truth; the cost side of an intervention."),
    ("false halt", "a rule triggering on a quiet market."),
    ("gate 1", "named human approval of the exact battery (by hash) before anything simulates."),
    ("gate 2", "named human approval before the briefing is released; armed only after the "
     "critic passes; can be refused with reasons, which are recorded."),
    ("four eyes", "the approver at a gate must differ from the preparer of the run."),
    ("emergency stop", "halts orchestration mid run; recorded in the ledger; the partial "
     "evidence pack is still exportable."),
    ("critic", "independent recomputation of the headline claims from the per scenario rows, "
     "the battery hash binding, interval checks, the no lookahead check, ledger replay and "
     "vetting of every number in the briefing."),
    ("autonomy gate", "score triggered autonomy after Iravani et al.: two thresholds on the "
     "sentinel's per scenario herding score; autonomous action only in the score tails the "
     "battery backs with zero claims; the band between escalates to the named supervisor."),
    ("leave one out", "each scenario is classified by gates fitted without it; the resulting "
     "claim rate is the out of sample number to quote."),
    ("held out family", "scenarios with a different population, shock time and impact "
     "coefficient, never used to calibrate any threshold."),
    ("evader", "an adversarial family in which the dominant vendor rotates cohorts so pairwise "
     "correlation stays low while aggregate impact is preserved."),
    ("evidence grade", "A, B or C set by the number of scenarios and the width of the bootstrap "
     "interval behind a headline number."),
    ("ledger", "append only, hash chained, HMAC signed record of every step, gate and release; "
     "replayable with python -m hsl.ledger verify."),
    ("conformal guarantee", "alert threshold set by conformal anomaly detection on the quiet "
     "calibration scenarios; if a new quiet scenario is exchangeable with them, the false alert "
     "probability is at most alpha whatever the sentinel. Held out quiet scenarios check exchangeability "
     "empirically and are not covered."),
    ("shapley attribution", "the average marginal contribution of an agent group to the post shock "
     "drawdown over every order of silencing the other groups under common random numbers; the "
     "behavioural ground truth of which group moved the market."),
    ("cost frontier", "the loss of each tool as a function of the declared weight c on false alerts "
     "or false halts relative to misses; the intervals of c on which each tool is optimal."),
    ("truth dependence", "whether the decision ranking of the sentinels survives a change of the market "
     "generator (shared signal, imitation, square root impact)."),
    ("concentration dose response", "post shock drawdown and dislocation probability as the dominant "
     "vendor's share is swept at fixed correlation; tests the convexity prediction of Meng and Chen "
     "(2026)."),
    ("red team", "a budgeted adversarial search for the evasion that hurts the certified sentinel most "
     "while the market still dislocates, and an injection suite against the planner, the persona "
     "elicitation, the drafter, ASK and the ledger."),
    ("persona", "an LLM trading persona distilled once into a policy table over fifteen market states; "
     "agents sharing it trade from the same table, so correlation follows from a shared model."),
]


def _lab(n):
    return SENTINEL_LABELS.get(n, str(n).replace("_", " "))


def _f(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _pct(x):
    return "n/a" if x is None else f"{round(x * 100):d}%"


def _ci(ci):
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def _n(k, word):
    return f"{k} {word}" + ("" if k == 1 else "s")


def chunks(snap):
    """Retrieval units built from the run snapshot."""
    ch = []

    def add(cid, title, text):
        ch.append({"id": cid, "title": title, "text": text})

    add("run", "this run", f"Run {snap.get('run_id') or '(none)'}, stage {str(snap.get('stage', '')).upper()}. "
        f"Policy question: {snap.get('question') or '(none yet)'}. Prepared by "
        f"{snap.get('preparer') or '(not set)'}. {len(snap.get('specs') or [])} scenarios planned.")
    ap = snap.get("approvals") or {}
    if ap:
        add("approvals", "approvals", " ".join(
            f"Gate {k[-1]}: {v.get('decision', 'approved')} by {v.get('actor')} at {v.get('ts')}"
            + (f" (reason: {v.get('reason')})" if v.get("reason") else "") + "."
            for k, v in ap.items() if isinstance(v, dict)))
    for sp in snap.get("specs") or []:
        add("scenario:" + sp["name"], "scenario " + sp["name"],
            f"family {sp.get('family')}, {sp.get('n_agents')} agents, vendor shares "
            f"{sp.get('vendor_shares')}, vendor rhos {sp.get('vendor_rhos')}, shock at "
            f"t={sp.get('shock_time')}, RL agents {sp.get('rl_n', 0)}, evader cohorts "
            f"{sp.get('evader_cohorts', 0)}, held out {sp.get('holdout')}, seed {sp.get('seed')}.")
    for name, v in (snap.get("summary") or {}).items():
        add("sentinel:" + name, "sentinel " + _lab(name),
            f"aggregate fidelity {_f(v['aggregate_fidelity'])} (multi moment "
            f"{_f(v.get('fidelity_moments'))}), decision F1 {_f(v['decision_f1'])} with 95% "
            f"interval {_ci(v['ci']['decision_f1'])} grade {v['grade']['decision_f1']}, precision "
            f"{_f(v['precision'])}, recall {_f(v['recall'])}, mean lead time "
            f"{_f(v['mean_lead_time'], 0)}, alerts on {_pct(v.get('share_alerting'))} of herding "
            f"scenarios, false alert rate {_f(v['false_alert_rate'])}. By family: "
            + ", ".join(f"{k} F1 {_f(x['decision_f1'])}" for k, x in v.get("by_family", {}).items()) + ".")
    for name, v in (snap.get("holdout") or {}).items():
        add("holdout:" + name, "held out result " + _lab(name),
            f"decision F1 {_f(v['decision_f1'])}, recall {_f(v['recall'])}, false alert rate "
            f"{_f(v['false_alert_rate'])} on {v['n_herd']} held out herding and {v['n_quiet']} "
            f"held out quiet scenarios.")
    g = snap.get("gap")
    if g:
        gb = snap.get("gap_bootstrap") or {}
        gm = snap.get("gap_moments") or {}
        add("gap", "decision gap",
            f"decision gap {_f(g['decision_gap'])}, Kendall tau {g['kendall_tau']:+.2f} over "
            f"{g['n_tools']} tools under the conventional fidelity construct; "
            f"{_f(gm.get('decision_gap'))} under the multi moment construct. Fidelity ranking: "
            f"{' > '.join(_lab(x) for x in g['fidelity_ranking'])}. Decision ranking: "
            f"{' > '.join(_lab(x) for x in g['decision_ranking'])}. Bootstrap over "
            f"{gb.get('n_scenarios')} scenarios: probability of inversion {_f(gb.get('p_inversion'))}, "
            f"gap interval {_ci(gb.get('gap_ci'))}.")
    for name, v in (snap.get("rules") or {}).items():
        b = v.get("burden_by_class", {})
        add("rule:" + name, "intervention rule " + v.get("label", name),
            f"post shock drawdown untreated {_f(v['mean_post_shock_dd_untreated'], 3)}, treated "
            f"{_f(v['mean_post_shock_dd_treated'], 3)}, containment {_f(v['containment'])} with "
            f"interval {_ci(v['containment_ci'])} grade {v['grade']}, dislocation probability "
            f"{_f(v['crash_prob_untreated'])} before and {_f(v['crash_prob_treated'])} after, false "
            f"halt rate on quiet markets {_f(v['false_halt_rate'])}, burden on non destabilising "
            f"agents {_f(b.get('non_destabilising'))} and on destabilising agents "
            f"{_f(b.get('destabilising'))}; fundamentalists {_f(b.get('fundamentalist'))}, noise "
            f"traders {_f(b.get('noise_trader'))}. Targeted: {v.get('targeted')}; lookahead: "
            f"{v.get('lookahead')}.")
    tw = snap.get("three")
    if tw:
        d = tw.get("post_shock_dd", {})
        add("worlds", "three worlds", f"same shock, three worlds: post shock drawdown quiet "
            f"{_f(d.get('quiet'), 3)}, herd {_f(d.get('herd'), 3)}, throttle treated "
            f"{_f(d.get('treated'), 3)}; herd pre shock volatility "
            f"{_f(tw.get('pre_shock_vol', {}).get('herd'), 1)} times noise.")
    rl = snap.get("rl")
    if rl:
        add("rl", "RL emergence", f"policy convergence {_f(rl.get('policy_convergence'))}, momentum "
            f"slope {_f(rl.get('momentum_slope'))}, sentinel F1 on the emergent herd "
            f"{rl.get('sentinel_f1_on_rl_herd')}.")
    for name, v in (snap.get("aut") or {}).items():
        loo = v.get("loo", {})
        add("aut:" + name, "autonomy gate " + _lab(name),
            f"gates {_f(v['t_lo'])} / {_f(v['t_hi'])} on the normalised pre emption score; backs "
            f"{_pct(v['breadth'])} of the battery in sample (auto clear {_pct(v['clear'])}, auto "
            f"throttle " + (_pct(v['throttle']) if v['throttle_ok'] else
                            f"withdrawn, localisation lift {_f(v['lift'])} below the "
                            f"{_f(v['lift_bar'])} bar") +
            f"); leave one out: backs {_pct(loo.get('backed'))} with {_n(loo.get('claims', 0), 'claim')} "
            f"(claim rate {_pct(loo.get('claim_rate'))}). Separable: {v.get('separable')}.")
    art = snap.get("artefacts") or {}
    for name, v in (art.get("conformal") or {}).items():
        add("conformal:" + name, "conformal certification " + _lab(name),
            f"calibration quiet scenarios {v['n_calibration']}, alpha {_f(v['alpha'])}, guaranteed false "
            f"alert bound {_f(v['guaranteed_false_alert_bound']) if v['guarantee_achievable'] else 'not achievable'}, "
            f"conformal threshold {_f(v['threshold_score'])}, power on calibration herds "
            f"{_f(v['power_calibration_herd'])}, held out quiet alert rate {_f(v['false_alert_rate_holdout'])}, "
            f"power on held out herds {_f(v['power_holdout_herd'])}.")
    fr = art.get("frontier") or {}
    if fr.get("sentinels"):
        fs, frr = fr["sentinels"], fr["rules"]
        add("frontier", "supervisory cost frontier",
            "sentinels: " + "; ".join(f"{_lab(g['tool'])} optimal for c in {_f(g['c_from'])} to {_f(g['c_to'])}"
                                     for g in fs["segments"]) +
            ". Rules: " + "; ".join(f"{g['tool']} optimal for c in {_f(g['c_from'])} to {_f(g['c_to'])}"
                                     for g in frr["segments"]) +
            f". At c = {_f(fs['c_declared'])}: sentinel {_lab(fs['best_at_declared'])}, rule {frr['best_at_declared']}.")
    at = art.get("attribution")
    if at:
        for e in at["scenarios"]:
            add("attribution:" + e["scenario"], "attribution " + _nice(e["scenario"]),
                "impact ordering " + " > ".join(f"{_nice(g)} ({_f(e['shapley'][g], 3)})" for g in e["impact_ordering"])
                + f"; full drawdown {_f(e['drawdown_full'], 3)}, all silenced {_f(e['drawdown_all_silenced'], 3)}.")
        add("attribution", "attribution by sentinel", "; ".join(
            f"{_lab(n)} puts {_f(v['mean_share_on_top_group'])} of its flags on the highest impact group "
            f"(rank correlation {_f(v['mean_tau_flags_vs_impact'])})" for n, v in at["by_sentinel"].items()) + ".")
    ta = art.get("truth_audit")
    if ta:
        add("truth", "truth dependence audit", "; ".join(
            f"{g}: ranking {' > '.join(_lab(x) for x in pg['ranking'])}"
            + (f", tau {_f(ta['comparison'][g]['tau_vs_shared_signal'])}, max rank shift "
               f"{ta['comparison'][g]['max_rank_shift']}" if g in ta["comparison"] else " (reference)")
            for g, pg in ta["per_generator"].items()) +
            f". Rank one under every generator: {_lab(ta['rank_one_under_every_generator']) if ta.get('rank_one_under_every_generator') else 'none'}.")
    dose = art.get("concentration")
    if dose:
        add("concentration", "concentration dose response",
            f"vendor correlation {_f(dose['rho'])}; " + "; ".join(
                f"share {_f(l['share'])}: drawdown {_f(l['mean_post_shock_dd'], 3)}, amplification "
                f"{_f(l['amplification'], 1)}, dislocation probability {_f(l['dislocation_prob'])}"
                for l in dose["levels"]) +
            f". Fitted response {'convex' if dose['convex'] else 'not convex'} (curvature "
            f"{_f(dose['curvature'], 3)}); dislocations become the more likely outcome from share "
            f"{_f(dose.get('dislocation_threshold_share'))}.")
    rt = art.get("redteam") or {}
    ev = rt.get("evasion")
    if ev:
        wc = ev.get("worst_case")
        add("redteam", "red team worst case",
            (f"certified {_lab(ev['certified'])}: battery F1 {_f(ev.get('battery_f1_certified'))}, worst case F1 "
             f"{_f(ev['worst_case_f1'])} (margin {_f(ev.get('robustness_margin'))}) at cohorts "
             f"{int(wc['params']['evader_cohorts'])}, period {int(wc['params']['evader_period'])}, rho "
             f"{_f(wc['params']['rho'])}, share {_f(wc['params']['share'])}; all sentinels there: "
             + ", ".join(f"{_lab(k)} {_f(v)}" for k, v in wc["f1_all"].items()) + "."
             if wc else f"no dislocating evasion found in {ev['budget']} trials."))
    inj = rt.get("injection")
    if inj:
        add("injection", "injection containment",
            f"{inj['n_contained']} of {inj['n_cases']} adversarial cases contained across "
            f"{', '.join(inj['surfaces'])}" + (
                "" if inj["all_contained"] else "; failed: " +
                ", ".join(c["name"] for c in inj["cases"] if not c["contained"])) + ".")
    sv = art.get("survival")
    if sv and sv.get("kaplan_meier"):
        add("survival", "time to dislocation", "; ".join(
            f"{arm.replace('_', ' ')}: {kk['events']} of {kk['n']} runs dislocated, median "
            f"{'not reached' if kk['median'] is None else _f(kk['median'], 0)} steps, contained after 20 steps "
            f"{_f(kk['survival_at_20'])}" for arm, kk in sv["kaplan_meier"].items()) +
            ((". Cox hazard ratios against the untreated market: " + ", ".join(
                f"{n.replace('_', ' ')} {_f(h)} ({_f(sv['cox']['hr_ci'][n][0])} to {_f(sv['cox']['hr_ci'][n][1])})"
                for n, h in sv["cox"]["hazard_ratio"].items()) + ".") if sv.get("cox") else "."))
        add("survival:alerts", "pre emption by sentinel", "; ".join(
            f"{_lab(n)}: alerts before the shock in {v['alerts_before_shock']} of {v['n']} scenarios, pre emption "
            f"probability {_f(v['pre_emption_probability'])}" for n, v in (sv.get("sentinel_alerts") or {}).items()) + ".")
    rr = art.get("rules") or snap.get("rules") or {}
    if rr and any(v.get("es_post_shock_dd_treated") is not None for v in rr.values()):
        add("tailrisk", "tail risk by rule", "; ".join(
            f"{v.get('label', n)}: expected shortfall untreated {_f(v.get('es_post_shock_dd_untreated'), 3)}, treated "
            f"{_f(v.get('es_post_shock_dd_treated'), 3)}" for n, v in rr.items()) + ".")
    da = art.get("direct_answer")
    qi = art.get("question_interpretation") or {}
    if da:
        add("question", "direct answer to the policy question",
            ("the case asked about is its own family; " if da.get("family_present") else "") +
            "; ".join((f"{t['label']}: containment {_f(t['containment_battery'])}"
                       + (f", {_f(t['containment_question'])} on the question family" if t.get("containment_question") is not None else "")
                       + f", false halts {_f(t['false_halt_rate'])}") if t["kind"] == "rule" else
                      (f"{t['label']}: decision F1 {_f(t['decision_f1'])}, false alerts {_f(t['false_alert_rate'])}")
                      for t in da["tools"]) +
            f". Matched: {', '.join(qi.get('matched', []))}. Not interpreted: {'; '.join(qi.get('unmatched', [])) or 'nothing'}.")
    bt = art.get("backtest")
    if bt:
        wf = bt.get("walk_forward") or {}
        add("backtest", "backtests",
            (f"walk forward over {wf.get('n_folds')} folds: mean regret {_f(wf.get('mean_regret'))}, certified tool still "
             f"best on {_f(wf.get('p_still_best'))} of test folds. " if wf else "") +
            "; ".join(f"{d['name']}: {len(d['episodes'])} episodes" +
                      ("; " + ", ".join(f"{_lab(n)} detects {_f(v['detection_rate'])} with median lead {_f(v['median_lead'], 0)}"
                                        for n, v in (d.get('sentinels') or {}).get('sentinels', {}).items()
                                        if not v.get('skipped')) if d.get("sentinels") else "") +
                      ("; rules: " + ", ".join(f"{n.replace('_', ' ')} {_f(v['mean_containment'])}"
                                               for n, v in d["rules"]["rules"].items()) if d.get("rules") and d["rules"].get("rules") else "")
                      for d in bt.get("datasets", [])) + ".")
    rp = art.get("reports")
    if rp:
        add("reports", "needs flagged by the reports",
            f"{rp['n_answered']} answered, {rp['n_partial']} partial, {rp['n_open']} open of {len(rp['needs'])}: " +
            "; ".join(f"{n['id']} {n['need']} ({n['source']}): {n['status']}, {n['evidence']}" for n in rp["needs"]) + ".")
        ind = rp["indicators"]; tc = ind["third_party_concentration"]
        add("indicators", "supervisory indicators",
            f"adoption share up to {_f(ind['adoption']['ai_agent_share_max'])}; vendor HHI up to {_f(tc['vendor_hhi_max'], 3)}, "
            f"top vendor share {_f(tc['top_vendor_share_max'])}, substitutability {_f(tc['substitutability_proxy'])}, "
            f"dislocation threshold share {_f(tc['dislocation_threshold_share'])}; expected shortfall "
            f"{_f(ind['incidents']['expected_shortfall_untreated'], 3)}; data gaps needing firm reporting: " +
            "; ".join(ind["data_gaps"]) + ".")
        for rn, rv in (art.get("rules") or {}).items():
            ho = rv.get("human_oversight")
            if ho:
                add("oversight:" + rn, "human oversight " + rv.get("label", rn),
                    f"{ho['level'].replace('_', ' ')}: {ho['note']}.")
    gm = art.get("game")
    if gm:
        add("game", "sentinel against evader game",
            f"maximin sentinel {_lab(gm['maximin_pure'])} guarantees F1 {_f(gm['maximin_value'])}; mixed strategy "
            f"value {_f(gm['mixed_value'])} with mixture " + ", ".join(f"{_lab(a_)} {_f(p)}" for a_, p in gm["mixture"].items())
            + f"; value of mixing {_f(gm['value_of_mixing'])}; {gm['n_trials']} dislocating evasions.")
    lp = art.get("learned_policy")
    if lp:
        mae = lp.get("mean_abs_error") or {}
        add("learned", "learned policy and off policy evaluation",
            f"learned policy halts in {_f(lp['action_share']['halt'])} and throttles in {_f(lp['action_share']['throttle'])} "
            f"of states; model coverage {_f(lp['model_coverage'])}; mean absolute error against the simulated value: "
            f"importance sampling {_f(mae.get('pdis'), 3)}, doubly robust {_f(mae.get('dr'), 3)}, model based "
            f"{_f(mae.get('model'), 3)}; closest {lp.get('best_estimator')}.")
    ap = art.get("appraisal")
    if ap:
        rec = ap.get("recommended")
        add("appraisal", "regulatory options appraisal",
            (f"recommended tier {rec['tier']} {rec['tier_label']}: {rec['label']} ({rec['instrument']}; basis "
             f"{rec['legal_basis']})" if rec else "no rule passes all tests; monitor and warn") +
            f"; {ap['n_eligible']} eligible; " + "; ".join(
                f"{o['label']} tier {o['tier']} {'passes' if o['passes_all'] else 'fails ' + ', '.join(kk for kk, vv in o['passes'].items() if not vv)}"
                for o in ap["options"]) + ".")
    rk = art.get("risk")
    if rk and rk.get("untreated"):
        u = rk["untreated"]
        add("risk", "value at risk and expected shortfall",
            f"untreated post shock drawdown: mean {_f(u['mean'], 3)}, value at risk {_f(u['var'], 3)}, expected "
            f"shortfall {_f(u['es'], 3)} at level {_f(rk['alpha'])}; ES reduction by rule: " +
            ", ".join(f"{n.replace('_', ' ')} {_f(v['es_reduction'])}" for n, v in rk["rules"].items()) + ".")
    dt = art.get("data")
    if dt and dt.get("datasets"):
        for e in dt["datasets"]:
            s_ = e["summary"]; an = e.get("anchoring") or {}; ow = e.get("observed_window") or {}
            add("data:" + s_["name"], "observed data " + s_["name"],
                f"classification {s_['classification']}, {s_['n_rows']} rows, source {s_.get('source', 'upload')}, "
                f"hash {s_['sha256'][:16]}" + (
                    "; anchoring: " + ", ".join(f"{kk} ratio {_f(an['ratios'][kk])}" for kk in an.get("ratios", {}))
                    + f", {an.get('n_within')} of {an.get('n_compared')} within band" if an.get("ok") else "") + (
                    "; observed window: " + ", ".join(f"{_lab(kk)} flagged {vv['n_flagged']}" for kk, vv in ow["sentinels"].items())
                    if ow.get("ok") else "") + ".")
    sec = art.get("security")
    if sec:
        add("security", "security posture",
            f"{sec['n_pass']} pass, {sec['n_warn']} warn, {sec['n_fail']} fail; " +
            "; ".join(f"{i['control']}: {i['status']} ({i['detail']}; chapter {i['sev3']})" for i in sec["items"]) + ".")
    for name, v in (art.get("personas") or {}).items():
        add("persona:" + name, "persona " + name,
            f"source {v['source'].replace('_', ' ')}, momentum slope {_f(v['momentum_slope'])}, table hash "
            f"{v['table_sha256'][:16]}; {v.get('description', '')}.")
    for name, v in (art.get("rule_library") or {}).items():
        add("rulelib:" + name, "rule library " + name.replace("_", " "),
            f"jurisdiction {v['jurisdiction']}; modelled on {v['basis']}.")
    c = snap.get("critic")
    if c:
        failed = [x["name"] for x in c.get("checks", []) if not x["ok"]]
        add("critic", "critic verdict", f"{'PASSED' if c.get('ok') else 'FAILED'} "
            f"({c.get('n_checks')} checks" + (f"; failed: {failed}" if failed else "") + ").")
    lg = snap.get("ledger")
    if lg:
        add("ledger", "ledger status", f"{lg.get('entries')} entries, head hash "
            f"{str(lg.get('head'))[:16]}, signed {lg.get('signed')}, verified "
            f"{lg.get('ok')}.")
    if snap.get("briefing"):
        add("briefing", "released briefing (excerpt)", " ".join(snap["briefing"].split())[:700])
    for k, v in GLOSSARY:
        add("gloss:" + k, "definition " + k, v)
    return ch


def _tok(s):
    return re.findall(r"[a-z0-9_]+", str(s).lower())


def retrieve(ch, q, k=6):
    N = max(1, len(ch))
    df = {}
    tfs = []
    for c in ch:
        tf = {}
        for t in _tok(c["title"] + " " + c["text"]):
            tf[t] = tf.get(t, 0) + 1
        tfs.append(tf)
        for t in tf:
            df[t] = df.get(t, 0) + 1
    ql = q.lower()
    qt = _tok(q)
    scored = []
    for c, tf in zip(ch, tfs):
        s = sum(tf.get(t, 0) * math.log(1 + N / (df.get(t, 0) + 1)) for t in qt)
        bare = re.sub(r"^[a-z]+:", "", c["id"]).lower()
        if bare and (bare in ql or bare.replace("_", " ") in ql):
            s += 8
        if c["id"].startswith("gloss:"):
            s *= 0.6            # definitions support, they do not lead
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda p: -p[0])
    return [c for _, c in scored[:k]]


INTENTS = [
    ("backtest", ["backtest", "back test", "walk forward", "walk-forward", "episode", "historical", "regret"]),
    ("question", ["the question", "policy question", "direct answer", "what i asked", "my question", "interpret"]),
    ("reports", ["fsb", "iosco", "bank of england", "imf", "report", "needs flagged", "data gap", "indicator",
                 "third party", "third-party", "concentration index", "hhi", "oversight level", "human oversight"]),
    ("game", ["game", "maximin", "minimax", "mixed strategy", "randomis"]),
    ("learned", ["learned policy", "off policy", "off-policy", "importance sampling", "doubly robust",
                 "logged data", "pilot data"]),
    ("appraisal", ["appraisal", "enforcement ladder", "responsive regulation", "proportionality", "legal basis",
                   "instrument", "lowest tier", "which tier"]),
    ("redteam", ["worst case", "red team", "adversarial search", "injection", "evasion", "robustness",
                 "prompt"]),
    ("conformal", ["conformal", "guarantee", "exchangeab", "p value"]),
    ("attribution", ["shapley", "attribut", "caused", "counterfactual", "which group", "moved the market",
                     "impact ordering"]),
    ("frontier", ["frontier", "cost of a false", "trade off", "tradeoff", "weight c", "declared weight"]),
    ("truth", ["generator", "truth depend", "imitation", "square root", "change of world"]),
    ("concentration", ["concentration", "monoculture", "dose", "convex", "adoption share",
                       "vendor share"]),
    ("persona", ["persona", "distill", "policy table"]),
    ("survival", ["survival", "hazard", "time to dislocation", "kaplan", "cox", "how long", "pre emption",
                  "pre-emption", "median time"]),
    ("tailrisk", ["expected shortfall", "tail risk", "worst quarter", "coherent", "shortfall", "value at risk",
                  "pareto", "extreme value"]),
    ("certify", ["certif", "recommend", "which sentinel", "which tool", "best tool", "best sentinel",
                 "should the authority", "adopt", "choose"]),
    ("gap", ["gap", "inver", "kendall", "tau", "fidelity"]),
    ("rules", ["throttle", "breaker", "kill", "rule", "interven", "contain", "burden", "halt",
               "drawdown", "dislocation"]),
    ("autonomy", ["autonom", "backed", "escalat", "claim", "leave one out", "loo"]),
    ("false", ["false alert", "false alarm", "quiet"]),
    ("lead", ["lead", "early", "warning", "before the shock"]),
    ("general", ["held out", "holdout", "generalis", "evader", "adversar", "emergent", "rl ",
                 "reinforcement", "blind spot"]),
    ("ledger", ["ledger", "hash", "chain", "verify", "audit", "tamper", "sign"]),
    ("status", ["gate", "approv", "who ", "status", "stage", "critic", "prepar", "reject"]),
]


def intent_of(q):
    ql = " " + q.lower() + " "
    for name, keys in INTENTS:
        if any(k in ql for k in keys):
            return name
    return "retrieval"


def deterministic_answer(snap, q):
    """Compose an answer from the artefacts for the common supervisory
    questions. Returns (text, source_ids)."""
    it = intent_of(q)
    s, g = snap.get("summary") or {}, snap.get("gap")
    hold, rules, aut = snap.get("holdout") or {}, snap.get("rules") or {}, snap.get("aut") or {}
    gb = snap.get("gap_bootstrap") or {}
    if not s:
        return ("No battery has been scored yet in this run. Plan a battery and approve Gate 1; "
                "the sentinel scores, the decision gap and the rules appear as the run streams.",
                ["run"]), it
    if it == "certify":
        top = g["decision_ranking"][0]
        v = s[top]
        lines = [f"For the supervisory decision (which agents are destabilising), the evidence "
                 f"favours {_lab(top)}: decision F1 {_f(v['decision_f1'])} (95% interval "
                 f"{_f(v['ci']['decision_f1'][0])} to {_f(v['ci']['decision_f1'][1])}, grade "
                 f"{v['grade']['decision_f1']}), recall {_f(v['recall'])}, false alert rate "
                 f"{_f(v['false_alert_rate'])}."]
        if not v.get("within_budget", True):
            ok = [(x["decision_f1"], n) for n, x in s.items() if x.get("within_budget")]
            cert = max(ok)[1] if ok else None
            lines.append(f"However {_lab(top)} exceeds the false alert budget ({_f(v['false_alert_rate'])} "
                         f"against {_f(v.get('false_alert_budget'))} on quiet markets), so it is not "
                         f"certifiable on this battery. "
                         + (f"The best tool within budget is {_lab(cert)} (decision F1 "
                            f"{_f(s[cert]['decision_f1'])}, false alert rate "
                            f"{_f(s[cert]['false_alert_rate'])})." if cert else "No tool is within budget."))
            top = cert or top
            v = s[top]
        fid_top = g["fidelity_ranking"][0]
        if fid_top != top:
            lines.append(f"The tool a fidelity only certification would pick is {_lab(fid_top)} "
                         f"(fidelity {_f(s[fid_top]['aggregate_fidelity'])}, decision F1 "
                         f"{_f(s[fid_top]['decision_f1'])}). Decision gap {_f(g['decision_gap'])}, "
                         f"probability of inversion {_f(gb.get('p_inversion'))} over "
                         f"{gb.get('n_scenarios')} resampled scenarios.")
        if hold.get(top):
            lines.append(f"Held out family: {_lab(top)} decision F1 {_f(hold[top]['decision_f1'])}, "
                         f"false alert rate {_f(hold[top]['false_alert_rate'])}.")
        bf = v.get("by_family", {})
        weak = [k for k, x in bf.items() if x["decision_f1"] < 0.2]
        if weak:
            lines.append(f"Caveat: {_lab(top)} scores below 0.20 on {', '.join(weak)}. Certify for "
                         f"detection on the parametric herds only, and record those families as "
                         f"open calibration items.")
        a = aut.get(top)
        if a:
            lines.append(f"Execution authority: leave one out backs {_pct(a['loo']['backed'])} of "
                         f"the battery with {_n(a['loo']['claims'], 'claim')}; the auto throttle is "
                         + ("available." if a["throttle_ok"] else
                            f"withdrawn (localisation lift {_f(a['lift'])} below the "
                            f"{_f(a['lift_bar'])} bar), so execution stays with the named supervisor."))
        lines.append("This is a comparative ranking on synthetic scenarios, not a forecast; the "
                     "named supervisor decides.")
        return ("\n".join(lines), ["sentinel:" + top, "gap", "holdout:" + top, "aut:" + top]), it
    if it == "gap":
        gm = snap.get("gap_moments") or {}
        gbm = snap.get("gap_bootstrap_moments") or {}
        txt = (f"Decision gap {_f(g['decision_gap'])} (Kendall tau {g['kendall_tau']:+.2f}) under "
               f"the conventional fidelity construct and {_f(gm.get('decision_gap'))} (tau "
               f"{gm.get('kendall_tau', 0):+.2f}) under the multi moment construct. Fidelity "
               f"ranking {' > '.join(_lab(x) for x in g['fidelity_ranking'])}; decision ranking "
               f"{' > '.join(_lab(x) for x in g['decision_ranking'])}. Over {gb.get('B')} scenario "
               f"resamples the rankings invert with probability {_f(gb.get('p_inversion'))} "
               f"(conventional) and {_f(gbm.get('p_inversion'))} (multi moment). With "
               f"{g['n_tools']} tools tau can take only a few values, so quote the resampled "
               f"probability rather than the point value.")
        return (txt, ["gap"]), it
    if it == "rules":
        lines = []
        for n, v in rules.items():
            b = v.get("burden_by_class", {})
            lines.append(f"{v.get('label', n)}: containment {_f(v['containment'])} (interval "
                         f"{_f(v['containment_ci'][0])} to {_f(v['containment_ci'][1])}, grade "
                         f"{v['grade']}), dislocation probability {_f(v['crash_prob_untreated'])} to "
                         f"{_f(v['crash_prob_treated'])}, false halts on quiet markets "
                         f"{_f(v['false_halt_rate'])}, burden on non destabilising agents "
                         f"{_f(b.get('non_destabilising'))} against {_f(b.get('destabilising'))} on "
                         f"destabilising agents; fundamentalists {_f(b.get('fundamentalist'))}, noise "
                         f"traders {_f(b.get('noise_trader'))}.")
        hurt = [v for v in rules.values() if v.get("targeted") and
                (v.get("burden_by_class", {}).get("fundamentalist") or 0)
                >= 0.5 * max(1e-9, v.get("burden_by_class", {}).get("destabilising") or 0)]
        if hurt:
            lines.append("Yes: the targeted rules suppress fundamentalists about as much as the "
                         "destabilising cluster. Fundamentalists trade on a shared signal and are as "
                         "correlated with one another as the herd, so a correlation based flag cannot "
                         "tell the stabilising group from the destabilising one. Removing the mean "
                         "reverting agents is why disconnecting flagged agents can deepen the drawdown.")
        best = max(rules.items(), key=lambda kv: kv[1]["containment"])
        lines.append(f"Highest containment: {best[1].get('label', best[0])}. A targeted rule that "
                     f"loads its burden on the destabilising agents and spares fundamentalists "
                     f"preserves price discovery; a market wide halt does not. Targeted rules act "
                     f"only on flags issued by that step.")
        return ("\n".join(lines), ["rule:" + n for n in rules]), it
    if it == "autonomy":
        lines = []
        for n, v in aut.items():
            loo = v["loo"]
            lines.append(f"{_lab(n)}: in sample breadth {_pct(v['breadth'])}; leave one out backs "
                         f"{_pct(loo['backed'])} with {_n(loo['claims'], 'claim')} (claim rate "
                         f"{_pct(loo['claim_rate'])}); auto throttle "
                         + ("available." if v["throttle_ok"] else
                            f"withdrawn (lift {_f(v['lift'])} below {_f(v['lift_bar'])})."))
        lines.append("Autonomous action is confined to the score tails; the band between the gates "
                     "always escalates to the named supervisor. Quote the leave one out figures.")
        return ("\n".join(lines), ["aut:" + n for n in aut]), it
    if it == "false":
        lines = [f"{_lab(n)}: false alert rate {_f(v['false_alert_rate'])} over {v['n_quiet']} quiet "
                 f"scenarios" + (f", held out {_f(hold[n]['false_alert_rate'])}" if hold.get(n) else "")
                 for n, v in s.items()]
        for n, v in rules.items():
            lines.append(f"{v.get('label', n)}: false halt rate {_f(v['false_halt_rate'])}.")
        return ("\n".join(lines), ["sentinel:" + n for n in s]), it
    if it == "lead":
        lines = [f"{_lab(n)}: mean lead {_f(v['mean_lead_time'], 0)} steps, alerting on "
                 f"{_pct(v.get('share_alerting'))} of herding scenarios" for n, v in s.items()]
        lines.append("Lead time runs from the first alert to the shock. A large positive lead means "
                     "the correlated cluster was visible long before the shock; it is structural "
                     "detection, not a forecast of the shock.")
        return ("\n".join(lines), ["sentinel:" + n for n in s]), it
    if it == "general":
        lines = []
        for n, v in s.items():
            bf = v.get("by_family", {})
            parts = [f"{k} {_f(x['decision_f1'])}" for k, x in bf.items()]
            if hold.get(n):
                parts.append(f"held out {_f(hold[n]['decision_f1'])}")
            lines.append(f"{_lab(n)}: " + ", ".join(parts) + ".")
        rl = snap.get("rl")
        if rl:
            lines.append(f"RL emergence: policy convergence {_f(rl.get('policy_convergence'))}, "
                         f"momentum slope {_f(rl.get('momentum_slope'))}.")
        lines.append("Families where a tool's F1 collapses (evaders, the emergent RL herd) are the "
                     "blind spots a fidelity only certification would never have surfaced.")
        return ("\n".join(lines), ["sentinel:" + n for n in s] + ["rl"]), it
    if it == "ledger":
        lg = snap.get("ledger") or {}
        return (f"The ledger has {lg.get('entries', 0)} entries, head hash "
                f"{str(lg.get('head'))[:16]}, {lg.get('signed', 0)} signed; last replay "
                f"{'verified' if lg.get('ok') else 'not verified'}. Replay it with "
                f"python -m hsl.ledger verify.", ["ledger"]), it
    if it == "status":
        ap = snap.get("approvals") or {}
        c = snap.get("critic")
        txt = (f"Stage {str(snap.get('stage', '')).upper()}. Prepared by "
               f"{snap.get('preparer') or 'n/a'}. " + " ".join(
                   f"Gate {k[-1]} {v.get('decision', 'approved')} by {v.get('actor')} at {v.get('ts')}."
                   for k, v in ap.items() if isinstance(v, dict)))
        if c:
            txt += f" Critic {'passed' if c.get('ok') else 'failed'} ({c.get('n_checks')} checks)."
        return (txt, ["run", "approvals", "critic"]), it
    if it in ("redteam", "conformal", "attribution", "frontier", "truth", "concentration", "persona",
              "survival", "tailrisk", "reports", "game", "learned", "appraisal", "question", "backtest"):
        ch = chunks(snap)
        prefix = {"redteam": ("redteam", "injection"), "conformal": ("conformal:",),
                  "attribution": ("attribution",), "frontier": ("frontier",), "truth": ("truth",),
                  "concentration": ("concentration",), "persona": ("persona:",),
                  "survival": ("survival",), "tailrisk": ("tailrisk", "risk"),
                  "reports": ("reports", "indicators", "oversight:"), "game": ("game",),
                  "learned": ("learned",), "appraisal": ("appraisal",), "question": ("question",),
                  "backtest": ("backtest",)}[it]
        picked = [c for c in ch if any(c["id"].startswith(p) for p in prefix)]
        if picked:
            return ("\n".join(f"{c['title']}: {c['text']}" for c in picked[:8]),
                    [c["id"] for c in picked[:8]]), it
        return (f"This run has no {it.replace('_', ' ')} results yet; they are computed after the rules "
                f"are scored.", ["run"]), it
    ch = chunks(snap)
    srcs = retrieve(ch, q, 3)
    if not srcs:
        return ("I could not find that in this run. Try a sentinel name, a scenario from the "
                "battery, a rule, the decision gap, the autonomy gate or what the authority "
                "should certify.", []), it
    return ("From this run:\n" + "\n".join(f"- {c['text']}" for c in srcs),
            [c["id"] for c in srcs]), it


def answer(snap, q, k=6):
    ch = chunks(snap)
    (text, ids), it = deterministic_answer(snap, q)
    by_id = {c["id"]: c for c in ch}
    sources = [by_id[i] for i in ids if i in by_id]
    for c in retrieve(ch, q, k):
        if c not in sources and len(sources) < k:
            sources.append(c)
    return {"text": text, "sources": sources, "intent": it}
