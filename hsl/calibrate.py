"""Synthetic markets calibrated from the authority's own data.

Observed data cannot replace the synthetic markets, because decision
accuracy needs a ground truth that a real order book does not carry. It can
set the parameters of the markets that do carry one. This module fits the
simulator to an accepted dataset and turns the fit into scenario families:

  volatility     the standard deviation of observed log returns per step
  shock          the tail of the observed drawdown distribution over rolling
                 windows (the 90th percentile of window drawdowns), not the
                 single largest drop
  price impact   the regression of returns on the aggregate observed order
                 flow when per participant flows are present
  momentum       the window over which past returns best predict the next
                 return (the signal the vendor clusters read)
  reversion      the fraction of fundamentalists that reproduces the observed
                 speed of mean reversion toward a slow moving reference
  vendor split   groups of participants whose flows move together, from the
                 observed flow correlation matrix (Louvain communities on the
                 thresholded matrix): their shares and within group
                 correlations become the vendor shares and correlations

Every fitted value is clamped to the planner's bounds and the clamp is
reported. Two families follow. The calibrated family is a synthetic market
with the fitted parameters and the generator's ground truth, so decision
accuracy is measured as usual. The hybrid family lets the observed return
path drive the market as its news while synthetic agents respond to it and
to each other, so a rule is tested against real shocks with a known
population. The fitted parameters, the diagnostics and the family
definitions are written to the ledger.
"""

import hashlib

import networkx as nx
import numpy as np

from .ingest import price_series, _log_returns, participant_vendors, flow_matrix_with_meta
from .simulator import ScenarioSpec

BOUNDS = {"sigma": (0.002, 0.03), "shock": (0.01, 0.10), "kappa": (0.005, 0.03), "momentum_window": (5, 40),
          "frac_fundamental": (0.05, 0.40), "vendor_share": (0.05, 0.45), "vendor_rho": (0.20, 0.95)}
_OBSERVED = {}       # sha256 -> observed log returns, for the hybrid generator


def register_observed(sha, returns):
    _OBSERVED[sha] = np.asarray(returns, dtype=float)


def observed_returns(sha):
    if sha not in _OBSERVED:
        raise KeyError(f"observed series {sha[:12]} is not loaded; plan again with the dataset present")
    return _OBSERVED[sha]


def observed_snapshot():
    return {k: v.tolist() for k, v in _OBSERVED.items()}


def _clamp(name, v, notes):
    lo, hi = BOUNDS[name]
    c = float(min(hi, max(lo, v)))
    if c != v:
        notes.append(f"{name}: {v:.4g} clamped to {c:.4g}")
    return c


def flow_matrix(ds):
    """(times, participants) aggregate flow matrix and the price per time, or
    (None, None) without participant flows. One helper serves calibration
    and the backtests."""
    F, price, _ = flow_matrix_with_meta(ds)
    return F, price


