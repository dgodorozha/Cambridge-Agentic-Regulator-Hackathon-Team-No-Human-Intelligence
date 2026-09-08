"""What the reports ask for, and what a run answers.

The central bank and standard setter reports on AI in markets converge on
a short list of needs. This module holds that list with its sources, the
supervisory indicators the reports ask authorities to monitor, and a
coverage map computed from a run's artefacts: for each need, the evidence
HSL produces, or the honest statement that the sandbox cannot supply it
and firm reporting is required.

Sources (all public; details in REFERENCES.md):
  FSB (2024) The Financial Stability Implications of Artificial Intelligence.
  FSB (2025) Monitoring Adoption of AI and Related Vulnerabilities in the
      Financial Sector: data gaps, taxonomies, indicators of criticality,
      concentration and substitutability of third party providers.
  FSB (2026) Sound Practices for Responsible Adoption of AI, consultation.
  IOSCO (2025) Artificial Intelligence in Capital Markets: Use Cases, Risks
      and Challenges (CR/01/2025).
  IOSCO (2026) Supervisory Toolkit for AI Use in Capital Markets (FR/02/2026):
      risk based supervision, human oversight levels, market risk evidence
      (stress testing, circuit breaker and kill switch policies), third party
      contingency planning, recordkeeping, and the indicators of Table 7.
  Bank of England (2025) Financial Stability in Focus: AI in the financial
      system; Breeden (2026) speech on kill switches.
  IMF (2024) Global Financial Stability Report, chapter 3: AI and capital
      markets (herding, liquidity withdrawal, market concentration).
"""

import numpy as np

from ._common import nice_name as _nice


def _r(v, nd=3):
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) and v == v else "n/a"

# Human oversight levels of IOSCO (2026) Box 2, OECD classification.
OVERSIGHT = {
    "human_in_control": "the system cannot act; a human uses or disregards its output",
    "human_in_the_loop": "the system acts only if a human approves",
    "human_on_the_loop": "the system acts unless a human disapproves",
    "human_out_of_the_loop": "the system acts without human involvement",
}

# Each rule as deployed in HSL, and the level it would need to be live.
RULE_OVERSIGHT = {
    "static_circuit_breaker": ("human_on_the_loop", "venue rule; a supervisor can suspend it"),
    "market_wide_breaker": ("human_on_the_loop", "venue rule with declared levels"),
    "luld_style_band": ("human_out_of_the_loop", "mechanical band; oversight is in calibration"),
    "venue_volatility_halt": ("human_on_the_loop", "venue rule; parameters set by the venue"),
    "responsive_ladder": ("human_on_the_loop", "escalation with a supervisor able to halt escalation"),
    "dynamic_throttle": ("human_in_the_loop", "targeted action on named agents warrants approval"),
    "kill_switch": ("human_in_the_loop", "cancellation for named agents warrants approval"),
    "learned_policy": ("human_in_control", "a learned policy is advisory until validated in a pilot"),
}

