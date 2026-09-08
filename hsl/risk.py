"""Quantitative risk measures for the dislocation, and a tail dependence
sentinel.

A mean drawdown treats a 5% and a 25% dislocation as one number. The risk
management literature (McNeil, Frey and Embrechts 2015) measures the tail
instead: Value at Risk at level alpha is the alpha quantile of the loss,
Expected Shortfall is the mean loss beyond it (coherent, unlike VaR), and
extreme value theory fits the excesses over a high threshold with a
generalised Pareto distribution (Pickands 1975; Balkema and de Haan 1974)
to estimate the probability of losses larger than any observed. HSL
applies all three to the post shock drawdown across the herding
scenarios, untreated and under each rule, so containment can be read in
the tail and not only in the mean.

The tail dependence sentinel that applies the same chapter's dependence
measures to agents lives in `herding.py`.
"""

import numpy as np
from scipy.stats import genpareto



def value_at_risk(losses, alpha=0.9):
    x = np.sort(np.asarray(losses, dtype=float))
    if len(x) == 0:
        return None
    return float(np.quantile(x, alpha))


def expected_shortfall(losses, alpha=0.9):
    x = np.sort(np.asarray(losses, dtype=float))
    if len(x) == 0:
        return None
    q = np.quantile(x, alpha)
    tail = x[x >= q]
    return float(tail.mean()) if len(tail) else float(q)


def gpd_tail(losses, threshold_q=0.7, probe=None):
    """Peaks over threshold fit. Returns the threshold, the number of
    excesses, the fitted shape and scale, and the tail probability of
    exceeding `probe` (default: twice the threshold) under the fitted
    model. With few excesses the fit is descriptive; the count is reported
    beside it so the reader can weigh it."""
    x = np.asarray(losses, dtype=float)
    if len(x) < 8:
        return {"n": int(len(x)), "n_excess": 0, "threshold": None, "shape": None, "scale": None,
                "probe": None, "tail_prob": None}
    u = float(np.quantile(x, threshold_q))
    exc = x[x > u] - u
    probe = probe if probe is not None else 2.0 * u
    if len(exc) < 5:
        return {"n": int(len(x)), "n_excess": int(len(exc)), "threshold": u, "shape": None,
                "scale": None, "probe": float(probe), "tail_prob": None}
    shape, _loc, scale = genpareto.fit(exc, floc=0.0)
    p_u = float(np.mean(x > u))
    tail = p_u * float(genpareto.sf(probe - u, shape, loc=0.0, scale=scale)) if probe > u else p_u
    return {"n": int(len(x)), "n_excess": int(len(exc)), "threshold": u, "shape": float(shape),
            "scale": float(scale), "probe": float(probe), "tail_prob": float(tail),
            "empirical_prob_above_probe": float(np.mean(x > probe))}


def risk_report(rules, base_dd, alpha=0.9, B=300, seed=0):
    """VaR, ES and the GPD tail of the untreated post shock drawdown, and
    the ES reduction of each rule with a bootstrap interval. `base_dd` is
    the list of untreated post shock drawdowns over the herding scenarios;
    `rules[name]["per_scenario"]` supplies the treated ones."""
    base = np.asarray(base_dd, dtype=float)
    rng = np.random.default_rng(seed)
    out = {"alpha": float(alpha), "n_scenarios": int(len(base)),
           "untreated": {"mean": float(base.mean()) if len(base) else None,
                         "var": value_at_risk(base, alpha), "es": expected_shortfall(base, alpha),
                         "gpd": gpd_tail(base)},
           "rules": {}}
    for name, v in rules.items():
        per = v.get("per_scenario") or []
        rp = np.asarray([p["rule_post_dd"] for p in per if not p["quiet"]], dtype=float)
        bp = np.asarray([p["base_post_dd"] for p in per if not p["quiet"]], dtype=float)
        if len(rp) == 0:
            continue
        es_b, es_r = expected_shortfall(bp, alpha), expected_shortfall(rp, alpha)
        red = 1.0 - es_r / max(es_b, 1e-9)
        boots = []
        for _ in range(B):
            idx = rng.integers(0, len(rp), size=len(rp))
            boots.append(1.0 - expected_shortfall(rp[idx], alpha) / max(expected_shortfall(bp[idx], alpha), 1e-9))
        out["rules"][name] = {
            "var_treated": value_at_risk(rp, alpha), "es_treated": es_r,
            "es_untreated": es_b, "es_reduction": float(red),
            "es_reduction_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "mean_reduction": float(1.0 - rp.mean() / max(bp.mean(), 1e-9)),
            "gpd_treated": gpd_tail(rp)}
    ranked = sorted(out["rules"], key=lambda n: out["rules"][n]["es_reduction"], reverse=True)
    out["ranking_by_es_reduction"] = ranked
    out["ranking_by_mean_reduction"] = sorted(out["rules"], key=lambda n: out["rules"][n]["mean_reduction"],
                                              reverse=True)
    return out