def _window_drawdowns(prices, w=80):
    p = np.asarray(prices, dtype=float)
    out = []
    for a in range(0, max(1, len(p) - w), max(1, w // 4)):
        seg = p[a:a + w]
        peak = np.maximum.accumulate(seg)
        out.append(float(np.max((peak - seg) / peak)))
    return np.array(out) if out else np.array([0.0])


def calibrate(ds):
    """Fit the simulator's parameters to an accepted dataset. Returns the
    parameters, the diagnostics and the clamps; None if the data is too
    short."""
    prices = price_series(ds)
    r = _log_returns(prices)
    if len(r) < 60:
        return None
    notes = []
    sigma = _clamp("sigma", float(r.std()), notes)
    dds = _window_drawdowns(prices)
    shock = _clamp("shock", float(np.quantile(dds, 0.9)), notes)

    # momentum window: the past window whose standardised mean best predicts the next return
    best_w, best_c = 20, 0.0
    for w in (5, 10, 20, 40):
        if len(r) <= w + 10:
            continue
        sig = np.array([r[t - w:t].mean() / (r[t - w:t].std() + 1e-9) for t in range(w, len(r))])
        nxt = r[w:]
        c = float(np.corrcoef(sig, nxt)[0, 1]) if sig.std() > 0 and nxt.std() > 0 else 0.0
        if abs(c) > abs(best_c):
            best_w, best_c = w, c
    mom_w = int(_clamp("momentum_window", best_w, notes))

    # price impact and vendor split from participant flows
    F, _ = flow_matrix(ds)
    kappa, kappa_r2, n_parts = 0.015, None, 0
    vendors, vendor_rhos, vendor_notes = [], [], []
    split_source, observed_split = "not estimable", {}
    if F is not None and F.shape[0] >= 80 and F.shape[1] >= 5:
        n_parts = int(F.shape[1])
        q = F.mean(axis=1)
        q = q[1:len(r) + 1] if len(q) > len(r) else q[:len(r)]
        rr = r[:len(q)]
        if q.std() > 0:
            X = np.column_stack([np.ones_like(q), q])
            beta, *_ = np.linalg.lstsq(X, rr, rcond=None)
            fitted = X @ beta
            kappa_r2 = float(1 - ((rr - fitted) ** 2).sum() / max(((rr - rr.mean()) ** 2).sum(), 1e-12))
            if beta[1] > 0:
                kappa = _clamp("kappa", float(beta[1]), notes)
            else:
                vendor_notes.append("impact regression not positive; default impact kept")
        C = np.nan_to_num(np.corrcoef(F.T))
        vend = participant_vendors(ds)
        groups, split_source, observed_split = [], "inferred from flow communities", {}
        if vend:
            # observed split: participants grouped by the vendor they report
            by = {}
            for i, v in vend.items():
                if i < n_parts:
                    by.setdefault(v, []).append(i)
            for v, members in sorted(by.items(), key=lambda kv: -len(kv[1])):
                if len(members) < 2:
                    continue
                sub = C[np.ix_(members, members)]
                within = float((sub.sum() - len(members)) / max(1, len(members) * (len(members) - 1)))
                observed_split[v] = {"n_participants": len(members), "share": len(members) / n_parts,
                                     "within_correlation": within}
                groups.append((len(members) / n_parts, within))
            split_source = "observed from the vendor column"
            groups.sort(reverse=True)
        else:
            A = (np.abs(C) > 0.3).astype(float)
            np.fill_diagonal(A, 0)
            G = nx.from_numpy_array(A)
            comms = [sorted(c) for c in nx.community.louvain_communities(G, seed=0)] if G.number_of_edges() else []
            for c in comms:
                if len(c) < 3:
                    continue
                sub = C[np.ix_(c, c)]
                within = float((sub.sum() - len(c)) / max(1, len(c) * (len(c) - 1)))
                if within >= 0.3:
                    groups.append((len(c) / n_parts, within))
            groups.sort(reverse=True)
        for share, within in groups[:3]:
            vendors.append(_clamp("vendor_share", share, notes))
            vendor_rhos.append(_clamp("vendor_rho", within, notes))
        if sum(vendors) > 0.70:
            scale = 0.70 / sum(vendors)
            vendors = [v * scale for v in vendors]
            notes.append("vendor shares scaled to sum to 0.70")
        if not vendors:
            vendor_notes.append("no correlated group of three or more participants; default split kept"
                                if not vend else "no vendor with two or more participants; default split kept")
    else:
        split_source, observed_split = "not estimable", {}
        vendor_notes.append("no participant flows; impact and vendor split not estimable, defaults kept")
    if not vendors:
        vendors, vendor_rhos = [0.30, 0.15], [0.80, 0.30]

    # reversion: regress returns on the gap to a slow reference; map to the fundamentalist fraction
    ref_w = 50
    lp = np.log(np.asarray(prices, dtype=float))
    gap = np.array([lp[t - 1] - lp[max(0, t - ref_w):t].mean() for t in range(1, len(lp))])
    gap = gap[:len(r)]
    beta_rev = 0.0
    if gap.std() > 0:
        beta_rev = float(np.polyfit(gap, r[:len(gap)], 1)[0])
    # in the simulator each fundamentalist trades -1.5 * gap / 0.02 and impact is kappa per unit mean flow
    frac = -beta_rev * 0.02 / (1.5 * kappa) if beta_rev < 0 else 0.05
    frac = _clamp("frac_fundamental", float(frac), notes)

    params = {"sigma": sigma, "shock_size": shock, "kappa": kappa, "momentum_window": mom_w,
              "frac_fundamental": frac, "vendor_shares": [round(v, 3) for v in vendors],
              "vendor_rhos": [round(v, 3) for v in vendor_rhos]}
    diag = {"n_returns": int(len(r)), "n_participants": n_parts, "impact_r2": kappa_r2,
            "vendor_split_source": split_source, "observed_vendor_split": observed_split,
            "momentum_predictiveness": float(best_c), "reversion_coefficient": float(beta_rev),
            "drawdown_p90": float(np.quantile(dds, 0.9)), "drawdown_max": float(dds.max()),
            "notes": vendor_notes}
    sha = hashlib.sha256(str(sorted(params.items())).encode()).hexdigest()
    return {"params": params, "diagnostics": diag, "clamped": notes, "params_sha256": sha,
            "dataset_sha256": ds.get("sha256", "")}


def calibrated_family(ds, cal, n=2):
    """Synthetic markets with the fitted parameters and the generator's
    ground truth; scored like any calibration family."""
    if not cal:
        return []
    p = cal["params"]
    tag = ds.get("sha256", "")[:6] or "obs"
    return [ScenarioSpec(name=f"calibrated_{tag}_{s}", family=f"calibrated_{tag}",
                         vendor_shares=tuple(p["vendor_shares"]), vendor_rhos=tuple(p["vendor_rhos"]),
                         frac_fundamental=p["frac_fundamental"], kappa=p["kappa"], sigma=p["sigma"],
                         momentum_window=p["momentum_window"], shock_size=p["shock_size"],
                         seed=1300 + s) for s in range(n)]


def hybrid_family(ds, cal, n=2, max_steps=600):
    """The observed return path is the market's news; synthetic agents with
    the fitted structure respond to it and to each other. The shock time is
    the step of the largest observed drop, so post shock measures line up
    with the real event."""
    if not cal:
        return []
    prices = price_series(ds)
    r = _log_returns(prices)
    if len(r) < 120:
        return []
    r = r[:max_steps]
    sha = ds.get("sha256", "")
    register_observed(sha, r)
    p = cal["params"]
    t_shock = int(np.argmin(r))
    t_shock = int(min(max(50, t_shock), len(r) - 30))
    tag = sha[:6] or "obs"
    return [ScenarioSpec(name=f"hybrid_{tag}_{s}", family=f"hybrid_{tag}", generator="hybrid", hybrid_sha=sha,
                         t_steps=int(len(r)), shock_time=t_shock, shock_size=0.0,
                         vendor_shares=tuple(p["vendor_shares"]), vendor_rhos=tuple(p["vendor_rhos"]),
                         frac_fundamental=p["frac_fundamental"], kappa=p["kappa"], sigma=p["sigma"],
                         momentum_window=p["momentum_window"], seed=1400 + s) for s in range(n)]


def calibration_shift(rows, sentinel_names, calibrated_families, positives_present=True):
    """Kendall tau between the decision ranking on the demonstration herds
    and on the calibrated families; the authority's version of the truth
    dependence question."""
    from scipy.stats import kendalltau
    demo = [x for x in rows if not x["quiet"] and not x["holdout"] and x["family"] not in calibrated_families
            and not x["family"].startswith("hybrid_")]
    cal = [x for x in rows if x["family"] in calibrated_families]
    if not cal or not demo:
        return None

    def rank(sub):
        f = {n: float(np.mean([x["f1"] for x in sub if x["sentinel"] == n] or [0.0])) for n in sentinel_names}
        return f
    fd, fc = rank(demo), rank(cal)
    order_d = sorted(fd, key=fd.get, reverse=True)
    order_c = sorted(fc, key=fc.get, reverse=True)
    tau = float(kendalltau([fd[n] for n in sentinel_names], [fc[n] for n in sentinel_names])[0])
    return {"families": sorted(calibrated_families), "ranking_demonstration": order_d, "ranking_calibrated": order_c,
            "tau": (tau if tau == tau else 0.0) if positives_present else None,
            "rank_one_preserved": bool(order_d[0] == order_c[0]) if positives_present else None,
            "positives_present": bool(positives_present),
            "decision_f1_calibrated": fc, "decision_f1_demonstration": fd,
            "n_calibrated_rows": len(cal)}