NEEDS = [
    {"id": "N1", "need": "Close the data gaps on AI adoption and use; indicators and a common taxonomy",
     "source": "FSB 2024 (recommendation 1); FSB 2025; IOSCO 2026 Table 7"},
    {"id": "N2", "need": "Monitor third party concentration, criticality and substitutability of AI providers",
     "source": "FSB 2025 case study; IOSCO 2026 Table 4; Bank of England 2025"},
    {"id": "N3", "need": "Detect herding, correlated positioning and collusion between AI agents",
     "source": "IOSCO 2025 and 2026 (market risks); Bank of England 2025; IMF 2024"},
    {"id": "N4", "need": "Test AI systems in an environment segregated from production, in stressed and "
                         "unstressed conditions", "source": "IOSCO 2021 Measure 2, reaffirmed 2026"},
    {"id": "N5", "need": "Circuit breaker and kill switch policies, calibrated and evidenced",
     "source": "IOSCO 2026 (market risk evidence); Breeden 2026; IMF 2024"},
    {"id": "N6", "need": "Contingency for a third party model that fails or misbehaves",
     "source": "IOSCO 2026 Table 4 (contingency planning); FSB 2025"},
    {"id": "N7", "need": "Liquidity risk when AI liquidity providers withdraw in stress",
     "source": "IMF 2024; IOSCO 2026 (liquidity management plans)"},
    {"id": "N8", "need": "Disinformation and deepfake driven market moves",
     "source": "FSB 2024; IOSCO 2025 (malicious uses)"},
    {"id": "N9", "need": "Risk based, proportionate supervision with a stated level of human oversight",
     "source": "IOSCO 2026 Box 2"},
    {"id": "N10", "need": "Recordkeeping, audit trail and explainability of AI driven decisions",
     "source": "IOSCO 2026 Table 6; FSB 2026 sound practices"},
    {"id": "N11", "need": "Model validation, anomaly alerts and a methodology for suspension",
     "source": "IOSCO 2026 Table 3 (model risk management)"},
    {"id": "N12", "need": "Measure macro risk: the effect of aggregate firm conduct on system wide stability",
     "source": "IOSCO 2025 (knowledge gap); FSB 2024"},
    {"id": "N13", "need": "Adversarial robustness: data poisoning, prompt injection, agents gaming the "
                          "surveillance", "source": "IOSCO 2026 Table 3; FSB 2024 (cyber)"},
    {"id": "N14", "need": "Cross border alignment of indicators so authorities can compare",
     "source": "FSB 2025 (next steps); IOSCO 2026 (coordination)"},
    {"id": "N15", "need": "AI monitoring AI, with accountable human oversight",
     "source": "FSB 2026 consultation; IOSCO 2026 (AI as a judge)"},
]


def _hhi(shares):
    s = np.asarray(shares, dtype=float)
    return float(np.sum(s ** 2)) if len(s) else 0.0


def indicators(artefacts):
    """Supervisory indicators computable from a run, in the families of
    IOSCO (2026) Table 7 and the FSB (2025) third party indicators, plus the
    data gaps register: the indicators that need firm reporting and cannot
    be read from a synthetic run."""
    a = artefacts
    specs = (a.get("battery") or {}).get("specs", [])
    herd = [s for s in specs if s.get("shock_time") is not None and not s.get("holdout")]
    adoption, hhi, top, nvend = [], [], [], []
    for s in herd:
        shares = list(s.get("vendor_shares") or [])
        ai = sum(shares) + float(s.get("rl_share") or 0.0) + float(s.get("persona_share") or 0.0)
        adoption.append(ai)
        if shares:
            hhi.append(_hhi(shares)); top.append(max(shares)); nvend.append(len(shares))
    dose = a.get("concentration") or {}
    rl = a.get("rl_emergence") or {}
    pers = a.get("personas") or {}
    sens = None
    for p in pers.values():
        tab = np.asarray(p.get("table") or [], dtype=float)
        if tab.size:
            jump = float(np.max(np.abs(np.diff(tab, axis=1)))) if tab.shape[1] > 1 else 0.0
            sens = max(sens or 0.0, jump)
    s_summ = a.get("sentinels") or {}
    hold = a.get("sentinels_holdout") or {}
    drift = {n: float((hold.get(n) or {}).get("decision_f1", 0.0) - v.get("decision_f1", 0.0))
             for n, v in s_summ.items() if n in hold}
    risk = (a.get("risk") or {}).get("untreated") or {}
    rules = a.get("rules") or {}
    three = a.get("three_worlds") or {}
    out = {
        "adoption": {
            "ai_agent_share_mean": float(np.mean(adoption)) if adoption else None,
            "ai_agent_share_max": float(np.max(adoption)) if adoption else None,
            "families_in_battery": sorted({s.get("family") for s in specs}),
            "note": "share of agents driven by an AI vendor signal, an RL policy or an LLM persona; the "
                    "sandbox analogue of the adoption share indicator"},
        "third_party_concentration": {
            "vendor_hhi_mean": float(np.mean(hhi)) if hhi else None,
            "vendor_hhi_max": float(np.max(hhi)) if hhi else None,
            "top_vendor_share_max": float(np.max(top)) if top else None,
            "n_vendors_typical": int(np.median(nvend)) if nvend else None,
            "substitutability_proxy": (float(1.0 - np.max(top)) if top else None),
            "dislocation_threshold_share": dose.get("dislocation_threshold_share"),
            "response_convex": dose.get("convex"),
            "note": "Herfindahl index and top share of the vendor split; the dose response gives the share "
                    "at which dislocations become the likelier outcome"},
        "correlation_and_herding": {
            "herd_pre_shock_vol_ratio": (float((three.get("pre_shock_vol") or {}).get("herd", 0.0) /
                                               max((three.get("pre_shock_vol") or {}).get("quiet", 1e-9), 1e-9))
                                         if (three.get("pre_shock_vol") or {}).get("quiet") else None),
            "herd_post_shock_dd": (three.get("post_shock_dd") or {}).get("herd"),
            "quiet_post_shock_dd": (three.get("post_shock_dd") or {}).get("quiet"),
            "rl_emergent_policy_convergence": rl.get("policy_convergence"),
            "rl_emergent_momentum_slope": rl.get("momentum_slope"),
            "note": "correlated positioning as the herd's volatility and drawdown against the same shock "
                    "in a quiet market; emergent convergence of independently trained policies"},
        "input_output_sensitivity": {
            "persona_max_action_jump": sens,
            "note": "largest change of a persona's action for a one bucket change of the market state "
                    "(IOSCO 2026: erratic output to small input changes)"},
        "incidents": {
            "dislocation_probability_untreated": (np.mean([r["crash_prob_untreated"] for r in rules.values()
                                                           if r.get("crash_prob_untreated") is not None])
                                                  if rules else None),
            "expected_shortfall_untreated": risk.get("es"),
            "value_at_risk_untreated": risk.get("var"),
            "note": "frequency and severity of dislocations across the herding scenarios"},
        "model_performance": {
            "decision_f1": {n: v.get("decision_f1") for n, v in s_summ.items()},
            "held_out_drift": drift,
            "false_alert_rate": {n: v.get("false_alert_rate") for n, v in s_summ.items()},
            "note": "held out drift is the change of decision F1 from the calibration to the held out "
                    "population, the sandbox analogue of model drift monitoring"},
        "data_gaps": [
            "proportion of supervised firms using AI, by use case and production status (survey or reporting)",
            "AI research and development spending and patents (firm reporting)",
            "AI inventories with model type, provider and dependencies (firm reporting; the ATRS record "
            "covers HSL itself)",
            "incident frequency and severity in production AI systems (incident reporting)",
            "direct and indirect third party dependencies across firms, including cloud (firm reporting; "
            "the sandbox measures the consequence of concentration, not its level in the market)",
        ],
    }
    if isinstance(out["incidents"]["dislocation_probability_untreated"], float):
        out["incidents"]["dislocation_probability_untreated"] = float(out["incidents"]["dislocation_probability_untreated"])
    return out


