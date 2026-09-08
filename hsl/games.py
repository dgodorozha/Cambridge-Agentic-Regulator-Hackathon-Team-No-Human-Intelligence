"""The certification as a game between the sentinel and an adversary.

The red team search returns the worst evasion for the certified sentinel.
A supervisor choosing among sentinels faces a matrix game: rows are
sentinels, columns are evasion strategies, entries are decision F1 (the
supervisor's payoff; the adversary's loss). The maximin pure strategy is
the sentinel whose worst column is best (von Neumann 1928); the mixed
strategy value, solved as a linear programme, is what a supervisor who
randomises which sentinel is armed could guarantee, an idea familiar from
minimax search and self play in game AI (the RL Games labs) and from
security games. The gap between the two says how much unpredictability
is worth against an adaptive adversary.
"""

import numpy as np
from scipy.optimize import linprog


def matrix_game(payoff, row_names, col_names):
    """payoff: rows = supervisor choices, columns = adversary choices,
    higher is better for the supervisor. Returns the maximin pure
    strategy, the minimax pure counter, and the mixed strategy value with
    the supervisor's optimal mixture."""
    A = np.asarray(payoff, dtype=float)
    m, n = A.shape
    row_min = A.min(axis=1)
    col_max = A.max(axis=0)
    maximin_i = int(np.argmax(row_min))
    minimax_j = int(np.argmin(col_max))
    # LP: maximise v subject to sum_i x_i A[i, j] >= v for all j, sum x = 1, x >= 0
    c = np.zeros(m + 1); c[-1] = -1.0
    A_ub = np.hstack([-A.T, np.ones((n, 1))])
    b_ub = np.zeros(n)
    A_eq = np.zeros((1, m + 1)); A_eq[0, :m] = 1.0
    bounds = [(0, 1)] * m + [(None, None)]
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if r.success:
        x = r.x[:m]; value = float(r.x[-1])
    else:
        x = np.eye(m)[maximin_i]; value = float(row_min[maximin_i])
    mixture = {row_names[i]: float(x[i]) for i in range(m) if x[i] > 1e-6}
    return {"rows": row_names, "cols": col_names, "payoff": A.tolist(),
            "maximin_pure": row_names[maximin_i], "maximin_value": float(row_min[maximin_i]),
            "minimax_pure_col": col_names[minimax_j], "minimax_value": float(col_max[minimax_j]),
            "mixed_value": value, "mixture": mixture,
            "value_of_mixing": float(value - row_min[maximin_i]),
            "saddle_point": bool(abs(row_min[maximin_i] - col_max[minimax_j]) < 1e-9)}


def game_from_trials(red, sentinel_names):
    """Build the sentinel by evasion game from the red team trials that
    dislocated (an evasion that makes the herd harmless is not a threat)."""
    trials = [t for t in red.get("trials", []) if t.get("dislocates") and t.get("f1_all")]
    if len(trials) < 2:
        return None
    cols = [f"trial {t['k']} (cohorts {int(t['params']['evader_cohorts'])}, period "
            f"{int(t['params']['evader_period'])}, rho {t['params']['rho']:.2f}, share {t['params']['share']:.2f})"
            for t in trials]
    rows = [s for s in sentinel_names if all(s in t["f1_all"] for t in trials)]
    A = np.array([[t["f1_all"][s] for t in trials] for s in rows])
    g = matrix_game(A, rows, cols)
    g["n_trials"] = len(trials)
    g["battery_certified"] = red.get("certified")
    g["certified_worst"] = float(A[rows.index(red["certified"])].min()) if red.get("certified") in rows else None
    return g
