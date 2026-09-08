"""Survival analysis of dislocation and detection.

A mean containment hides when a dislocation happens and whether a rule
merely delays it. Survival analysis (ST411; Kaplan and Meier 1958; Cox
1972) treats the time to an event with censoring: a run that has not
dislocated by the horizon is censored, not dropped, and a run that never
alerts is censored at its length.

Time to dislocation. Each run is at risk from the shock; the event is
the first step at which the drawdown from the pre shock level exceeds the
dislocation threshold. Arms are the untreated market and the market under
each rule. The Kaplan Meier curve per arm reads the probability of no
dislocation yet; a Cox proportional hazards model with the untreated
market as reference gives each rule a hazard ratio, adjusted for the
dominant vendor's share and correlation, so a rule that merely delays a
dislocation is distinguished from one that prevents it.

Detection. Per sentinel, the share of herding runs with an alert before
the shock (pre emption) and the median alert step over the runs.

The Cox model uses the Breslow partial likelihood maximised by Newton
steps on the analytic gradient and Hessian; standard errors come from the
observed information at the optimum. Proportional hazards is an
assumption, stated as such in the briefing.
"""

import numpy as np
from scipy.optimize import minimize
from scipy.stats import chi2, norm

from .evaluate import DISLOCATION_DD


def time_to_dislocation(res, threshold=DISLOCATION_DD):
    """(time, event): steps after the shock to the first crossing of the
    threshold and 1, or (None, 0) if the run never crosses. Quiet runs
    (no shock) are measured from the start."""
    t = res.first_crossing(threshold)
    return (None, 0) if t is None else (int(t), 1)


def kaplan_meier(times, events):
    """Kaplan Meier estimate. `events` are 1 for an event and 0 for a
    censored time. Returns the distinct event times, the survival at each,
    the median (None if not reached), the event count and n."""
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=int).astype(bool)
    uniq = np.unique(t[e])
    surv, at_risk, d_list = [], [], []
    s = 1.0
    for u in uniq:
        n_risk = int(np.sum(t >= u))
        d = int(np.sum((t == u) & e))
        s *= (1.0 - d / n_risk) if n_risk else 1.0
        surv.append(float(s)); at_risk.append(n_risk); d_list.append(d)
    median = None
    for u, s_ in zip(uniq, surv):
        if s_ <= 0.5:
            median = float(u)
            break
    return {"times": [float(u) for u in uniq], "survival": surv, "at_risk": at_risk,
            "events_at": d_list, "median": median, "events": int(e.sum()), "n": int(len(t))}


def survival_at(km, t):
    """Survival probability at time t from a Kaplan Meier dict."""
    s = 1.0
    for u, s_ in zip(km["times"], km["survival"]):
        if u <= t:
            s = s_
        else:
            break
    return float(s)


def logrank_test(t1, e1, t2, e2):
    """Two sample log rank test."""
    t = np.concatenate([t1, t2]).astype(float)
    e = np.concatenate([e1, e2]).astype(int).astype(bool)
    g = np.concatenate([np.zeros(len(t1)), np.ones(len(t2))]).astype(int)
    O, E, V = 0.0, 0.0, 0.0
    for u in np.unique(t[e]):
        at = t >= u
        n, n1 = at.sum(), (at & (g == 0)).sum()
        d = int(((t == u) & e).sum())
        d1 = int(((t == u) & e & (g == 0)).sum())
        if n == 0:
            continue
        O += d1
        E += d * n1 / n
        if n > 1:
            V += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
    stat = (O - E) ** 2 / V if V > 0 else 0.0
    return {"statistic": float(stat), "p_value": float(chi2.sf(stat, 1))}