def coverage(artefacts):
    """Coverage map: for each need, what this run supplies (with the figure),
    or that firm reporting is required."""
    a = artefacts
    ind = indicators(a)
    rules = a.get("rules") or {}
    fam = {}
    for n, r in rules.items():
        for f, v in (r.get("containment_by_family") or {}).items():
            fam.setdefault(f, {})[n] = v
    def best(f):
        d = fam.get(f) or {}
        if not d:
            return None
        k = max(d, key=lambda x: d[x] if d[x] is not None else -9)
        return {"rule": k, "containment": d[k]}
    inj = (a.get("redteam") or {}).get("injection") or {}
    ev = (a.get("redteam") or {}).get("evasion") or {}
    cf = a.get("conformal") or {}
    ap = a.get("appraisal") or {}
    tc = ind["third_party_concentration"]
    ch = ind["correlation_and_herding"]
    gap = a.get("decision_gap") or {}
    rows = []
    def add(nid, status, evidence):
        n = next(x for x in NEEDS if x["id"] == nid)
        rows.append(dict(n, status=status, evidence=evidence))
    add("N1", "partial", "indicators block computed from the run; the data gaps register lists what needs firm "
                         "reporting")
    srcs = sorted({(e.get("calibration") or {}).get("diagnostics", {}).get("vendor_split_source", "")
                   for e in ((a.get("data") or {}).get("datasets") or []) if e.get("calibration")} - {""})
    add("N2", "answered", (f"vendor Herfindahl index up to {tc['vendor_hhi_max']:.3f}, top vendor share "
                           f"{tc['top_vendor_share_max']:.2f}, dislocations likelier from share "
                           f"{tc['dislocation_threshold_share']}" if tc.get("vendor_hhi_max") is not None else "no vendor split")
        + (f"; from supplied data the split is {', '.join(srcs)}" if srcs else ""))
    add("N3", "answered", f"{gap.get('n_tools')} sentinels ranked by decision F1; certified "
                          f"{_nice(a.get('certified') or '')}; ignition family for collusion; herd against quiet drawdown "
                          f"{_r(ch.get('herd_post_shock_dd'))} against {_r(ch.get('quiet_post_shock_dd'))}")
    add("N4", "answered", "every scenario is simulated in a network restricted sandbox with quiet and stressed "
                          "families, held out and empirical families")
    b5 = best("vendor_fault") or best("herd_high")
    add("N5", "answered", f"{len(rules)} rules scored on containment and false halts; best on the faulty model "
                          f"episode {_nice(b5['rule'])} at {b5['containment']:.2f}" if b5 else f"{len(rules)} rules scored")
    b6 = best("vendor_fault")
    add("N6", "answered" if b6 else "open", f"vendor fault family: best rule {_nice(b6['rule'])} contains "
                                            f"{b6['containment']:.2f}" if b6 else "family not in this battery")
    b7 = best("liquidity_withdrawal")
    add("N7", "answered" if b7 else "open", f"liquidity withdrawal family: best rule {_nice(b7['rule'])} contains "
                                            f"{b7['containment']:.2f}" if b7 else "family not in this battery")
    b8 = best("misinformation")
    add("N8", "answered" if b8 else "open", f"misinformation family: best rule {_nice(b8['rule'])} contains "
                                            f"{b8['containment']:.2f}" if b8 else "family not in this battery")
    rec = ap.get("recommended")
    add("N9", "answered", f"appraisal by tier and proportionality; recommended tier "
                          f"{rec['tier']} ({rec['tier_label']}); every rule carries its human oversight level"
        if rec else "appraisal by tier and proportionality; no rule eligible on this run")
    add("N10", "answered", "hash chained signed ledger, critic vetting of every number, transparency record, "
                           "flags explained per agent in the network panel")
    add("N11", "answered", f"conformal false alert guarantee at {next(iter(cf.values()))['alpha']} on "
                           f"{next(iter(cf.values()))['n_calibration']} calibration scenarios; autonomy gate; "
                           f"emergency stop" if cf else "autonomy gate and emergency stop")
    add("N12", "partial", "aggregate conduct to system outcome measured in the sandbox (dose response, Shapley "
                          "attribution, tail risk); not a measurement of the real market")
    add("N13", "answered", f"injection suite {inj.get('n_contained')} of {inj.get('n_cases')} contained; "
                           f"adversarial evasion worst case F1 {_r(ev.get('worst_case_f1'), 2)}; matrix game")
    add("N14", "answered", "exchange record in the evidence pack with the indicators in a fixed schema")
    add("N15", "answered", "sentinels, critic and red team are AI monitoring AI; named preparer and approver "
                           "with SMF or certified function at both gates")
    return {"needs": rows, "n_answered": sum(r["status"] == "answered" for r in rows),
            "n_partial": sum(r["status"] == "partial" for r in rows),
            "n_open": sum(r["status"] == "open" for r in rows), "indicators": ind}


def exchange_record(artefacts, run_id, authority=""):
    """Machine readable summary in a fixed schema for exchange between
    authorities (FSB 2025: alignment of indicators across borders)."""
    a = artefacts
    cov = coverage(a)
    prov = a.get("provenance") or {}
    return {"schema": "hsl.exchange/1", "run_id": run_id, "authority": authority,
            "hsl_version": prov.get("hsl_version"), "battery_hash": prov.get("battery_hash"),
            "indicators": cov["indicators"],
            "certified_sentinel": a.get("certified"),
            "decision_gap": (a.get("decision_gap") or {}).get("decision_gap"),
            "p_inversion": (a.get("decision_gap_bootstrap") or {}).get("p_inversion"),
            "recommended_rule": (a.get("appraisal") or {}).get("recommended"),
            "rule_oversight": {k: RULE_OVERSIGHT.get(k, ("", ""))[0] for k in (a.get("rules") or {})},
            "needs_coverage": {r["id"]: r["status"] for r in cov["needs"]},
            "data_classifications": [d["summary"]["classification"] for d in ((a.get("data") or {}).get("datasets") or [])]}
