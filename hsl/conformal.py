"""Conformal certification of alert thresholds.

Version 2 declared a false alert budget and reported each sentinel's
empirical quiet market alert rate against it. That is an estimate, not a
guarantee. Conformal anomaly detection (Laxhammar and Falkman 2010; Vovk,
Gammerman and Shafer 2005; Bates, Candes, Lei, Romano and Sesia 2023)
turns the same calibration scenarios into a threshold with a finite sample
guarantee: if a new quiet scenario is exchangeable with the n calibration
scenarios, flagging it whenever its conformal p value is at most alpha
has false alert probability at most alpha, whatever the sentinel and
whatever the score distribution. The guarantee needs n at least 1/alpha - 1
calibration scenarios, so the battery carries eight quiet calibration
scenarios and the declared budget of 0.25 is achievable exactly.

What the guarantee does not cover is written down beside it: held out
quiet scenarios come from a different population and their alert rate is
reported as the empirical check of exchangeability, not as a guaranteed
quantity. The score is the sentinel's peak stress inside the pre emption
window, the same score the autonomy gate uses.
"""

import numpy as np

from .evaluate import FALSE_ALERT_BUDGET


def conformal_p(score, calibration):
    """Conformal p value of a score against calibration scores from quiet
    scenarios: the share of calibration scores at least as extreme, with the
    test point counted in the denominator (Vovk and others 2005)."""
    cal = np.asarray(calibration, dtype=float)
    return float((1 + np.sum(cal >= score)) / (len(cal) + 1))


def conformal_threshold(calibration, alpha):
    """Smallest score whose conformal p value is at most alpha, or None when
    n is too small for the level to be achievable."""
    cal = np.sort(np.asarray(calibration, dtype=float))[::-1]
    n = len(cal)
    k = int(np.floor(alpha * (n + 1))) - 1      # number of calibration scores allowed above
    if k < 0:
        return None
    return float(cal[k]) if k < n else float(cal[-1])


def certify(rows, sentinel_names, alpha=FALSE_ALERT_BUDGET):
    """Per sentinel conformal certification from the evaluation rows.

    Calibration set: quiet scenarios of the calibration battery. The
    conformal alert rule flags a scenario when its p value is at most alpha.
    Reports the guaranteed false alert bound (alpha, achievable when n >=
    1/alpha - 1), the empirical alert rate on held out quiet scenarios, and
    the conformal power on herding scenarios, calibration and held out."""
    out = {}
    for name in sentinel_names:
        r = [x for x in rows if x["sentinel"] == name]
        cal = [x["peak_stress"] for x in r if x["quiet"] and not x["holdout"]]
        n = len(cal)
        achievable = n >= int(np.ceil(1.0 / alpha)) - 1
        thr = conformal_threshold(cal, alpha) if n else None
        min_level = 1.0 / (n + 1) if n else None

        def rate(sel):
            ps = [conformal_p(x["peak_stress"], cal) for x in sel]
            return (float(np.mean([p <= alpha for p in ps])) if ps else None), len(ps)

        p_cal_herd, n_cal_herd = rate([x for x in r if not x["quiet"] and not x["holdout"]])
        p_hold_quiet, n_hold_quiet = rate([x for x in r if x["quiet"] and x["holdout"]])
        p_hold_herd, n_hold_herd = rate([x for x in r if not x["quiet"] and x["holdout"]])
        out[name] = {
            "alpha": float(alpha), "n_calibration": n,
            "min_achievable_level": min_level,
            "guarantee_achievable": bool(achievable),
            "guaranteed_false_alert_bound": float(alpha) if achievable else None,
            "threshold_score": thr,
            "power_calibration_herd": p_cal_herd, "n_calibration_herd": n_cal_herd,
            "false_alert_rate_holdout": p_hold_quiet, "n_holdout_quiet": n_hold_quiet,
            "power_holdout_herd": p_hold_herd, "n_holdout_herd": n_hold_herd,
            "exchangeability_check": (None if p_hold_quiet is None else
                                      bool(p_hold_quiet <= alpha + 1e-12)),
        }
    return out


def certifiable(cert, summary, min_power=0.5):
    """Sentinels whose conformal guarantee is achievable and whose conformal
    power on calibration herds is at least min_power, ranked by decision F1."""
    ok = [(summary[n]["decision_f1"], n) for n, v in cert.items()
          if v["guarantee_achievable"] and (v["power_calibration_herd"] or 0.0) >= min_power
          and n in summary]
    return [n for _, n in sorted(ok, reverse=True)]
