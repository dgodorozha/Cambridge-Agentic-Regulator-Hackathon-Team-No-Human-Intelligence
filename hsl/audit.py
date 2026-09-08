"""Two audits that ask whether the battery's conclusions survive a change
of world.

Truth dependence. "Accurate Networks, Wrong Banks" shows that the ordering
of reconstruction methods depends on which generator is designated the
truth. The same question applies to sentinels: a tool certified on the
shared signal generator may not rank the same when herding arises by
imitation (Kirman 1993; Lux and Marchesi 1999) or when price impact is
concave (the square root law of Bouchaud, Farmer and Lillo 2009 and Toth
and others 2011). The audit re runs a reduced battery under each
generator, ranks the sentinels by decision F1 under each, and reports the
rank correlation with the default ranking and the largest rank shift of
any tool. A tool that holds rank one under every generator is a safer
certification than one that does not.

Concentration dose response. Meng and Chen (2026, arXiv:2604.03272), the
paper the problem statement cites, derive a systemic risk coupling that is
convex in the AI adoption share, so the amplification multiplier grows
superlinearly with concentration. The audit sweeps the dominant vendor's
share, holding correlation fixed, and reports the post shock drawdown, the
dislocation probability and the curvature of the fitted response, with the
smallest share at which dislocations become the more likely outcome. It is
a test of the prediction inside the sandbox, not a claim about markets.
"""

import dataclasses

import numpy as np
from scipy.stats import kendalltau

from .evaluate import DISLOCATION_DD, score_row, summarise
from .simulator import ScenarioSpec, simulate

GENERATORS = ("shared_signal", "imitation", "voter", "sqrt_impact")


def _rank_stats(ranking_a, ranking_b):
    names = ranking_a
    pos_a = {n: i for i, n in enumerate(ranking_a)}
    pos_b = {n: i for i, n in enumerate(ranking_b)}
    shifts = {n: abs(pos_a[n] - pos_b[n]) for n in names}
    tau = float(kendalltau([pos_a[n] for n in names], [pos_b[n] for n in names])[0]) \
        if len(names) > 1 else 1.0
    return (tau if tau == tau else 0.0), shifts


def truth_dependence(specs, sentinel_classes, families=None, per_family=1, n_quiet=4,
                     stop=None, generators=GENERATORS):
    """Reduced battery under each generator: the first `per_family` scenario
    of each non held out herding family plus every calibration quiet
    scenario. Only the shared signal, imitation and square root generators
    are compared; scenarios whose own generator differs are skipped."""
    fams = families or sorted({s.family for s in specs if not s.quiet and not s.holdout
                               and s.generator == "shared_signal"})
    picked, seen, quiet_seen = [], {}, 0
    for sp in specs:
        if sp.holdout or sp.generator != "shared_signal":
            continue
        if sp.quiet:
            if quiet_seen < n_quiet:
                picked.append(sp)
                quiet_seen += 1
        elif sp.family in fams and seen.get(sp.family, 0) < per_family:
            picked.append(sp)
            seen[sp.family] = seen.get(sp.family, 0) + 1
    names = [S.name for S in sentinel_classes]
    per_gen = {}
    for gen in generators:
        rows = []
        for sp in picked:
            sp_g = dataclasses.replace(sp, generator=gen, name=f"{sp.name}@{gen}")
            res = simulate(sp_g, stop=stop)
            for S in sentinel_classes:
                out = S().run(res)
                rows.append(score_row(sp_g, res, S.name, out))
        summ, _ = summarise(rows, names, B=50)
        dec = {n: summ[n]["decision_f1"] for n in names if n in summ}
        fa = {n: summ[n]["false_alert_rate"] for n in names if n in summ}
        ranking = sorted(dec, key=dec.get, reverse=True)
        per_gen[gen] = {"decision_f1": dec, "false_alert_rate": fa, "ranking": ranking,
                        "mean_post_shock_dd": float(np.mean([r["post_shock_dd"] for r in rows
                                                             if r["post_shock_dd"] is not None]))}
    base = per_gen["shared_signal"]["ranking"]
    comp = {}
    for gen in generators:
        if gen == "shared_signal":
            continue
        tau, shifts = _rank_stats(base, per_gen[gen]["ranking"])
        comp[gen] = {"tau_vs_shared_signal": tau, "rank_shift": shifts,
                     "max_rank_shift": int(max(shifts.values())) if shifts else 0,
                     "rank_one_preserved": bool(per_gen[gen]["ranking"][0] == base[0])}
    stable = [n for n in names if all(per_gen[g]["ranking"][0] == n for g in generators)]
    return {"generators": list(generators), "per_generator": per_gen, "comparison": comp,
            "n_scenarios": len(picked), "families": fams,
            "rank_one_under_every_generator": stable[0] if stable else None,
            "max_rank_shift_any": int(max([c["max_rank_shift"] for c in comp.values()] or [0]))}


def concentration_sweep(shares=(0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50),
                        rho=0.85, seeds=(0, 1), base=None, stop=None):
    """Dose response of the dislocation to the dominant vendor's share at a
    fixed correlation. The quiet baseline is the same market with the vendor
    correlation below the destabilising threshold."""
    base = base or ScenarioSpec(name="dose", vendor_shares=(0.10, 0.15), vendor_rhos=(rho, 0.30),
                                shock_size=0.05)
    quiet_dd = []
    for s in seeds:
        q = dataclasses.replace(base, name=f"dose_quiet_{s}", vendor_rhos=(0.45, 0.30), seed=100 + s)
        quiet_dd.append(simulate(q, stop=stop).post_shock_drawdown())
    q0 = float(np.mean(quiet_dd))
    levels = []
    for sh in shares:
        dds = []
        for s in seeds:
            sp = dataclasses.replace(base, name=f"dose_{sh:.2f}_{s}", vendor_shares=(sh, 0.15),
                                     seed=100 + s)
            dds.append(simulate(sp, stop=stop).post_shock_drawdown())
        dds = np.array(dds)
        levels.append({"share": float(sh), "mean_post_shock_dd": float(dds.mean()),
                       "amplification": float(dds.mean() / max(q0, 1e-9)),
                       "dislocation_prob": float(np.mean(dds > DISLOCATION_DD))})
    x = np.array([l["share"] for l in levels])
    y = np.array([l["mean_post_shock_dd"] for l in levels])
    quad = np.polyfit(x, y, 2)
    lin = np.polyfit(x, y, 1)
    sse_q = float(((y - np.polyval(quad, x)) ** 2).sum())
    sse_l = float(((y - np.polyval(lin, x)) ** 2).sum())
    second_diff = np.diff(y, 2)
    thr = next((l["share"] for l in levels if l["dislocation_prob"] >= 0.5), None)
    return {"rho": float(rho), "seeds": list(seeds), "quiet_baseline_dd": q0,
            "levels": levels,
            "curvature": float(quad[0]), "convex": bool(quad[0] > 0),
            "share_of_positive_second_differences": float(np.mean(second_diff > 0)) if len(second_diff) else None,
            "r2_gain_quadratic_over_linear": float(1.0 - sse_q / max(sse_l, 1e-12)),
            "dislocation_threshold_share": thr,
            "dislocation_dd": DISLOCATION_DD,
            "prediction_tested": "Meng and Chen (2026): coupling convex in the adoption share"}