def cox_ph(X, times, events, names=None, ridge=0.01):
    """Cox proportional hazards by the Breslow partial likelihood. X is
    (n, p); columns are standardised internally and coefficients reported
    on the original scale. Returns lists (coef, hazard_ratio, se, z,
    p_value, hr_ci) in column order, plus n, events and converged."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=int).astype(bool)
    n, p = X.shape
    names = names or [f"x{j}" for j in range(p)]
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    order = np.argsort(-t, kind="stable")
    t, e, Z = t[order], e[order], Z[order]
    last = {}
    for i in range(n):
        last[t[i]] = i
    idx = np.array([last[ti] for ti in t])

    def nll_grad_hess(beta):
        eta = Z @ beta
        w = np.exp(eta)
        S0 = np.cumsum(w)
        S1 = np.cumsum(w[:, None] * Z, axis=0)
        S2 = np.cumsum(w[:, None, None] * (Z[:, :, None] * Z[:, None, :]), axis=0)
        ll, g, H = 0.0, np.zeros(p), np.zeros((p, p))
        for i in np.where(e)[0]:
            k = idx[i]
            ll += eta[i] - np.log(S0[k])
            m1 = S1[k] / S0[k]
            g += Z[i] - m1
            H -= S2[k] / S0[k] - np.outer(m1, m1)
        # a small ridge penalty on the standardised coefficients keeps a
        # sparse or collinear design from running off to infinity
        ll -= 0.5 * ridge * float(beta @ beta)
        g -= ridge * beta
        H -= ridge * np.eye(p)
        return -ll, -g, -H

    beta, converged = np.zeros(p), False
    for _ in range(60):
        f, g, H = nll_grad_hess(beta)
        try:
            step = np.linalg.solve(H + 1e-8 * np.eye(p), g)
        except np.linalg.LinAlgError:
            break
        # damped Newton step
        lam = 1.0
        while lam > 1e-4:
            cand = beta - lam * step
            if nll_grad_hess(cand)[0] <= f + 1e-12:
                break
            lam *= 0.5
        beta_new = cand
        if np.max(np.abs(beta_new - beta)) < 1e-7:
            beta, converged = beta_new, True
            break
        beta = beta_new
    f, g, H = nll_grad_hess(beta)
    cov = np.linalg.pinv(H)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    coef = beta / sd
    se_o = se / sd
    z = np.where(se_o > 0, coef / np.where(se_o > 0, se_o, 1.0), 0.0)
    def _ex(x):
        return float(np.exp(np.clip(x, -30.0, 30.0)))      # a hazard ratio beyond e^30 is a degenerate fit, not a number
    hr = np.array([_ex(c) for c in coef])
    ci = [[_ex(c - 1.96 * s), _ex(c + 1.96 * s)] for c, s in zip(coef, se_o)]
    hr_std = np.array([_ex(b_) for b_ in beta])   # per standard deviation of the covariate
    ci_std = [[_ex(b_ - 1.96 * s), _ex(b_ + 1.96 * s)] for b_, s in zip(beta, se)]
    return {"names": names, "coef": coef.tolist(), "hazard_ratio": hr.tolist(), "se": se_o.tolist(),
            "hazard_ratio_per_sd": hr_std.tolist(), "hr_ci_per_sd": ci_std,
            "z": z.tolist(), "p_value": (2 * norm.sf(np.abs(z))).tolist(), "hr_ci": ci,
            "n": int(n), "events": int(e.sum()), "converged": bool(converged),
            "ridge": float(ridge), "stable": bool(np.max(np.abs(beta)) < 10.0),
            "log_partial_likelihood": float(-f)}


def weibull_fit(times, events):
    """Weibull MLE with right censoring: scale and shape."""
    t = np.maximum(np.asarray(times, dtype=float), 1e-9)
    e = np.asarray(events, dtype=int).astype(bool)

    def nll(theta):
        lam, k = np.exp(theta)
        z = (t / lam) ** k
        return -(np.sum(e * (np.log(k / lam) + (k - 1) * np.log(t / lam))) - np.sum(z))

    r = minimize(nll, np.log([max(t.mean(), 1e-3), 1.0]), method="Nelder-Mead")
    lam, k = np.exp(r.x)
    return {"scale": float(lam), "shape": float(k), "n": int(len(t)), "events": int(e.sum())}


def survival_analysis(specs, cache, rule_event_times, sentinel_names, threshold=DISLOCATION_DD):
    """Time to dislocation by arm (untreated and each rule) over the
    calibration herding scenarios, with a Cox model against the untreated
    reference adjusted for the dominant vendor's share and correlation;
    and the pre emption record of each sentinel."""
    herd = [sp for sp in specs if not sp.quiet and not sp.holdout and sp.name in cache]
    horizon = {sp.name: int(sp.t_steps - max(0, (sp.shock_time or 1) - 1)) for sp in herd}
    arms = {"untreated": {sp.name: time_to_dislocation(cache[sp.name]["res"], threshold) for sp in herd}}
    for rule_name, d in (rule_event_times or {}).items():
        arms[rule_name] = {k: v for k, v in d.items() if k in horizon}
    km = {}
    rows_t, rows_e, rows_x, arm_names = [], [], [], []
    for arm, d in arms.items():
        times = [horizon[s] if te[0] is None else te[0] for s, te in d.items()]
        events = [te[1] for te in d.values()]
        if not times:
            continue
        k = kaplan_meier(times, events)
        km[arm] = {"times": k["times"], "survival": k["survival"], "median": k["median"],
                   "events": k["events"], "n": k["n"],
                   "survival_at_20": survival_at(k, 20), "survival_at_60": survival_at(k, 60),
                   "weibull": weibull_fit(times, events) if k["events"] >= 3 else None}
        for s, te in d.items():
            sp = next(x for x in herd if x.name == s)
            rows_t.append(horizon[s] if te[0] is None else te[0]); rows_e.append(te[1])
            rows_x.append([1.0 if arm == a else 0.0 for a in arms if a != "untreated"] +
                          [max(sp.vendor_shares) if sp.vendor_shares else 0.0,
                           max(sp.vendor_rhos) if sp.vendor_rhos else 0.0])
        arm_names.append(arm)
    # log rank test of each arm against the untreated market
    base_d = arms.get("untreated", {})
    bt = np.array([horizon[k] if te[0] is None else te[0] for k, te in base_d.items()], dtype=float)
    be = np.array([te[1] for te in base_d.values()], dtype=int)
    for arm, d in arms.items():
        if arm == "untreated" or arm not in km:
            continue
        at = np.array([horizon[k] if te[0] is None else te[0] for k, te in d.items()], dtype=float)
        ae = np.array([te[1] for te in d.values()], dtype=int)
        km[arm]["logrank_vs_untreated"] = logrank_test(bt, be, at, ae) if len(at) and len(bt) else None
    cox = None
    covariates = [a for a in arms if a != "untreated"] + ["dominant_share", "dominant_rho"]
    if sum(rows_e) >= 5 and len(arms) >= 2:
        X = np.array(rows_x)
        keep = [j for j in range(X.shape[1]) if X[:, j].std() > 0]
        try:
            fit = cox_ph(X[:, keep], rows_t, rows_e, [covariates[j] for j in keep])
            # binary arm indicators keep the per unit hazard ratio; the continuous
            # covariates are reported per standard deviation so a share that only
            # spans 0.2 to 0.4 does not produce a per unit ratio in the billions
            cont = {"dominant_share", "dominant_rho"}
            hr = {n: (h_sd if n in cont else h) for n, h, h_sd in zip(fit["names"], fit["hazard_ratio"],
                                                                     fit["hazard_ratio_per_sd"])}
            hr_ci = {n: (c_sd if n in cont else c) for n, c, c_sd in zip(fit["names"], fit["hr_ci"],
                                                                        fit["hr_ci_per_sd"])}
            cox = {"covariates": fit["names"], "hazard_ratio": hr, "hr_ci": hr_ci,
                   "continuous_per_sd": sorted(cont & set(fit["names"])),
                   "p_value": dict(zip(fit["names"], fit["p_value"])),
                   "n": fit["n"], "events": fit["events"], "converged": fit["converged"],
                   "stable": fit["stable"], "reference": "untreated"}
        except Exception:  # noqa: BLE001 - a degenerate design is reported as absent
            cox = None
    sentinel_alerts = {}
    for name in sentinel_names:
        steps, before = [], 0
        for sp in herd:
            out = cache[sp.name]["outs"].get(name)
            if out is None:
                continue
            fa = out["first_alert"]
            steps.append(float(fa) if fa is not None else float(sp.t_steps))
            before += int(fa is not None and sp.shock_time is not None and fa < sp.shock_time)
        if steps:
            k = kaplan_meier(steps, [1 if s < sp.t_steps else 0 for s in steps])
            sentinel_alerts[name] = {"n": len(steps), "alerts_before_shock": before,
                                     "pre_emption_probability": float(before / len(steps)),
                                     "median_alert_step": k["median"]}
    return {"threshold": float(threshold), "arms": list(km), "kaplan_meier": km, "cox": cox,
            "sentinel_alerts": sentinel_alerts, "n_scenarios": len(herd)}
