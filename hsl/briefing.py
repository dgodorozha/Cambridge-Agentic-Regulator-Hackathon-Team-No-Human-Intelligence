"""Supervisory briefing, drafted only from artefacts.json.

Every figure is read from the artefacts; no prose can alter a number, and
the critic vets every number in the text against the artefacts before the
release gate arms. Each headline carries an evidence grade (A, B or C) set
by the width of its bootstrap interval and the number of scenarios behind
it. British spelling; short sentences; no forecasts.
"""

import html as html_mod

from .evaluate import FIDELITY_CONSTRUCTS, BURDEN_WINDOW, best_certifiable
from .sentinels import SENTINEL_LABELS
from ._common import nice_name as _nice

GRADE_NOTE = ("Evidence grades: A means at least 12 scenarios and a 95% "
              "interval half width below 0.10; B means at least 6 scenarios "
              "and a half width below 0.20; C means anything weaker.")


def _f(x, nd=2):
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def _pct(x):
    return "n/a" if x is None else f"{round(x * 100):d}%"


def _ci(ci, nd=2):
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


def _lab(name):
    return SENTINEL_LABELS.get(name, name.replace("_", " "))


def _times(k):
    return "once" if k == 1 else f"{k} times"


def _v3_sections(a):
    """Version 3 assurance sections. Every figure is read from the artefacts;
    sections whose block is absent are skipped."""
    L = []
    w = L.append
    cf = a.get("conformal") or {}
    if cf:
        w("## Certification with a false alert guarantee")
        w("")
        w("| Sentinel | Calibration quiet scenarios | Guaranteed false alert bound | Conformal "
          "threshold | Power, calibration herds | Held out quiet alert rate | Power, held out herds |")
        w("|---|---|---|---|---|---|---|")
        for n, v in cf.items():
            w(f"| {_lab(n)} | {v['n_calibration']} | "
              f"{_f(v['guaranteed_false_alert_bound']) if v['guarantee_achievable'] else 'not achievable'} "
              f"| {_f(v['threshold_score'])} | {_f(v['power_calibration_herd'])} "
              f"| {_f(v['false_alert_rate_holdout'])} | {_f(v['power_holdout_herd'])} |")
        w("")
        cc = a.get("conformally_certifiable") or []
        first = next(iter(cf.values()))
        w(f"The conformal rule flags a scenario when its p value against the {first['n_calibration']} "
          f"calibration quiet scenarios is at most {_f(first['alpha'])}. If a new quiet scenario is "
          f"exchangeable with the calibration set, the false alert probability is at most "
          f"{_f(first['alpha'])} whatever the sentinel and whatever its score distribution; the smallest "
          f"achievable level with this calibration set is {_f(first['min_achievable_level'])}. The held out "
          f"quiet column is the empirical check of exchangeability on a different population and is not "
          f"covered by the guarantee. "
          + (f"Sentinels with an achievable guarantee and conformal power of at least 0.50 on the "
             f"calibration herds, in decision order: {', '.join(_lab(x) for x in cc)}."
             if cc else "No sentinel reaches conformal power 0.50 on the calibration herds."))
        w("")
    fr = a.get("frontier") or {}
    if fr.get("sentinels"):
        fs, frr = fr["sentinels"], fr["rules"]
        w("## Supervisory cost frontier")
        w("")
        w(f"Sentinel loss is {fs['definition']}; rule loss is {frr['definition']}. The weight c is the "
          f"supervisor's declared cost of a false alert or false halt relative to a miss.")
        w("")
        w("| Tool | Optimal for c from | to |")
        w("|---|---|---|")
        for seg in fs["segments"]:
            w(f"| {_lab(seg['tool'])} | {_f(seg['c_from'])} | {_f(seg['c_to'])} |")
        for seg in frr["segments"]:
            w(f"| {a['rules'].get(seg['tool'], {}).get('label', seg['tool'])} | {_f(seg['c_from'])} "
              f"| {_f(seg['c_to'])} |")
        w("")
        w(f"At the declared weight c = {_f(fs['c_declared'])} the sentinel with the lowest loss is "
          f"{_lab(fs['best_at_declared'])} (loss {_f(fs['loss_at_declared'][fs['best_at_declared']])}) "
          f"and the rule with the lowest loss is "
          f"{a['rules'].get(frr['best_at_declared'], {}).get('label', frr['best_at_declared'])} "
          f"(loss {_f(frr['loss_at_declared'][frr['best_at_declared']])}). The sentinel choice switches "
          f"{_times(fs['n_switches'])} across the range of c and the rule choice {_times(frr['n_switches'])}; "
          f"a choice that switches depends on a cost the supervisor has to own.")
        w("")
    at = a.get("attribution")
    if at and at["scenarios"]:
        w("## Counterfactual attribution: which group moved the market")
        w("")
        w("| Scenario | Impact ordering (Shapley value of post shock drawdown) | Full market drawdown "
          "| All groups silenced |")
        w("|---|---|---|---|")
        for e in at["scenarios"]:
            parts = ", ".join(f"{_nice(g)} {_f(e['shapley'][g], 3)}" for g in e["impact_ordering"])
            w(f"| {_nice(e['scenario'])} | {parts} | {_f(e['drawdown_full'], 3)} | {_f(e['drawdown_all_silenced'], 3)} |")
        w("")
        w("| Sentinel | Share of flags on the highest impact group | Rank correlation of flag rates "
          "with impact |")
        w("|---|---|---|")
        for n, v in at["by_sentinel"].items():
            w(f"| {_lab(n)} | {_f(v['mean_share_on_top_group'])} | {_f(v['mean_tau_flags_vs_impact'])} |")
        w("")
        w(f"Each group's Shapley value is its average marginal contribution to the post shock drawdown "
          f"over every order of silencing the other groups, under common random numbers; the values add "
          f"up to the drawdown removed when every group is silenced, which the critic checks. This is the "
          f"behavioural ground truth: it ranks groups by what removing them does, not by how they were "
          f"generated. A sentinel whose flags land on the highest impact group is answering the "
          f"supervisory question; {at['n_scenarios']} scenarios, one per family, were attributed.")
        w("")
    ta = a.get("truth_audit")
    if ta:
        w("## Truth dependence: does the ranking survive a change of generator")
        w("")
        w("| Generator | Decision ranking | Rank correlation with shared signal | Largest rank shift "
          "| Rank one preserved |")
        w("|---|---|---|---|---|")
        for g, pg in ta["per_generator"].items():
            c = ta["comparison"].get(g)
            w(f"| {_nice(g)} | {' > '.join(_lab(x) for x in pg['ranking'])} "
              f"| {_f(c['tau_vs_shared_signal']) if c else 'reference'} "
              f"| {c['max_rank_shift'] if c else 0} | {('yes' if c['rank_one_preserved'] else 'no') if c else 'reference'} |")
        w("")
        r1 = ta.get("rank_one_under_every_generator")
        w(f"The reduced battery ({ta['n_scenarios']} scenarios) was re run with herding produced by "
          f"imitation within a vendor cluster and with square root price impact, and the sentinels were "
          f"re ranked by decision F1 under each. "
          + (f"{_lab(r1)} holds rank one under every generator." if r1 else
             "No sentinel holds rank one under every generator, so the certification is conditional on "
             "the generator; the largest rank shift of any tool is "
             f"{ta['max_rank_shift_any']} positions."))
        w("")
    dose = a.get("concentration")
    if dose:
        w("## Concentration dose response")
        w("")
        w("| Dominant vendor share | Post shock drawdown | Amplification over the quiet baseline "
          "| Dislocation probability |")
        w("|---|---|---|---|")
        for lv in dose["levels"]:
            w(f"| {_f(lv['share'])} | {_f(lv['mean_post_shock_dd'], 3)} | {_f(lv['amplification'], 1)} "
              f"| {_f(lv['dislocation_prob'])} |")
        w("")
        w(f"Vendor correlation is held at {_f(dose['rho'])} and the share of the dominant vendor is "
          f"swept. The fitted response is {'convex' if dose['convex'] else 'not convex'} (quadratic "
          f"coefficient {_f(dose['curvature'], 3)}; {_pct(dose['share_of_positive_second_differences'])} "
          f"of second differences positive). "
          + (f"Dislocations become the more likely outcome from a share of {_f(dose['dislocation_threshold_share'])}. "
             if dose.get("dislocation_threshold_share") is not None else
             "No swept share makes dislocations the more likely outcome. ")
          + f"This tests, inside the sandbox, the prediction of {dose['prediction_tested']}.")
        w("")
    rt = a.get("redteam") or {}
    ev, inj = rt.get("evasion"), rt.get("injection")
    if ev or inj:
        w("## Red team: worst case evasion and injection containment")
        w("")
        if ev:
            wc = ev.get("worst_case")
            if wc:
                p = wc["params"]
                w(f"A budgeted search of {ev['budget']} evasions over cohorts, rotation period, vendor "
                  f"correlation and share found {ev['n_dislocating']} dislocating markets. The worst case "
                  f"for the certified sentinel ({_lab(ev['certified'])}) rotates "
                  f"{int(p['evader_cohorts'])} cohorts every {int(p['evader_period'])} steps at correlation "
                  f"{_f(p['rho'])} and share {_f(p['share'])}: decision F1 {_f(wc['f1_certified'])} against "
                  f"{_f(ev.get('battery_f1_certified'))} on the battery, a robustness margin of "
                  f"{_f(ev.get('robustness_margin'))}. Every sentinel on that market: "
                  + ", ".join(f"{_lab(k)} {_f(v)}" for k, v in wc["f1_all"].items()) + ".")
            else:
                w(f"A budgeted search of {ev['budget']} evasions found no market that still dislocates, so "
                  f"no worst case is reported.")
            w("")
        if inj:
            w(f"Injection containment: {inj['n_contained']} of {inj['n_cases']} adversarial cases against "
              f"the battery planner, the persona elicitation, the briefing drafter, ASK and the ledger "
              f"were contained"
              + (" (all)." if inj["all_contained"] else "; the failures are listed in the artefacts."))
            w("")
    pers = a.get("personas") or {}
    if pers:
        w("## LLM personas in the battery")
        w("")
        w("| Persona | Source | Momentum slope | Table hash |")
        w("|---|---|---|---|")
        for n, v in pers.items():
            w(f"| {n} | {v['source'].replace('_', ' ')} | {_f(v['momentum_slope'])} | {v['table_sha256'][:16]} |")
        w("")
        w("A persona is distilled once into a policy table over fifteen market states; every agent that "
          "shares it trades from the same table plus its own execution noise, so their correlation is a "
          "consequence of a shared model. The table hash was bound into the battery at Gate 1 and the "
          "simulator refuses a table that has changed. An offline surrogate is a documented synthetic "
          "table, not a claim about any real model.")
        w("")
    sv = a.get("survival")
    if sv and sv.get("kaplan_meier"):
        w("## Time to dislocation: survival analysis of the battery")
        w("")
        w("| Arm | Runs | Dislocations | Median steps to dislocation | Still contained after 20 steps "
          "| Still contained after 60 steps |")
        w("|---|---|---|---|---|---|")
        for arm, k in sv["kaplan_meier"].items():
            lab = a["rules"].get(arm, {}).get("label", _nice(arm))
            w(f"| {lab} | {k['n']} | {k['events']} | "
              f"{'not reached' if k['median'] is None else _f(k['median'], 0)} | {_f(k['survival_at_20'])} "
              f"| {_f(k['survival_at_60'])} |")
        w("")
        cx = sv.get("cox")
        if cx:
            w("| Covariate | Hazard ratio | 95% interval |")
            w("|---|---|---|")
            for n in cx["covariates"]:
                lab = a["rules"].get(n, {}).get("label", _nice(n))
                lo, hi = cx["hr_ci"][n]
                w(f"| {lab} | {_f(cx['hazard_ratio'][n])} | {_f(lo)} to {_f(hi)} |")
            w("")
            w(f"Each run is at risk from the shock; the event is the first step at which the drawdown "
              f"from the pre shock level exceeds {_f(sv['threshold'])}, and runs that never dislocate "
              f"are censored at the horizon. The Kaplan Meier rows read the probability of no "
              f"dislocation yet. The Cox model ({cx['n']} runs, {cx['events']} events, "
              f"{'converged' if cx['converged'] else 'not converged'}) takes the untreated market as "
              f"the reference: a hazard ratio below one means the rule delays or prevents dislocation, "
              f"and the share and correlation rows give the hazard multiplier per standard deviation of each. "
              f"Proportional hazards is an assumption here, not a finding.")
            w("")
        sa = sv.get("sentinel_alerts") or {}
        if sa:
            w("| Sentinel | Alerts before the shock | Pre emption probability | Median alert step |")
            w("|---|---|---|---|")
            for n, v in sa.items():
                w(f"| {_lab(n)} | {v['alerts_before_shock']} of {v['n']} | {_f(v['pre_emption_probability'])} "
                  f"| {'not reached' if v['median_alert_step'] is None else _f(v['median_alert_step'], 0)} |")
            w("")
    rr = a.get("rules") or {}
    if rr and any(v.get("es_post_shock_dd_treated") is not None for v in rr.values()):
        w("## Tail risk of the treated market")
        w("")
        lvl = next(v["es_level"] for v in rr.values() if v.get("es_level") is not None)
        w("| Rule | Expected shortfall of post shock drawdown, untreated | Treated | Tail containment |")
        w("|---|---|---|---|")
        for n, v in rr.items():
            eu, et = v.get("es_post_shock_dd_untreated"), v.get("es_post_shock_dd_treated")
            w(f"| {v.get('label', n)} | {_f(eu, 3)} | {_f(et, 3)} | {_f(v.get('tail_containment'))} |")
        w("")
        w(f"Expected shortfall at level {_f(lvl)} is the mean drawdown of the worst "
          f"{_pct(1 - lvl)} of herding scenarios. Unlike the mean, it reads the tail a supervisor is "
          f"paid to worry about, and unlike value at risk it is coherent. A rule whose mean containment "
          f"looks good but whose tail containment is poor is spending its halts on the easy scenarios.")
        w("")
    if "responsive_ladder" in rr:
        w("## Enforcement ladder")
        w("")
        v = rr["responsive_ladder"]
        w(f"The responsive enforcement ladder escalates from a targeted throttle to kill functionality "
          f"to a market wide halt only when the lower rung fails, and steps down on recovery, after the "
          f"enforcement pyramid of Ayres and Braithwaite. On this battery it contained "
          f"{_f(v['containment'])} of the post shock drawdown with a false halt rate of "
          f"{_f(v['false_halt_rate'])} and engaged before the shock in {_pct(v['pre_shock_engagement'])} "
          f"of herding scenarios. Because it is sentinel informed, its burden by class carries the "
          f"sentinel's targeting error.")
        w("")
    w("## Impact assessment summary")
    w("")
    w("Set out in the structure of the UK Better Regulation Framework (rationale for intervention, "
      "options considered, costs and benefits, monitoring and evaluation), so the briefing can feed an "
      "impact assessment rather than sit beside one.")
    w("")
    w("1. Rationale: agents built on shared foundation models can herd, and the tools meant to detect "
      "and interrupt herding are today certified on aggregate fidelity, a criterion this battery shows "
      "can invert the decision ranking.")
    w("2. Options: the surveillance sentinels and intervention rules compared above, including doing "
      "nothing (the untreated market).")
    w("3. Costs and benefits: decision accuracy, false alerts and false halts, burden by participant "
      "class, containment in the mean and in the tail, all with intervals; the cost frontier states on "
      "which declared weight each option is optimal.")
    w("4. Monitoring and evaluation: the ledger and evidence pack make every figure replayable; the "
      "held out family, the conformal guarantee and the red team are the review that a certified tool "
      "should pass again after deployment.")
    w("")
    rp = a.get("reports")
    if rp:
        w("## What the central bank and regulator reports ask for, and what this run answers")
        w("")
        w("| | Need flagged | Source | Status | Evidence in this run |")
        w("|---|---|---|---|---|")
        for n in rp["needs"]:
            w(f"| {n['id']} | {n['need']} | {n['source']} | {n['status']} | {n['evidence']} |")
        w("")
        ind = rp["indicators"]
        tc, ch, mp = ind["third_party_concentration"], ind["correlation_and_herding"], ind["model_performance"]
        w(f"Of the {len(rp['needs'])} needs, {rp['n_answered']} are answered by this run, {rp['n_partial']} in part "
          f"and {rp['n_open']} not on this battery. Indicators in the families the IOSCO toolkit and the FSB "
          f"monitoring report ask for: adoption share of AI driven agents up to "
          f"{_f(ind['adoption']['ai_agent_share_max'])}, vendor Herfindahl index up to {_f(tc['vendor_hhi_max'], 3)} "
          f"with a top vendor share of {_f(tc['top_vendor_share_max'])} (substitutability proxy "
          f"{_f(tc['substitutability_proxy'])}), herd against quiet post shock drawdown {_f(ch['herd_post_shock_dd'], 3)} "
          f"against {_f(ch['quiet_post_shock_dd'], 3)}, persona output jump {_f(ind['input_output_sensitivity']['persona_max_action_jump'])} "
          f"for a one bucket change of state, expected shortfall of the dislocation "
          f"{_f(ind['incidents']['expected_shortfall_untreated'], 3)}. The held out drift of decision F1, the "
          f"sandbox analogue of model drift, is largest for "
          f"{_lab(max(mp['held_out_drift'], key=lambda k: abs(mp['held_out_drift'][k]))) if mp['held_out_drift'] else 'n/a'}. "
          f"Five indicators in those families need firm reporting and cannot be read from a synthetic run; they "
          f"are listed in the artefacts as the data gaps register.")
        w("")
        w("| Rule | Human oversight as deployed in HSL | Note |")
        w("|---|---|---|")
        for rn, rv in (a.get("rules") or {}).items():
            ho = rv.get("human_oversight") or {}
            w(f"| {rv.get('label', rn)} | {ho.get('level', '').replace('_', ' ')} | {ho.get('note', '')} |")
        w("")
    rk = a.get("risk")
    if rk and rk.get("untreated"):
        u = rk["untreated"]
        w("## Tail risk of the dislocation: value at risk, expected shortfall and the extreme value tail")
        w("")
        w(f"Over the {rk['n_scenarios']} herding scenarios the untreated post shock drawdown has mean "
          f"{_f(u['mean'], 3)}, value at risk {_f(u['var'], 3)} and expected shortfall {_f(u['es'], 3)} at "
          f"level {_f(rk['alpha'])}. "
          + (f"A generalised Pareto fit to the {u['gpd']['n_excess']} excesses over {_f(u['gpd']['threshold'], 3)} "
             f"has shape {_f(u['gpd']['shape'])} and gives a probability of {_f(u['gpd']['tail_prob'], 3)} of a "
             f"drawdown beyond {_f(u['gpd']['probe'], 3)} (empirical share {_f(u['gpd']['empirical_prob_above_probe'], 3)})."
             if u["gpd"].get("shape") is not None else
             "Too few excesses over the threshold for an extreme value fit on this battery."))
        w("")
        w("| Rule | ES treated | ES reduction | 95% interval | Mean reduction |")
        w("|---|---|---|---|---|")
        for n in rk["ranking_by_es_reduction"]:
            v = rk["rules"][n]
            w(f"| {a['rules'].get(n, {}).get('label', n)} | {_f(v['es_treated'], 3)} | {_f(v['es_reduction'])} "
              f"| {_f(v['es_reduction_ci'][0])} to {_f(v['es_reduction_ci'][1])} | {_f(v['mean_reduction'])} |")
        w("")
        w("Expected shortfall is the mean of the worst dislocations, the ones a supervisor is paid to prevent, "
          "and unlike value at risk it is coherent (McNeil, Frey and Embrechts 2015). A rule whose mean "
          "reduction exceeds its ES reduction contains the typical herd better than the severe one. The "
          "extreme value fit is descriptive at this sample size; the number of excesses is stated beside it.")
        w("")
    gm = a.get("game")
    if gm:
        w("## The certification as a game against the evader")
        w("")
        w(f"Rows are sentinels, columns the {gm['n_trials']} evasions found by the red team that still "
          f"dislocated the market, entries decision F1. The maximin sentinel is {_lab(gm['maximin_pure'])} "
          f"with a guaranteed F1 of {_f(gm['maximin_value'])} against the worst evasion; the adversary's "
          f"best pure counter holds every sentinel to at most {_f(gm['minimax_value'])}. A supervisor who "
          f"randomised which sentinel is armed could guarantee {_f(gm['mixed_value'])} "
          + ("by mixing " + ", ".join(f"{_lab(k)} {_f(v)}" for k, v in gm["mixture"].items())
             if len(gm["mixture"]) > 1 else f"with {_lab(next(iter(gm['mixture'])))} alone")
          + f"; the value of unpredictability is {_f(gm['value_of_mixing'])}"
          + (" and the game has a saddle point." if gm["saddle_point"] else "."))
        w("")
    lp = a.get("learned_policy")
    if lp:
        w("## A learned market wide policy, and what logged data could have told a supervisor")
        w("")
        w(f"A tabular model of the market's response to intervention was fitted from {lp['n_logged_trajectories']} "
          f"runs logged under an epsilon soft behaviour policy ({lp['n_logged_steps']} steps, "
          f"{_pct(lp['model_coverage'])} of state action pairs observed) and solved by value iteration with "
          f"a halt costing {_f(lp['costs']['halt_per_step'], 3)} and a throttle {_f(lp['costs']['throttle_per_step'], 3)} "
          f"per step. The learned policy halts in {_pct(lp['action_share']['halt'])} of states and throttles in "
          f"{_pct(lp['action_share']['throttle'])}; it is scored as a rule in the intervention monitor and is "
          f"advisory.")
        w("")
        w("| Policy | Importance sampling | Doubly robust | Model based | Simulated on policy |")
        w("|---|---|---|---|---|")
        for n, v in lp["ope"].items():
            lab = a["rules"].get(n, {}).get("label", n.replace("_", " "))
            w(f"| {lab} | {_f(v['pdis'], 3)} | {_f(v['dr'], 3)} | {_f(v.get('model'), 3)} | {_f(v['on_policy'], 3)} |")
        w("")
        mae = lp.get("mean_abs_error") or {}
        names = {"pdis": "per decision importance sampling", "dr": "the doubly robust estimator",
                 "model": "the fitted model's value"}
        best = lp.get("best_estimator", "model")
        w(f"Off policy evaluation answers the pilot's question: what would this rule have been worth, using "
          f"only trajectories logged under another policy. On this battery the mean absolute error against the "
          f"simulated value is {_f(mae.get('pdis'), 3)} for importance sampling, {_f(mae.get('dr'), 3)} for the "
          f"doubly robust estimator and {_f(mae.get('model'), 3)} for the fitted model; {names[best]} comes "
          f"closest. Importance sampling truncates as soon as the logged action differs from the target's and "
          f"the doubly robust recursion compounds model error over a long horizon, so neither can be trusted "
          f"on its own at this sample size. The sandbox can measure the error because it can simulate the "
          f"truth; a pilot cannot, which is why this audit belongs before one.")
        w("")
    ap = a.get("appraisal")
    if ap:
        w("## Regulatory options appraisal and the enforcement ladder")
        w("")
        w(f"Baseline: {ap['baseline']}. Non regulatory option: {ap['non_regulatory_option']}. Tests: containment "
          f"of at least {_f(ap['containment_target'])}, false halts within {_f(ap['false_halt_budget'])}, and for "
          f"targeted rules a burden on agents that were not destabilising of at most {_f(ap['proportionality_limit'])} "
          f"of the burden on those that were.")
        w("")
        w("| Tier | Rule | Instrument | Containment | False halts | ES reduction | Burden ratio | Passes | Legal basis |")
        w("|---|---|---|---|---|---|---|---|---|")
        for o in ap["options"]:
            w(f"| {o['tier']} {o['tier_label']} | {o['label']} | {o['instrument']} | {_f(o['containment'])} "
              f"| {_f(o['false_halt_rate'])} | {_f(o['es_reduction'])} | {_f(o['burden_ratio_others_to_destabilising'])} "
              f"| {'all' if o['passes_all'] else ', '.join(k for k, v in o['passes'].items() if not v) + ' failed'} "
              f"| {o['legal_basis']} |")
        w("")
        rec = ap.get("recommended")
        w((f"Responsive regulation recommends tier {rec['tier']} ({rec['tier_label']}): {rec['label']}, "
           f"{rec['instrument']}, basis {rec['legal_basis']}."
           if rec else "No rule passes all three tests on this battery; the recommendation is to monitor and warn "
                       "and to recalibrate the targeted rules before any is adopted.")
          + f" {ap['n_eligible']} rules are eligible. The principle is {ap['principle']}. The legal basis "
            f"column is a pointer to the power a UK or EU authority would name, not legal advice.")
        w("")
    dt = a.get("data")
    if dt and dt.get("datasets"):
        w("## Observed data brought to the sandbox")
        w("")
        w("| Dataset | Classification | Rows | Source | In the evidence pack | Hash |")
        w("|---|---|---|---|---|---|")
        for e in dt["datasets"]:
            s_ = e["summary"]
            w(f"| {s_['name']} | {s_['classification']} | {s_['n_rows']} | {s_.get('source', 'upload')} | "
              f"{'yes' if s_['packable'] else 'hashes and aggregates only'} | {s_['sha256'][:16]} |")
        w("")
        for e in dt["datasets"]:
            an = e.get("anchoring")
            if an and an.get("ok"):
                w(f"Anchoring of {e['summary']['name']} against the battery's quiet family: "
                  + "; ".join(f"{k.replace('_', ' ')} {_f(an['observed'][k], 4)} against {_f(an['battery_quiet'][k], 4)} "
                              f"(ratio {_f(an['ratios'][k])}, {'within' if an['within_band'][k] else 'outside'} the band)"
                              for k in an["ratios"])
                  + f". {an['n_within']} of {an['n_compared']} statistics fall within a factor of two.")
                w("")
            ow = e.get("observed_window") or {}
            if ow.get("ok"):
                w(f"Observed window of {e['summary']['name']}: {ow['n_participants']} participants over "
                  f"{ow['n_steps']} steps. " + "; ".join(
                      f"{_lab(k)} {'alerted' if v['alerted'] else 'did not alert'}, peak stress {_f(v['peak_stress'])}, "
                      f"flagged {v['n_flagged']} ({_f(v['share_flagged'])} of participants)"
                      for k, v in ow["sentinels"].items())
                  + f". There is no ground truth for observed data, so these are counts only; no participant is "
                    f"named and counts below {ow['k_anon']} are withheld.")
                w("")
        w("Every dataset passed one quarantine: size and type limits, text only, a schema check, a spreadsheet "
          "formula check, a personal identifier scan that refuses rather than redacts, and a classification "
          "with a no write down rule. Held out empirical scenarios take their shock and volatility from the "
          "observed data" + (" and are in this battery." if dt.get("empirical_family_present") else "."))
        w("")
        cal_rows = [(e["summary"]["name"], e.get("calibration")) for e in dt["datasets"] if e.get("calibration")]
        if cal_rows:
            w("| Dataset | Volatility | Shock | Impact | Momentum window | Fundamentalists | Vendor share and correlation | Split | Participants |")
            w("|---|---|---|---|---|---|---|---|---|")
            for name, cal in cal_rows:
                p, g = cal["params"], cal["diagnostics"]
                w(f"| {name} | {_f(p['sigma'], 4)} | {_f(p['shock_size'], 3)} | {_f(p['kappa'], 4)} | {p['momentum_window']} "
                  f"| {_f(p['frac_fundamental'])} | {', '.join(f'{x:.2f} at {r:.2f}' for x, r in zip(p['vendor_shares'], p['vendor_rhos']))} "
                  f"| {g.get('vendor_split_source', '')} | {g['n_participants'] or 'none'} |")
            w("")
            notes = [n for _, cal in cal_rows for n in (cal["clamped"] + cal["diagnostics"].get("notes", []))]
            w("Each dataset was used to calibrate the simulator: volatility from the observed returns, the shock from "
              "the tail of rolling window drawdowns, price impact from the regression of returns on aggregate flow, the "
              "momentum window from the past window that best predicts the next return, the fundamentalist fraction "
              "from the observed speed of reversion, and the vendor split from the vendor column where the data "
              "carries one (observed) or from communities in the flow correlation matrix (inferred: a correlated "
              "group may be a shared model, a shared information source or a shared hedging need). Two families "
              "followed: a calibrated synthetic market with these parameters and the generator's "
              "ground truth, and a hybrid market in which the observed return path is the news and the synthetic "
              "agents respond to it."
              + (" Clamps and notes: " + "; ".join(notes) + "." if notes else ""))
            w("")
        cs = dt.get("calibration_shift")
        if cs:
            if cs.get("positives_present"):
                w(f"Calibration shift. The rank correlation between the decision ranking on the demonstration herds "
                  f"and on the calibrated families is {_f(cs['tau'])}; rank one is "
                  f"{'preserved' if cs['rank_one_preserved'] else 'not preserved'} "
                  f"({_lab(cs['ranking_demonstration'][0])} on the demonstration herds, "
                  f"{_lab(cs['ranking_calibrated'][0])} on the calibrated families). This is the truth dependence "
                  f"question asked of the authority's own structure.")
            else:
                w("Calibration shift. The calibrated structure sits below the destabilising thresholds, so its "
                  "families carry no positives; they test false alerts and containment, not localisation.")
            w("")
    sec = a.get("security")
    if sec:
        w("## Security posture at release")
        w("")
        w(f"{sec['n_pass']} controls pass, {sec['n_warn']} warn, {sec['n_fail']} fail. "
          + ("Warnings: " + "; ".join(f"{i['control']} ({i['detail']})" for i in sec["items"]
                                      if i["status"] == "warn") + ". " if sec["n_warn"] else "")
          + "Each control applies a chapter of Anderson's Security Engineering; the mapping is in the "
            "security framework document of the evidence pack. A failing control blocks release.")
        w("")
    bt = a.get("backtest")
    if bt:
        w("## Backtests: observed episodes and the certification procedure")
        w("")
        wf = bt.get("walk_forward")
        if wf:
            w(f"Walk forward. Over {wf['n_folds']} folds of the calibration scenarios, the tool certified on the "
              f"earlier folds was scored on the next: mean regret against the best tool on the test fold "
              f"{_f(wf['mean_regret'])}, worst {_f(wf['max_regret'])}, and the certified tool was still the best on "
              f"{_pct(wf['p_still_best'])} of test folds. "
              + "; ".join(f"fold {f['fold']}: certified {_lab(f['certified'])} at {_f(f['f1_certified_test'])} against "
                          f"{_lab(f['best_on_test'])} at {_f(f['f1_best_test'])}" for f in wf["folds"]) + ".")
            w("")
        for d in bt.get("datasets", []):
            if not d["episodes"]:
                w(f"{d['name']}: no stress episode found (no window drawdown above the threshold and no event column).")
                w("")
                continue
            w(f"{d['name']}: {len(d['episodes'])} episode{'s' if len(d['episodes']) != 1 else ''} ("
              + "; ".join(f"{_nice(e['name'])} drawdown {_f(e['drawdown'], 3)} at step {e['event_step']}, {e['source']}"
                          for e in d["episodes"]) + ").")
            w("")
            bs = d.get("sentinels")
            if bs:
                w("| Sentinel | Episodes detected | Median lead (steps) | Alerts per 100 quiet steps | Recall on labelled positives |")
                w("|---|---|---|---|---|")
                for n, v in bs["sentinels"].items():
                    if v.get("skipped"):
                        w(f"| {_lab(n)} | {v['skipped']} | | | |")
                    else:
                        w(f"| {_lab(n)} | {_f(v['detection_rate'])} | {_f(v['median_lead'], 0)} | "
                          f"{_f(v['quiet_alerts_per_100_steps'])} | {_f(v['mean_recall_on_labelled'])} |")
                w("")
                w("This is a timing and workload backtest. The tape says when a sentinel alerted relative to the "
                  "observed event and how often it alerts in quiet stretches; it does not say who the destabilising "
                  "participants were, so precision is not reported"
                  + (" and recall is on the labelled positives only." if bs["labelled_positives"] else
                     " and no participant labels were supplied."))
                w("")
            br = d.get("rules")
            if br and br.get("rules"):
                w("| Rule | Mean containment over episodes | Worst episode |")
                w("|---|---|---|")
                for n, v in br["rules"].items():
                    w(f"| {a['rules'].get(n, {}).get('label', n)} | {_f(v['mean_containment'])} | {_f(v['worst_containment'])} |")
                w("")
                w("Each episode was replayed as a hybrid market: the observed return path as the news, the "
                  "calibrated synthetic population responding, every rule applied; containment is against the "
                  "untreated hybrid run of the same episode.")
                w("")
    rl = a.get("rule_library") or {}
    if rl:
        w("## Rule library")
        w("")
        w("| Rule | Jurisdiction | Modelled on |")
        w("|---|---|---|")
        for n, v in rl.items():
            w(f"| {a['rules'].get(n, {}).get('label', n)} | {v['jurisdiction']} | {v['basis']} |")
        w("")
        w("Durations are simulation steps and parameters are illustrative; the library lets one battery "
          "compare regimes, it does not reproduce any venue's calibration.")
        w("")
    return L


