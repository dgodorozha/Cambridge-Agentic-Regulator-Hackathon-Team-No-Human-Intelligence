"""Score triggered autonomy gate with out of sample validation.

Construct (after Iravani, Orfanoudaki, Markakis and Szpruch, "The Limits of
Autonomy in Agentic AI"): each sentinel's per scenario herding score (peak
stress inside the pre emption window, normalised across the battery) is
split by two gates set to the zero claim tails of the battery. Below the
low gate the system autonomously stands behind no intervention; above the
high gate it may autonomously trigger the targeted throttle; every score in
the band between escalates to the named supervisor.

Version 1 fitted the gates on the same scenarios it then scored, so "zero
claims" held by construction. Version 2 keeps the in sample breadth for
comparability and adds a leave one out estimate: for each scenario the
gates are refitted without it and the held out scenario is classified.
The out of sample claim rate is the number a certification should quote.
"""

import numpy as np

LIFT_BAR = 1.25


def _fit(scores, quiet):
    """Return (t_lo, t_hi, separable) from normalised scores and quiet flags."""
    herd = [s for s, q in zip(scores, quiet) if not q]
    qt = [s for s, q in zip(scores, quiet) if q]
    separable = bool(herd and qt and min(herd) > max(qt))
    if separable:
        t = (min(herd) + max(qt)) / 2
        return t, t, True
    t_lo = min(herd) if herd else 0.0
    t_hi = max(qt) if qt else 1.0
    return t_lo, t_hi, False


def autonomy_gates(rows, sentinel_names, lift_bar=LIFT_BAR):
    """rows: evaluation rows (calibration battery only, held out rows are
    ignored). Returns per sentinel gates, breadths and the leave one out
    validation."""
    aut = {}
    for name in sentinel_names:
        rr = [x for x in rows if x["sentinel"] == name and not x["holdout"]]
        if not rr:
            continue
        pk = np.array([x["peak_stress"] for x in rr], dtype=float)
        lo_, hi_ = pk.min(), pk.max()
        span = (hi_ - lo_) or 1.0
        s = (pk - lo_) / span
        quiet = [bool(x["quiet"]) for x in rr]
        t_lo, t_hi, separable = _fit(list(s), quiet)

        prec = [x["precision"] for x in rr if not x["quiet"] and x.get("precision") is not None]
        base = [x["base_rate"] for x in rr if not x["quiet"]]
        lift = (np.mean(prec) / np.mean(base)) if prec and base and np.mean(base) > 0 else 0.0
        throttle_ok = bool(lift >= lift_bar)

        n_all = len(rr)
        clear = float(np.sum(s < t_lo) / n_all)
        thr_tail = float(np.sum(s > t_hi) / n_all)
        throttle = thr_tail if throttle_ok else 0.0

        # leave one out: refit gates without scenario i, classify i
        claims, backed, decisions = 0, 0, []
        for i in range(n_all):
            keep = [j for j in range(n_all) if j != i]
            lo_i, hi_i, _ = _fit([s[j] for j in keep], [quiet[j] for j in keep])
            si = s[i]
            if si < lo_i:
                decision = "auto_clear"
                claim = not quiet[i]           # cleared a herd scenario
            elif si > hi_i and throttle_ok:
                decision = "auto_throttle"
                claim = quiet[i]               # throttled a quiet market
            else:
                decision = "escalate"
                claim = False
            backed += decision != "escalate"
            claims += bool(claim)
            decisions.append({"scenario": rr[i]["scenario"], "decision": decision,
                              "claim": bool(claim)})
        loo = {"backed": backed / n_all, "claims": claims,
               "claim_rate": claims / n_all,
               "claim_rate_of_backed": (claims / backed) if backed else 0.0,
               "decisions": decisions}

        aut[name] = {
            "scores": [{"scenario": x["scenario"], "quiet": bool(x["quiet"]),
                        "family": x["family"], "s": float(v)} for x, v in zip(rr, s)],
            "t_lo": float(t_lo), "t_hi": float(t_hi),
            "clear": clear, "throttle": throttle, "thr_tail": thr_tail,
            "breadth": clear + throttle,
            "lift": float(lift), "lift_bar": lift_bar,
            "throttle_ok": throttle_ok, "separable": separable,
            "loo": loo,
        }
    return aut


def autonomy_public(aut):
    """The autonomy result without per scenario score lists, for
    artefacts.json and the ledger."""
    out = {}
    for k, v in aut.items():
        d = {kk: vv for kk, vv in v.items() if kk != "scores"}
        d["loo"] = {kk: vv for kk, vv in v["loo"].items() if kk != "decisions"}
        out[k] = d
    return out
