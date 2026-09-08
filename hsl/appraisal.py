"""Regulatory options appraisal and enforcement ladder.

The intervention monitor scores rules on containment and false halts. A
regulator has to justify a choice of instrument as well: the Better
Regulation Framework (HM Government 2023) requires a do nothing baseline,
non regulatory options and a proportionate assessment of costs and
benefits; responsive regulation (Ayres and Braithwaite 1992; Baldwin and
Black 2008) escalates from the least intrusive instrument that works;
risk based regulation (Black 2005) targets intervention on the sources
of risk rather than the whole market. This module writes those tests down
against the numbers HSL already measures.

Instrument types. A market wide halt is command and control applied to
everyone; a targeted throttle or kill switch is a risk based instrument
aimed at the flagged agents; surveillance without intervention is the
non regulatory option; the untreated herd is the do nothing baseline.

Enforcement ladder. Tier 0 monitor and warn (sentinel only), tier 1
targeted throttle, tier 2 targeted kill, tier 3 venue or price band halt,
tier 4 market wide halt. The recommendation is the lowest tier whose rule
contains the dislocation to the declared target within the false halt
budget and whose burden on agents that were not destabilising stays below
the proportionality limit.

Legal basis (illustrative, for a UK or EU authority): MiFID II Article
48(5) and RTS 7 (venue halts), RTS 6 Article 12 (firm kill functionality),
MAR Article 12 and Annex II (manipulation indicators), FSMA 2000 section
1D (the integrity objective), the FCA's supervisory and enforcement
powers under FSMA Part XI. Nothing here is legal advice; the basis is a
pointer for the supervisory workflow to name the power it would use.
"""

INSTRUMENTS = {
    "static_circuit_breaker": ("command and control", 4, "market wide halt on a rolling return limit"),
    "market_wide_breaker": ("command and control", 4, "market wide halt at set decline levels"),
    "luld_style_band": ("command and control", 3, "price band with a limit state and pause"),
    "venue_volatility_halt": ("command and control", 3, "venue volatility interruption"),
    "learned_policy": ("adaptive command and control", 3, "market wide throttle or halt chosen by a learned policy"),
    "dynamic_throttle": ("risk based, targeted", 1, "throttle of flagged agents"),
    "kill_switch": ("risk based, targeted", 2, "cancellation for flagged agents"),
}
LEGAL = {
    "static_circuit_breaker": "MiFID II Art 48(5); RTS 7",
    "market_wide_breaker": "MiFID II Art 48(5); market wide breaker rules of the venue",
    "luld_style_band": "MiFID II Art 48(5); LULD plan (US)",
    "venue_volatility_halt": "MiFID II Art 48(5); ESMA circuit breaker guidelines",
    "learned_policy": "MiFID II Art 48(5) (as a venue rule); advisory only in HSL",
    "dynamic_throttle": "RTS 6 Art 12 by analogy; MAR Art 12 and Annex II for the conduct",
    "kill_switch": "RTS 6 Art 12; MAR Art 12 and Annex II for the conduct",
}
TIERS = {0: "monitor and warn", 1: "targeted throttle", 2: "targeted kill", 3: "price band or venue halt",
         4: "market wide halt"}


def appraise(rules, risk=None, frontier=None, containment_target=0.3, false_halt_budget=0.25,
             proportionality=0.5, c_declared=0.5):
    """Options appraisal per rule and a responsive regulation
    recommendation. Proportionality is the burden on non destabilising
    agents relative to the burden on destabilising ones; a targeted rule
    that burdens the innocent as much as the guilty fails it."""
    options = []
    for name, v in rules.items():
        kind, tier, desc = INSTRUMENTS.get(name, ("command and control", 4, v.get("label", name)))
        b = v.get("burden_by_class") or {}
        bd, bo = b.get("destabilising"), b.get("non_destabilising")
        prop = None
        if bd is not None and bo is not None:
            prop = float(bo / bd) if bd > 1e-9 else (0.0 if bo <= 1e-9 else float("inf"))
        loss = None
        if frontier and frontier.get("rules"):
            loss = frontier["rules"]["loss_at_declared"].get(name)
        es_red = (risk or {}).get("rules", {}).get(name, {}).get("es_reduction")
        passes = {
            "containment": (v.get("containment") or 0.0) >= containment_target,
            "false_halt_budget": (v.get("false_halt_rate") or 0.0) <= false_halt_budget,
            "proportionality": (prop is None) or (not v.get("targeted")) or (prop <= proportionality),
        }
        options.append({"rule": name, "label": v.get("label", name), "instrument": kind, "tier": tier,
                        "tier_label": TIERS[tier], "description": desc, "legal_basis": LEGAL.get(name, ""),
                        "containment": v.get("containment"), "false_halt_rate": v.get("false_halt_rate"),
                        "es_reduction": es_red, "loss_at_declared_weight": loss,
                        "burden_ratio_others_to_destabilising": (None if prop is None or prop == float("inf")
                                                                 else prop),
                        "passes": passes, "passes_all": all(passes.values())})
    options.sort(key=lambda o: (o["tier"], -(o["containment"] or 0.0)))
    eligible = [o for o in options if o["passes_all"]]
    rec = eligible[0] if eligible else None
    return {"containment_target": containment_target, "false_halt_budget": false_halt_budget,
            "proportionality_limit": proportionality, "c_declared": c_declared,
            "baseline": "do nothing: the untreated herd (three worlds, herd path)",
            "non_regulatory_option": "monitor and warn: certify a sentinel, intervene by no rule",
            "options": options,
            "recommended": (None if rec is None else
                            {"rule": rec["rule"], "label": rec["label"], "tier": rec["tier"],
                             "tier_label": rec["tier_label"], "instrument": rec["instrument"],
                             "legal_basis": rec["legal_basis"]}),
            "n_eligible": len(eligible),
            "principle": "responsive regulation: the lowest tier that meets the containment target within "
                         "the false halt budget and the proportionality limit"}