def draft_briefing(a, critic, approvals, run_id=""):
    """`approvals`: dict with keys preparer, gate1 (dict actor, ts), gate2
    (dict actor, ts) as available."""
    s, g, r = a["sentinels"], a["decision_gap"], a["rules"]
    gm, gb, gbm = a["decision_gap_moments"], a["decision_gap_bootstrap"], a["decision_gap_bootstrap_moments"]
    aut, hold = a.get("autonomy", {}), a.get("sentinels_holdout", {})
    prov, bat = a.get("provenance", {}), a.get("battery", {})
    L = []
    w = L.append
    w("# HSL supervisory briefing")
    w("")
    w(f"**Run.** {run_id or 'n/a'}")
    w("")
    w(f"**Policy question.** {a['question']}")
    w("")
    pr = approvals.get("preparer_role")
    w(f"**Prepared by.** {approvals.get('preparer') or 'n/a'}" + (f" ({pr})" if pr else ""))
    g1, g2 = approvals.get("gate1") or {}, approvals.get("gate2") or {}
    def _reg(g):
        m = g.get("register") or {}
        if m and m.get("dev_mode"):
            return "; DEV MODE identity, not a regulated person"
        return (f"; on the register as {m.get('function')} at {m.get('firm')}, reference {m.get('irn')}, "
                f"checked {str(m.get('checked_at', ''))[:10]}") if m else ""
    w(f"**Gate 1 (battery sign off).** {g1.get('actor', 'n/a')}"
      + (f" ({g1['role']})" if g1.get("role") else "") + f" at {g1.get('ts', 'n/a')}" + _reg(g1))
    w(f"**Gate 2 (release).** {g2.get('actor', 'n/a')}"
      + (f" ({g2['role']})" if g2.get("role") else "") + f" at {g2.get('ts', 'n/a')}" + _reg(g2))
    w(f"**Critic verification.** {'PASSED' if critic['ok'] else 'FAILED'} "
      f"({critic['n_checks']} independent checks against the run artefacts and the ledger).")
    w("")
    da = a.get("direct_answer")
    qi = a.get("question_interpretation") or {}
    if da and (da.get("tools") or da.get("family_present")):
        w("## Direct answer to the question")
        w("")
        if da.get("family_present"):
            pr = da.get("params") or {}
            w("The case the question names was added to the battery as its own family ("
              + ", ".join(f"{k.replace('_', ' ')} {_f(v) if isinstance(v, float) else v}" for k, v in pr.items())
              + (("; mechanisms " + ", ".join(_nice(m) for m in da.get("mechanisms", []))) if da.get("mechanisms") else "")
              + ") and every figure below for it is measured on that family.")
            w("")
        for t in da["tools"]:
            if t["kind"] == "rule":
                w(f"{t['label']}: containment {_f(t['containment_battery'])} across the herding scenarios"
                  + (f" and {_f(t['containment_question'])} on the question's own family"
                     if t.get("containment_question") is not None else "")
                  + f"; false halt rate {_f(t['false_halt_rate'])}; dislocation probability after treatment "
                  f"{_f(t['crash_prob_treated'])}; human oversight as deployed: "
                  f"{(t.get('human_oversight') or 'n/a').replace('_', ' ')}.")
            else:
                w(f"{t['label']}: decision F1 {_f(t['decision_f1'])} across the herding scenarios"
                  + (f" and {_f(t['decision_f1_question'])} on the question's own family"
                     if t.get("decision_f1_question") is not None else "")
                  + f"; false alert rate {_f(t['false_alert_rate'])}.")
        w("")
        rec = da.get("recommended_rule")
        w(f"The certified sentinel on this battery is {_lab(da['certified'])} "
          f"({(da.get('certification_basis') or 'empirical').replace('_', ' ')} basis)"
          + (f"; the appraisal recommends tier {rec['tier']} ({rec['tier_label']}): {rec['label']}." if rec else
             "; no rule passes every appraisal test on this battery."))
        if qi.get("unmatched"):
            w("")
            w("Not interpreted from the question: " + "; ".join(f'"{u}"' for u in qi["unmatched"][:4])
              + ". A configured model plans further families from such phrases; without one they are recorded and "
                "the demonstration battery stands.")
        w("")
    w("## Headline")
    w("")
    top_dec, top_fid = g["decision_ranking"][0], g["fidelity_ranking"][0]
    grade = s[top_dec]["grade"]["decision_f1"]
    if g["decision_gap"] >= 0.5:
        w(f"The tool that best reproduces aggregate market statistics ({_lab(top_fid)}, "
          f"fidelity {_f(s[top_fid]['aggregate_fidelity'])}) is not the tool that best "
          f"identifies destabilising clusters ({_lab(top_dec)}, decision F1 "
          f"{_f(s[top_dec]['decision_f1'])}, 95% interval {_ci(s[top_dec]['ci']['decision_f1'])}, "
          f"grade {grade}). Certification on aggregate fidelity alone would select "
          f"the wrong surveillance tool for the supervisory decision in this battery.")
    else:
        w(f"Rankings are broadly consistent in this battery (decision gap "
          f"{_f(g['decision_gap'])}). Aggregate validation would not have been misleading here. "
          f"The best tool by decision accuracy is {_lab(top_dec)} (F1 {_f(s[top_dec]['decision_f1'])}, "
          f"grade {grade}).")
    w("")
    cert = a.get("certified") or best_certifiable(s)
    basis = a.get("certification_basis", "empirical false alert rate")
    cf0 = next(iter((a.get("conformal") or {}).values()), {})
    fa_top = s[top_dec].get("false_alert_rate")
    if basis == "conformal":
        w(f"Certification. {_lab(cert)} is conformally certified at level {_f(cf0.get('alpha'))} given "
          f"{cf0.get('n_calibration')} exchangeable calibration scenarios: its alert threshold is set by the "
          f"conformal rule, so the false alert probability on a new quiet scenario like those is at most "
          f"{_f(cf0.get('alpha'))} by construction, and among the sentinels with that guarantee and conformal "
          f"power of at least 0.50 it has the highest decision F1 ({_f(s[cert]['decision_f1'])}). "
          + (f"Its empirical quiet alert rate is {_f(s[cert].get('false_alert_rate'))}; a point estimate near "
             f"the budget is exactly where the finite sample bound, not the estimate, should adjudicate. "
             if s[cert].get("false_alert_rate") is not None else "")
          + (f"{_lab(top_dec)} has the higher decision F1 ({_f(s[top_dec]['decision_f1'])}) but does not reach "
             f"conformal power 0.50, so it is not certified." if cert != top_dec else ""))
        w("")
    elif not s[top_dec].get("within_budget", True):
        w(f"Cost side. {_lab(top_dec)} exceeds the declared false alert budget "
          f"({_f(fa_top)} against {_f(s[top_dec]['false_alert_budget'])} on quiet markets), so it is "
          f"not certifiable on this battery despite its localisation. "
          + (f"The best tool within budget by the empirical rate is {_lab(cert)} (decision F1 "
             f"{_f(s[cert]['decision_f1'])}, false alert rate {_f(s[cert]['false_alert_rate'])}); no sentinel "
             f"carries a conformal guarantee on this battery." if cert else "No candidate is within budget."))
        w("")
    elif cert and cert != top_dec:
        w(f"Cost side. The best tool within the false alert budget by the empirical rate is {_lab(cert)}.")
        w("")
    ws = gb.get("winner_stability")
    if ws is not None and gb.get("p_top_decision"):
        ptop = gb["p_top_decision"]; ppick = gb.get("p_within_budget_pick") or {}
        lead = max(ptop, key=ptop.get)
        w(f"Winner stability. Over the {gb['B']} scenario resamples, {_lab(lead)} is the top tool by decision "
          f"F1 in {_pct(ptop[lead])} of them"
          + (f" and {_lab(cert)} is the within budget pick in {_pct(ppick.get(cert))} of them"
             if ppick.get(cert) is not None else "")
          + ". A winner that changes with the resample is a reason to certify the procedure, not the tool; "
            "the number says how often this battery's answer would repeat.")
        w("")
    w(f"Decision gap {_f(g['decision_gap'])} (Kendall tau {g['kendall_tau']:+.2f}) under the "
      f"conventional fidelity construct; {_f(gm['decision_gap'])} (tau {gm['kendall_tau']:+.2f}) "
      f"under the multi moment construct. Across {gb['B']} scenario resamples the rankings invert "
      f"with probability {_f(gb['p_inversion'])} (conventional) and {_f(gbm['p_inversion'])} "
      f"(multi moment). With {g['n_tools']} tools tau takes few values, so the resampled "
      f"probability is the number to quote.")
    w("")
    w("## Surveillance candidates: aggregate fidelity versus decision accuracy")
    w("")
    w("| Sentinel | Fidelity (vol) | Fidelity (moments) | Decision F1 | 95% interval | Grade "
      "| Precision | Recall | Alert lead vs shock | False alert rate |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for n, v in s.items():
        w(f"| {_lab(n)} | {_f(v['aggregate_fidelity'])} | {_f(v['fidelity_moments'])} "
          f"| {_f(v['decision_f1'])} | {_ci(v['ci']['decision_f1'])} | {v['grade']['decision_f1']} "
          f"| {_f(v['precision'])} | {_f(v['recall'])} | {_f(v['mean_lead_time'], 0)} "
          f"| {_f(v['false_alert_rate'])} |")
    w("")
    w(f"Ranking by aggregate fidelity: {' > '.join(_lab(x) for x in g['fidelity_ranking'])}.")
    w("")
    w(f"Ranking by decision accuracy: {' > '.join(_lab(x) for x in g['decision_ranking'])}.")
    w("")
    w(f"Fidelity constructs. Conventional: {FIDELITY_CONSTRUCTS['vol']}. "
      f"Multi moment: {FIDELITY_CONSTRUCTS['moments']}.")
    w("")
    if any(n in s for n in ("imbalance", "endogeneity", "lead_lag")):
        w("Herding versus noise. Three candidates ask whether activity is coordinated and self "
          "reinforcing rather than merely loud: the buy sell imbalance herding measure (share of agents "
          "on the majority side in excess of independent decisions), the Hawkes branching ratio (share "
          "of large moves generated by earlier moves rather than news) and the lead lag ignition sentinel "
          "(a small cluster whose orders lead the crowd's next orders, and the crowd that follows).")
        w("")
    w("Lead time is measured from the sentinel's first alert to the shock. A positive lead "
      "means the structural vulnerability was flagged before the shock landed; it is a "
      "measure of when the cluster became visible, not a forecast of the shock.")
    w("")
    # generalisation
    w("## Generalisation: held out, adversarial and emergent families")
    w("")
    if hold:
        w("| Sentinel | Decision F1 (calibration battery) | Decision F1 (held out) | "
          "False alert rate (held out) |")
        w("|---|---|---|---|")
        for n, v in hold.items():
            w(f"| {_lab(n)} | {_f(s[n]['decision_f1'])} | {_f(v['decision_f1'])} "
              f"| {_f(v['false_alert_rate'])} |")
        w("")
        gh = a.get("decision_gap_holdout")
        if gh:
            w(f"On the held out family the decision ranking is "
              f"{' > '.join(_lab(x) for x in gh['decision_ranking'])} and the decision gap is "
              f"{_f(gh['decision_gap'])}. Held out scenarios use a different population, shock "
              f"time and impact coefficient and were never used to set any threshold.")
            w("")
    fams = sorted({f for v in s.values() for f in v.get("by_family", {})})
    if fams:
        w("| Sentinel | " + " | ".join(f"F1 {f.replace('_', ' ')}" for f in fams) + " |")
        w("|---|" + "---|" * len(fams))
        for n, v in s.items():
            w(f"| {_lab(n)} | " + " | ".join(_f(v['by_family'].get(f, {}).get('decision_f1')) for f in fams) + " |")
        w("")
    if "evader" in fams:
        best = max(s.items(), key=lambda kv: kv[1]["by_family"].get("evader", {}).get("decision_f1", 0))
        w(f"Adversarial evaders. The dominant vendor rotates three trading cohorts so pairwise "
          f"flow correlation stays low while its aggregate impact is unchanged. The best decision F1 "
          f"on that family is {_f(best[1]['by_family']['evader']['decision_f1'])} ({_lab(best[0])}). "
          f"A sentinel certified on the parametric herds alone would not have revealed this.")
        w("")
    if a.get("rl_emergence"):
        e = a["rl_emergence"]
        w(f"Emergent herding. Independently trained RL traders (Double Q learning, SARSA(lambda) "
          f"with function approximation and advantage actor critic) converged to near identical "
          f"momentum policies: policy convergence {_f(e['policy_convergence'])}, momentum slope "
          f"{_f(e['momentum_slope'])}. No correlation was imposed. Per sentinel decision F1 on the "
          f"emergent herd: " + ", ".join(f"{_lab(k)} {_f(v)}" for k, v in e.get("sentinel_f1_on_rl_herd", {}).items()) + ".")
        w("")
    # interventions
    w("## Intervention rules: containment on the same battery")
    w("")
    w("| Rule | Post shock drawdown untreated | Post shock drawdown treated | Containment "
      "| 95% interval | Grade | Trough containment | Dislocation probability before, after "
      "| False halt rate (quiet) | Engaged before the shock | Burden on non destabilising agents "
      "| Burden on destabilising agents |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n, v in r.items():
        b = v.get("burden_by_class", {})
        w(f"| {v.get('label', n)} | {_f(v['mean_post_shock_dd_untreated'], 3)} "
          f"| {_f(v['mean_post_shock_dd_treated'], 3)} | {_f(v['containment'])} "
          f"| {_ci(v['containment_ci'])} | {v['grade']} | {_f(v.get('containment_trough'))} "
          f"| {_f(v['crash_prob_untreated'])}, {_f(v['crash_prob_treated'])} "
          f"| {_f(v['false_halt_rate'])} | {_pct(v.get('pre_shock_engagement'))} "
          f"| {_f(b.get('non_destabilising'))} | {_f(b.get('destabilising'))} |")
    w("")
    tgt = [v for v in r.values() if v.get("targeted")]
    hurt = [v for v in tgt if (v.get("burden_by_class", {}).get("fundamentalist") or 0)
            >= 0.5 * max(1e-9, v.get("burden_by_class", {}).get("destabilising") or 0)]
    if hurt:
        v = hurt[0]
        b = v["burden_by_class"]
        w(f"Targeting cost. The targeted rules suppressed fundamentalists at "
          f"{_f(b.get('fundamentalist'))}, against {_f(b.get('destabilising'))} for the destabilising "
          f"cluster. Fundamentalists trade on the same signal and are therefore as correlated with "
          f"one another as the herd, so a correlation based flag cannot tell a stabilising correlated "
          f"group from a destabilising one. Suppressing the mean reverting agents removes the force "
          f"that would otherwise close the dislocation, which is why disconnecting flagged agents "
          f"can deepen the drawdown rather than contain it.")
        w("")
    eng = [v for v in r.values() if (v.get("pre_shock_engagement") or 0) > 0.5]
    if eng:
        w("Every rule that engaged before the shock did so on the herd's own pre shock swings, not "
          "on the shock. A rule tripped by endogenous herd volatility is intervening on the "
          "structure itself; whether that is desirable is a policy choice the briefing does not make.")
        w("")
    w(f"Containment is one minus treated over untreated mean post shock drawdown. Trough "
      f"containment uses the depth of the post shock trough relative to the pre shock price "
      f"instead. A dislocation "
      f"is a post shock drawdown above {_f(list(r.values())[0]['dislocation_threshold']) if r else 'n/a'}. "
      f"Burden is the share of intended order flow suppressed over the {BURDEN_WINDOW} steps after the shock; "
      f"a targeted rule should load it on destabilising agents and spare the rest. Targeted rules act "
      f"only on flags the sentinel had issued by that step (no lookahead).")
    w("")
    tw = a.get("three_worlds", {})
    if tw:
        d = tw.get("post_shock_dd", {})
        w(f"Same shock, three worlds: post shock drawdown {_f(d.get('quiet'), 3)} in the quiet market, "
          f"{_f(d.get('herd'), 3)} with a 40% single vendor herd and {_f(d.get('treated'), 3)} with the "
          f"sentinel informed throttle. The herd market's pre shock volatility is "
          f"{_f(tw.get('pre_shock_vol', {}).get('herd'), 1)} times the exogenous noise scale, against "
          f"{_f(tw.get('pre_shock_vol', {}).get('quiet'), 1)} in the quiet market, so part of the "
          f"herd's instability is endogenous and present before the shock.")
        w("")
    # autonomy
    if aut:
        w("## Autonomy gate: how much execution the evidence can back")
        w("")
        w("| Sentinel | Backed in sample | Auto clear | Auto throttle | Localisation lift | "
          "Backed (leave one out) | Out of sample claims |")
        w("|---|---|---|---|---|---|---|")
        for n, v in aut.items():
            thr = _pct(v["throttle"]) if v["throttle_ok"] else "withdrawn"
            w(f"| {_lab(n)} | {_pct(v['breadth'])} | {_pct(v['clear'])} | {thr} "
              f"| {_f(v['lift'])} (bar {_f(v['lift_bar'])}) | {_pct(v['loo']['backed'])} "
              f"| {v['loo']['claims']} of {len(a['battery']['seeds']) - a['battery']['n_holdout']} "
              f"({_pct(v['loo']['claim_rate'])}) |")
        w("")
        w("Below the low gate the system stands behind no intervention; above the high gate it may "
          "trigger the targeted throttle; the band between escalates to the named supervisor. The "
          "throttle is withdrawn, not narrowed, when a tool's localisation cannot beat the flag "
          "everyone baseline by the declared margin. The in sample breadth is fitted on the scored "
          "scenarios and holds by construction. The leave one out columns refit the gates without "
          "each scenario and are the figures to quote.")
        w("")
    L.extend(_v3_sections(a))
    w("## Scope and limitations")
    w("")
    w(f"The battery holds {bat.get('n_scenarios')} scenarios: {bat.get('n_herd')} herding, "
      f"{bat.get('n_quiet')} quiet and {bat.get('n_holdout')} held out. Synthetic markets stylise "
      f"real microstructure. All outputs are comparative rankings of tools and rules on this battery. "
      f"They are not forecasts and do not recommend live intervention. Sentinel and rule thresholds "
      f"were calibrated on the demonstration families; the held out and adversarial rows show where "
      f"that calibration does and does not carry.")
    w("")
    w(GRADE_NOTE)
    w("")
    w("## Provenance")
    w("")
    w(f"HSL {prov.get('hsl_version')}, code fingerprint {str(prov.get('code_fingerprint'))[:16]}, "
      f"battery hash {str(prov.get('battery_hash'))[:16]}, flags for targeted rules from "
      f"{_lab(prov.get('flags_from', ''))}, bootstrap resamples {prov.get('bootstrap_B')}, "
      f"numpy {prov.get('numpy')}, scipy {prov.get('scipy')}.")
    w("")
    w("*All figures are computed from logged simulation artefacts (artefacts.json); the drafting "
      "layer cannot alter them. Every step is recorded in the signed rationale ledger, which any "
      "reviewer can replay with `python -m hsl.ledger verify`.*")
    return "\n".join(L)


def to_html(md_text, title="HSL supervisory briefing"):
    """Minimal markdown to HTML for the printable briefing (headings,
    paragraphs, bold, tables, code spans)."""
    lines = md_text.split("\n")
    out, in_table = [], False
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.strip():
            out.append(f"<p>{_inline(ln)}</p>")
    if in_table:
        out.append("</table>")
    css = ("body{font:14px/1.5 Georgia,serif;color:#111;max-width:980px;margin:32px auto;padding:0 20px}"
           "h1{font-size:22px;border-bottom:2px solid #111;padding-bottom:6px}h2{font-size:16px;margin-top:26px}"
           "table{border-collapse:collapse;font:12px ui-monospace,Menlo,monospace;margin:10px 0}"
           "th,td{border:1px solid #bbb;padding:4px 7px;text-align:left}th{background:#f2f2f2}"
           "code{font:12px ui-monospace,Menlo,monospace;background:#f2f2f2;padding:1px 3px}"
           "@media print{body{margin:0;max-width:none}}")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html_mod.escape(title)}</title>"
            f"<style>{css}</style></head><body>" + "\n".join(out) + "</body></html>")


def _inline(s):
    import re
    s = html_mod.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s
