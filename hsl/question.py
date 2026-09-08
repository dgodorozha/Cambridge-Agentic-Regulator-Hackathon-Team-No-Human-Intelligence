"""The policy question, read without a model.

Without a model the battery used to be the same whatever the question
said. This module reads the question deterministically: the numbers it
states (shares, correlations, shock sizes, horizons), the mechanisms it
names (a faulty vendor model, liquidity withdrawal, misinformation,
collusion, evasion, a shared foundation model) and the tools it asks about
(a throttle, a kill switch, a circuit breaker, a sentinel). From those it
builds a `question` family that contains the case asked about, marks the
tools of interest so the briefing opens with a direct answer for them, and
records what it matched and what it could not read. The parse is
validated by the same bounds as a stored family and written to the
ledger. When a model is configured it still runs, so the direct answer is
always available and the model's plan is a complement, not a replacement.
"""

import re

from .families import validate_family, expand_family

_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", re.I)
_RHO = re.compile(r"(?:correlation|rho|correlated)\s*(?:of|at|=)?\s*(0?\.\d+|1\.0|\d{2,3}\s*(?:%|per\s*cent))", re.I)
_SHOCK = re.compile(r"(?:shock|drop|fall|decline)\s*(?:of|by)?\s*(\d{1,2}(?:\.\d+)?)\s*(?:%|per\s*cent|percent)"
                    r"|(\d{1,2}(?:\.\d+)?)\s*(?:%|per\s*cent|percent)\s*(?:shock|drop|fall|decline)", re.I)
_SHARE_CTX = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|per\s*cent|percent)\s*(?:of\s+(?:the\s+)?(?:agents|market|participants|traders|flow))?"
                        r"\s*(?:on|using|running|built on|from)\s+(?:one|a single|the same|a)\s+(?:vendor|model|provider|foundation model)", re.I)
_STEPS = re.compile(r"(\d{2,4})\s*(?:steps|ticks|periods)", re.I)

MECHANISMS = [
    ("vendor_fault", ("faulty", "fault", "malfunction", "erroneous", "bug", "misfir", "wrong signal", "model failure",
                      "breaks down")),
    ("liquidity_withdrawal", ("liquidity withdraw", "withdraw liquidity", "market maker", "market-maker",
                              "liquidity provider", "liquidity dries", "liquidity evaporat", "step away")),
    ("misinformation", ("misinformation", "disinformation", "deepfake", "fake news", "false news", "rumour", "rumor",
                        "hoax")),
    ("ignition", ("collu", "ignition", "manipulat", "spoof", "wash trad", "pump")),
    ("evader", ("evade", "evasion", "rotat", "hide from", "defeat surveillance", "avoid detection")),
    ("persona", ("llm", "language model", "persona", "foundation model", "same model", "shared model", "monoculture",
                 "one vendor", "single vendor", "one provider")),
    ("imitation", ("imitation", "copy each other", "contagion", "social", "word of mouth")),
    ("voter", ("voter", "opinion", "consensus")),
]
RULE_TERMS = [
    ("dynamic_throttle", ("throttl", "slow down", "speed bump")),
    ("kill_switch", ("kill switch", "kill-switch", "killswitch", "cancel", "switch off", "disconnect")),
    ("static_circuit_breaker", ("circuit breaker", "trading halt", "halt trading", "halt the market", "market halt",
                                "pause trading")),
    ("market_wide_breaker", ("market wide", "market-wide", "mwcb", "level 1", "7%", "13%", "20%")),
    ("luld_style_band", ("luld", "price band", "limit up", "limit down", "band")),
    ("venue_volatility_halt", ("venue", "volatility interruption", "auction", "collar")),
    ("responsive_ladder", ("ladder", "escalat", "graduated", "proportionate response")),
    ("learned_policy", ("learned policy", "adaptive policy", "reinforcement", "learned rule")),
]
SENTINEL_TERMS = [
    ("absorption_ratio", ("absorption",)),
    ("corr_clustering", ("correlation cluster", "correlation based", "correlation-based", "corr cluster")),
    ("network_sentinel", ("network", "community")),
    ("naive_threshold", ("volatility trigger", "volatility threshold", "naive", "vol trigger")),
    ("tail_dependence", ("tail dependence", "tail concordance", "joint extreme")),
    ("endogeneity", ("hawkes", "endogeneity", "branching ratio", "reflexiv")),
    ("imbalance", ("imbalance", "lsv", "buy sell", "buy-sell")),
    ("lead_lag", ("lead lag", "lead-lag", "ignition sentinel", "leader")),
]


def _num(s):
    s = s.replace("%", "").replace("per cent", "").replace("percent", "").strip()
    v = float(s)
    return v / 100.0 if v > 1.0 else v


