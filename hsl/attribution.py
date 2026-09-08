"""Counterfactual attribution: which group of agents caused the dislocation.

The decision accuracy of version 2 scores a sentinel against a generative
ground truth (clusters above the correlation and share thresholds). A
supervisor may fairly ask for a behavioural ground truth instead: remove a
group from the market and see how much of the post shock drawdown goes
with it. That is the criterion of "Accurate Networks, Wrong Banks" (fail
each bank in turn and rank by impact), transported to agent groups.

Groups are the vendor clusters and, where present, the RL population, the
LLM persona group and the colluding manipulators. The characteristic
function of a coalition is the post shock drawdown of the market in which
every group outside the coalition is silenced (its orders scaled to zero
from the first step) under common random numbers, so the only difference
between runs is which groups trade. The Shapley value of a group is its
average marginal contribution over all orderings (Shapley 1953; Tarashev,
Borio and Tsatsaronis 2010 apply the same construct to attribute systemic
risk to institutions). Shapley values add up exactly to the drawdown of
the full market less that of the market with every group silenced, which
the critic checks.

The attribution also grades each sentinel on an impact ordering: the share
of its flags that land on the highest impact group, and the rank
correlation between its per group flag rates and the Shapley values.
"""

import itertools
import math

import numpy as np
from scipy.stats import kendalltau

from .simulator import simulate, class_label


def groups_of(res):
    """Attributable groups in a result: vendor clusters and the special
    populations. Noise traders and fundamentalists are the background."""
    out = {}
    for c in np.unique(res.agent_cluster):
        c = int(c)
        if c in (-1, -2):
            continue
        out[class_label(c)] = np.where(res.agent_cluster == c)[0]
    return out


def _silencer(n_agents, silenced_idx):
    scale = np.ones(n_agents)
    if len(silenced_idx):
        scale[silenced_idx] = 0.0

    def rule(t, state):
        return {"throttle": scale}
    return rule


def shapley_attribution(spec, res=None, max_groups=4):
    """Shapley values of post shock drawdown over agent groups of one
    scenario. Returns the values, the impact ordering, the coalition table
    and the efficiency residual (should be zero)."""
    res = res if res is not None else simulate(spec)
    groups = groups_of(res)
    names = list(groups)[:max_groups]
    if not names:
        return None
    n = spec.n_agents
    value = {}
    for k in range(len(names) + 1):
        for S in itertools.combinations(names, k):
            silenced = np.concatenate([groups[g] for g in names if g not in S]) \
                if len(S) < len(names) else np.array([], dtype=int)
            treated = simulate(spec, intervention=_silencer(n, silenced))
            value[S] = treated.post_shock_drawdown()
    full, empty = value[tuple(names)], value[()]
    phi = {}
    G = len(names)
    for g in names:
        others = [x for x in names if x != g]
        total = 0.0
        for k in range(len(others) + 1):
            for S in itertools.combinations(others, k):
                w = math.factorial(len(S)) * math.factorial(G - len(S) - 1) / math.factorial(G)
                with_g = tuple(x for x in names if x in S or x == g)
                total += w * (value[with_g] - value[tuple(x for x in names if x in S)])
        phi[g] = float(total)
    order = sorted(names, key=lambda g: phi[g], reverse=True)
    return {"scenario": spec.name, "groups": names,
            "group_size": {g: int(len(groups[g])) for g in names},
            "shapley": phi, "impact_ordering": order,
            "drawdown_full": float(full), "drawdown_all_silenced": float(empty),
            "efficiency_residual": float(sum(phi.values()) - (full - empty)),
            "coalitions": {"+".join(S) if S else "none": float(v) for S, v in value.items()}}


def sentinel_impact_scores(attr, res, outs):
    """For each sentinel output on the same scenario: share of flags on the
    top impact group and Kendall tau between per group flag rates and the
    Shapley values."""
    groups = groups_of(res)
    names = attr["groups"]
    top = attr["impact_ordering"][0]
    out = {}
    for sname, o in outs.items():
        flags = o["flags"]
        n_flag = int(flags.sum())
        rates = [float(flags[groups[g]].mean()) if len(groups[g]) else 0.0 for g in names]
        vals = [attr["shapley"][g] for g in names]
        tau = None
        if len(names) >= 2 and np.std(rates) > 0 and np.std(vals) > 0:
            tau = float(kendalltau(rates, vals)[0])
        out[sname] = {"share_of_flags_on_top_group": (float(flags[groups[top]].sum() / n_flag)
                                                      if n_flag else None),
                      "flag_rate_by_group": dict(zip(names, rates)),
                      "tau_flags_vs_impact": tau, "n_flagged": n_flag}
    return out


def attribute_battery(specs, cache, sentinel_names, families=None, per_family=1, max_groups=4):
    """Shapley attribution for the first `per_family` scenario of each listed
    herding family (default: every non quiet, non held out family), plus the
    sentinel impact scores. Returns a list, one entry per scenario, and a
    per sentinel mean of the impact scores."""
    fams = families or sorted({s.family for s in specs if not s.quiet and not s.holdout})
    done, entries = {}, []
    for sp in specs:
        if sp.quiet or sp.holdout or sp.family not in fams:
            continue
        if done.get(sp.family, 0) >= per_family:
            continue
        res, outs = cache[sp.name]["res"], cache[sp.name]["outs"]
        attr = shapley_attribution(sp, res, max_groups=max_groups)
        if attr is None:
            continue
        attr["sentinels"] = sentinel_impact_scores(attr, res,
                                                   {k: v for k, v in outs.items() if k in sentinel_names})
        attr["family"] = sp.family
        entries.append(attr)
        done[sp.family] = done.get(sp.family, 0) + 1
    by_sentinel = {}
    for s in sentinel_names:
        shares = [e["sentinels"][s]["share_of_flags_on_top_group"] for e in entries
                  if e["sentinels"][s]["share_of_flags_on_top_group"] is not None]
        taus = [e["sentinels"][s]["tau_flags_vs_impact"] for e in entries
                if e["sentinels"][s]["tau_flags_vs_impact"] is not None]
        by_sentinel[s] = {"mean_share_on_top_group": float(np.mean(shares)) if shares else None,
                          "mean_tau_flags_vs_impact": float(np.mean(taus)) if taus else None,
                          "n_scenarios": len(entries)}
    return {"scenarios": entries, "by_sentinel": by_sentinel,
            "n_scenarios": len(entries), "max_groups": max_groups}
