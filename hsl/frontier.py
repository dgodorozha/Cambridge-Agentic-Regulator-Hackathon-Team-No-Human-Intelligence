"""Supervisory cost frontier.

A ranking by decision F1 or by containment hides a policy choice: how much
a false alert (or a false halt) costs relative to a missed herd (or an
uncontained dislocation). Decision focused evaluation (Wilder, Dilkina and
Tambe 2019; Mandi and others 2024) scores a tool by the loss of the
decision it informs. HSL exposes that loss as a function of one declared
number, c, the weight on the cost side:

  sentinel loss  L(c) = c * false alert rate + (1 - c) * (1 - recall)
  rule loss      L(c) = c * false halt rate  + (1 - c) * dislocation probability after treatment

and sweeps c from 0 to 1. The frontier lists the intervals of c on which
each tool is optimal and the crossover points, so the supervisor sees which
choice depends on a cost she has to own, and which does not. The loss at
the declared c is what the briefing quotes.
"""

import numpy as np


def _frontier(losses, grid):
    """losses: dict name -> array over grid. Returns segments of optimality."""
    names = list(losses)
    L = np.vstack([losses[n] for n in names])
    best = np.argmin(L, axis=0)
    segments = []
    start = 0
    for i in range(1, len(grid) + 1):
        if i == len(grid) or best[i] != best[start]:
            segments.append({"tool": names[best[start]], "c_from": float(grid[start]),
                             "c_to": float(grid[i - 1])})
            start = i
    return segments


def sentinel_frontier(summary, c_declared=0.5, n_grid=101):
    grid = np.linspace(0.0, 1.0, n_grid)
    losses = {}
    for n, v in summary.items():
        fa = v.get("false_alert_rate")
        fa = 0.0 if fa is None else fa
        miss = 1.0 - (v.get("recall") or 0.0)
        losses[n] = grid * fa + (1.0 - grid) * miss
    segs = _frontier(losses, grid)
    at = {n: float(np.interp(c_declared, grid, losses[n])) for n in losses}
    return {"c_declared": float(c_declared), "loss_at_declared": at,
            "best_at_declared": min(at, key=at.get) if at else None,
            "segments": segs, "n_switches": max(0, len(segs) - 1),
            "definition": "c times false alert rate plus (1 - c) times (1 - recall)"}


def rule_frontier(rules, c_declared=0.5, n_grid=101):
    grid = np.linspace(0.0, 1.0, n_grid)
    losses = {}
    for n, v in rules.items():
        fh = v.get("false_halt_rate")
        fh = 0.0 if fh is None else fh
        pc = v.get("crash_prob_treated")
        pc = 1.0 if pc is None else pc
        losses[n] = grid * fh + (1.0 - grid) * pc
    segs = _frontier(losses, grid)
    at = {n: float(np.interp(c_declared, grid, losses[n])) for n in losses}
    return {"c_declared": float(c_declared), "loss_at_declared": at,
            "best_at_declared": min(at, key=at.get) if at else None,
            "segments": segs, "n_switches": max(0, len(segs) - 1),
            "definition": "c times false halt rate plus (1 - c) times dislocation probability after treatment"}