def interpret(question):
    """Deterministic parse of the policy question. Returns the matched
    phrases, the parameters read, the mechanisms and tools named, the
    question family document (or None when nothing quantitative or
    mechanistic was found) and the fragments that were not interpreted."""
    q = (question or "").strip()
    ql = q.lower()
    matched, params = [], {}
    m = _SHARE_CTX.search(q)
    shares = [_num(x) for x in _PCT.findall(q)]
    if m:
        params["vendor_share"] = _num(m.group(1))
        matched.append(m.group(0).strip())
    elif shares and re.search(r"vendor|provider|foundation model|shared model|agents|traders|participants", ql):
        cand = [s for s in shares if 0.05 <= s <= 0.60]
        if cand:
            params["vendor_share"] = max(cand)
            matched.append(f"{params['vendor_share']:.0%} share")
    r = _RHO.search(q)
    if r:
        params["vendor_rho"] = _num(r.group(1))
        matched.append(r.group(0).strip())
    s = _SHOCK.search(q)
    if s:
        params["shock_size"] = _num(s.group(1) or s.group(2))
        matched.append(s.group(0).strip())
    st = _STEPS.search(q)
    if st:
        params["t_steps"] = int(st.group(1))
        matched.append(st.group(0).strip())
    mechanisms = [name for name, keys in MECHANISMS if any(k in ql for k in keys)]
    rules = [name for name, keys in RULE_TERMS if any(k in ql for k in keys)]
    sentinels = [name for name, keys in SENTINEL_TERMS if any(k in ql for k in keys)]
    for _name, keys in MECHANISMS + RULE_TERMS + SENTINEL_TERMS:
        for k in keys:
            if k in ql:
                matched.append(k)
    family = None
    if params or mechanisms:
        doc = {"name": "question", "note": f"the case asked about: {q[:160]}", "seeds": 2,
               "vendor_shares": [min(0.45, params.get("vendor_share", 0.35)), 0.15],
               "vendor_rhos": [params.get("vendor_rho", 0.85), 0.30],
               "shock_size": params.get("shock_size", 0.05)}
        if "t_steps" in params:
            doc["t_steps"] = params["t_steps"]
            doc["shock_time"] = params["t_steps"] // 2
        if "vendor_fault" in mechanisms:
            doc["vendor_fault_time"] = doc.get("shock_time", 300)
            doc["vendor_rhos"][0] = min(doc["vendor_rhos"][0], 0.60)
        if "liquidity_withdrawal" in mechanisms:
            doc["liquidity_withdrawal_time"] = doc.get("shock_time", 300) + 12
        if "misinformation" in mechanisms:
            doc["false_shock_len"] = 20
        if "ignition" in mechanisms:
            doc["manipulator_share"] = 0.08
        if "evader" in mechanisms:
            doc["evader_cohorts"] = 3
        if "persona" in mechanisms and "vendor_share" not in params:
            doc["persona"] = "momentum_follower"
            doc["persona_share"] = 0.30
            doc["vendor_shares"] = [0.15, 0.10]
        if "imitation" in mechanisms:
            doc["generator"] = "imitation"
        elif "voter" in mechanisms:
            doc["generator"] = "voter"
        family = doc
    # what was not read: sentences without any matched phrase
    unmatched = []
    for sent in re.split(r"(?<!\d)[.;?!](?!\d)\s*", q):
        sl = sent.lower().strip()
        if sl and not any(mm.lower() in sl for mm in matched):
            unmatched.append(sent.strip())
    return {"question": q, "matched": matched, "params": params, "mechanisms": mechanisms,
            "rules_of_interest": rules, "sentinels_of_interest": sentinels, "family": family,
            "unmatched": unmatched, "interpreted": bool(matched)}


def question_family(parse, log=None):
    """Validated scenarios for the question family, or [] with the reason
    logged."""
    if not parse or not parse.get("family"):
        return []
    ok, fam, errors, notes = validate_family(parse["family"], allow_reserved=True)
    if not ok:
        if log is not None:
            log("question_family_rejected", errors=errors)
        return []
    specs = expand_family(fam)
    if log is not None:
        log("question_interpreted", matched=parse["matched"], params=parse["params"],
            mechanisms=parse["mechanisms"], rules_of_interest=parse["rules_of_interest"],
            sentinels_of_interest=parse["sentinels_of_interest"], clamped=notes,
            unmatched=parse["unmatched"], n_scenarios=len(specs))
    return specs


def direct_answer(parse, artefacts, labels):
    """The briefing's opening: what the run says about the tools and the
    case the question named. Every figure is read from the artefacts."""
    if not parse or not parse.get("interpreted"):
        return None
    a = artefacts
    fam_present = any(f == "question" for f in (a.get("battery") or {}).get("families", []))
    lines = []
    rules = a.get("rules") or {}
    s = a.get("sentinels") or {}
    for rn in parse["rules_of_interest"]:
        v = rules.get(rn)
        if not v:
            continue
        byfam = v.get("containment_by_family") or {}
        lines.append({"kind": "rule", "name": rn, "label": v.get("label", rn),
                      "containment_battery": v.get("containment"),
                      "containment_question": byfam.get("question") if fam_present else None,
                      "false_halt_rate": v.get("false_halt_rate"),
                      "crash_prob_treated": v.get("crash_prob_treated"),
                      "human_oversight": (v.get("human_oversight") or {}).get("level")})
    for sn in parse["sentinels_of_interest"]:
        v = s.get(sn)
        if not v:
            continue
        lines.append({"kind": "sentinel", "name": sn, "label": labels.get(sn, sn),
                      "decision_f1": v.get("decision_f1"), "false_alert_rate": v.get("false_alert_rate"),
                      "decision_f1_question": (v.get("by_family") or {}).get("question", {}).get("decision_f1")
                      if fam_present else None})
    return {"family_present": fam_present, "tools": lines, "matched": parse["matched"],
            "unmatched": parse["unmatched"], "params": parse["params"], "mechanisms": parse["mechanisms"],
            "certified": a.get("certified"), "certification_basis": a.get("certification_basis"),
            "recommended_rule": (a.get("appraisal") or {}).get("recommended")}
