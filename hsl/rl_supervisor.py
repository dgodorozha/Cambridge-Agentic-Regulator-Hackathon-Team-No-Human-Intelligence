"""A learned intervention policy, and off policy evaluation of every rule.

Model based reinforcement learning (ST455 lecture 9; Sutton and Barto
2018, chapter 8): log transitions under a behaviour policy, fit a tabular
model of the market's response to intervention, solve it by value
iteration and read off the greedy policy. The state is what a market
wide breaker could observe at the time: a bucket of recent volatility
relative to normal, a bucket of the drawdown from the recent peak and
whether the market is currently halted. The actions are none, throttle
the whole market to half size, or halt. The reward per step is minus the
increase in drawdown, minus a declared cost for each step halted and each
step throttled, so the policy trades containment against interruption at
a price the supervisor sets. The result is a rule like any other and is
scored by the same harness, in sample and on the held out family. It is
advisory; nothing here trades.

Off policy evaluation (ST455 lecture 11; Precup, Sutton and Singh 2000;
Jiang and Li 2016; Thomas and Brunskill 2016) answers the question a
pilot with logged data would face: what would this rule have done, using
only trajectories collected under some other policy? HSL estimates the
value of every rule from the logged behaviour trajectories by per
decision importance sampling and by a doubly robust estimator that uses
the fitted model's value function as the control variate, then compares
each estimate with the on policy value the sandbox can simulate. The gap
is the audit: it says how far a supervisor could trust an offline
estimate before deploying a rule.
"""

import numpy as np

from .simulator import simulate

ACTIONS = ("none", "throttle", "halt")
N_VOL, N_DD = 4, 4
N_STATES = N_VOL * N_DD * 2


def _state(returns, prices, sigma, halted, w=25):
    if len(returns) < 5:
        v, dd = 0, 0
    else:
        vol = returns[-w:].std() / max(sigma, 1e-9)
        v = 0 if vol < 1.5 else (1 if vol < 2.5 else (2 if vol < 4.0 else 3))
        p = np.exp(prices[-80:])
        d = 1.0 - p[-1] / p.max()
        dd = 0 if d < 0.03 else (1 if d < 0.07 else (2 if d < 0.12 else 3))
    return (v * N_DD + dd) * 2 + (1 if halted else 0)


def _apply(action, n_agents):
    if action == 1:
        return {"throttle": np.full(n_agents, 0.5)}
    if action == 2:
        return {"halt": True}
    return {}


class PolicyRule:
    """Wraps a tabular policy (or a fixed action rule) as an intervention."""

    def __init__(self, policy, sigma, name="learned_policy", label="Learned policy (model based)"):
        self.policy, self.sigma, self.name, self.label = policy, sigma, name, label
        self.targeted = False
        self._halted = False

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._halted = False

        def rule(t, state):
            s = _state(state["returns"], state["prices"], self.sigma, self._halted)
            a = int(self.policy[s])
            self._halted = a == 2
            return _apply(a, n_agents)
        return rule


class LearnedPolicyRule:
    """Rule class for the evaluation harness. `policy` is set by the
    pipeline after training; until then it is the do nothing policy."""
    name = "learned_policy"
    label = "Learned policy (model based RL)"
    targeted = False
    policy = np.zeros(N_STATES, dtype=int)
    sigma = 0.01

    def __init__(self):
        self._impl = PolicyRule(type(self).policy, type(self).sigma)

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        return self._impl.make(n_agents, flags_online, sentinel_flags)


def _behaviour(rng, s, eps=0.3, base=None):
    """Epsilon soft behaviour policy: with probability 1 - eps follow the
    base policy (do nothing by default), otherwise act uniformly."""
    p = np.full(3, eps / 3.0)
    b = int(base[s]) if base is not None else 0
    p[b] += 1.0 - eps
    return p


def log_trajectories(specs, c_halt=0.02, c_throttle=0.005, eps=0.3, seed=0, stop=None):
    """Simulate each scenario under the behaviour policy and log (s, a, r,
    s', b(a|s)) per step. Rewards are minus the drawdown increase and the
    declared interruption costs."""
    rng = np.random.default_rng(seed)
    trajectories = []
    for sp in specs:
        traj = []
        halted = {"v": False}
        rec = {"s": None, "a": None, "p": None}

        def rule(t, state):
            s = _state(state["returns"], state["prices"], sp.sigma, halted["v"])
            probs = _behaviour(rng, s, eps)
            a = int(rng.choice(3, p=probs))
            halted["v"] = a == 2
            rec["s"], rec["a"], rec["p"] = s, a, float(probs[a])
            traj.append([s, a, 0.0, float(probs[a]), t])
            return _apply(a, sp.n_agents)

        res = simulate(sp, intervention=rule, stop=stop)
        p = np.exp(res.prices)
        peak = np.maximum.accumulate(p)
        dd = (peak - p) / peak
        for _k, row in enumerate(traj):
            t = row[4]
            inc = max(0.0, dd[t] - dd[t - 1]) if t >= 1 else 0.0
            cost = c_halt * (row[1] == 2) + c_throttle * (row[1] == 1)
            row[2] = -inc - cost
        trajectories.append({"scenario": sp.name, "quiet": sp.quiet, "steps": traj})
    return trajectories


def fit_model(trajectories):
    """Tabular maximum likelihood model: transition counts and mean rewards.
    Unseen state action pairs keep the state (self loop) with reward zero."""
    N = np.zeros((N_STATES, 3, N_STATES))
    R = np.zeros((N_STATES, 3)); C = np.zeros((N_STATES, 3))
    for tr in trajectories:
        steps = tr["steps"]
        for k in range(len(steps) - 1):
            s, a, r = steps[k][0], steps[k][1], steps[k][2]
            s2 = steps[k + 1][0]
            N[s, a, s2] += 1; R[s, a] += r; C[s, a] += 1
    P = np.zeros_like(N)
    for s in range(N_STATES):
        for a in range(3):
            if C[s, a] > 0:
                P[s, a] = N[s, a] / C[s, a]
                R[s, a] /= C[s, a]
            else:
                P[s, a, s] = 1.0
    return {"P": P, "R": R, "counts": C}


def value_iteration(model, gamma=0.97, iters=500):
    P, R = model["P"], model["R"]
    V = np.zeros(N_STATES)
    for _ in range(iters):
        Q = R + gamma * P @ V
        V_new = Q.max(axis=1)
        if np.max(np.abs(V_new - V)) < 1e-9:
            V = V_new
            break
        V = V_new
    Q = R + gamma * P @ V
    return Q.argmax(axis=1).astype(int), V, Q


def ope_estimates(trajectories, target, model, gamma=0.97, cap=100.0, cap_dr=3.0):
    """Three off policy estimates of a target policy's value from the
    logged trajectories: per decision importance sampling, a doubly robust
    estimator with per step weights clipped at `cap_dr` (Jiang and Li 2016;
    Thomas and Brunskill 2016) and the value under the fitted model alone.
    `target` is a (states, 3) matrix of action probabilities (a
    deterministic policy is one hot)."""
    T = _as_matrix(target)
    Vq = value_iteration_for(model, T, gamma) if model is not None else None
    pdis, dr, mb = [], [], []
    for tr in trajectories:
        steps = tr["steps"]
        rho, v_pdis, disc = 1.0, 0.0, 1.0
        for (s, a, rwd, b, _t) in steps:
            rho = min(cap, rho * T[s, a] / max(b, 1e-9))
            v_pdis += disc * rho * rwd
            disc *= gamma
            if rho == 0.0:
                break
        pdis.append(v_pdis)
        if Vq is not None:
            V, Q = Vq
            v = 0.0
            for k in range(len(steps) - 1, -1, -1):
                s, a, rwd, b, t = steps[k]
                w = min(cap_dr, T[s, a] / max(b, 1e-9))
                v = V[s] + w * (rwd + gamma * v - Q[s, a])
            dr.append(v)
            mb.append(float(V[steps[0][0]]))
    return {"pdis": float(np.mean(pdis)) if pdis else None,
            "dr": float(np.mean(dr)) if dr else None,
            "model": float(np.mean(mb)) if mb else None, "n_trajectories": len(pdis)}


def _as_matrix(target):
    target = np.asarray(target)
    if target.ndim == 1:
        M = np.zeros((N_STATES, 3)); M[np.arange(N_STATES), target.astype(int)] = 1.0
        return M
    return target


def value_iteration_for(model, target, gamma=0.97, iters=500):
    """Policy evaluation on the fitted model for a (possibly stochastic)
    target policy. Returns (V, Q)."""
    T = _as_matrix(target)
    P, R = model["P"], model["R"]
    V = np.zeros(N_STATES)
    for _ in range(iters):
        Q = R + gamma * P @ V
        V_new = (T * Q).sum(axis=1)
        if np.max(np.abs(V_new - V)) < 1e-9:
            V = V_new
            break
        V = V_new
    Q = R + gamma * P @ V
    return V, Q


def on_policy_value(specs, rule_factory, c_halt=0.02, c_throttle=0.005, gamma=0.97, stop=None):
    """Simulate the target rule on the scenarios and compute the same
    discounted reward the logged data uses, per step."""
    vals = []
    for sp in specs:
        acts = []
        inner = rule_factory(sp)

        def rule(t, state):
            out = inner(t, state) if inner is not None else {}
            a = 2 if out.get("halt") else (1 if "throttle" in out and float(np.mean(out["throttle"])) < 0.999 else 0)
            acts.append((t, a))
            return out

        res = simulate(sp, intervention=rule, stop=stop)
        p = np.exp(res.prices); peak = np.maximum.accumulate(p); dd = (peak - p) / peak
        v, disc = 0.0, 1.0
        for t, a in acts:
            inc = max(0.0, dd[t] - dd[t - 1]) if t >= 1 else 0.0
            v += disc * (-inc - (c_halt if a == 2 else 0.0) - (c_throttle if a == 1 else 0.0))
            disc *= gamma
        vals.append(v)
    return float(np.mean(vals)) if vals else None


def library_as_policy(rule_class, specs, sigma, floor=0.02):
    """Distil a library rule into the tabular state space as a stochastic
    policy: the frequency of each action it took in each state over the
    runs, with a small floor so the importance weights stay finite. Rules
    that act on sentinel flags are approximated as they behave with no
    flags (market wide behaviour)."""
    counts = np.zeros((N_STATES, 3))
    for sp in specs:
        inst = rule_class()
        inner = inst.make(sp.n_agents)
        halted = {"v": False}

        def rule(t, state):
            s = _state(state["returns"], state["prices"], sp.sigma, halted["v"])
            out = inner(t, state)
            a = 2 if out.get("halt") else (1 if "throttle" in out and float(np.mean(out["throttle"])) < 0.999 else 0)
            halted["v"] = a == 2
            counts[s, a] += 1
            return out
        simulate(sp, intervention=rule)
    probs = counts + floor
    probs[counts.sum(axis=1) == 0] = np.array([1.0, 0.0, 0.0]) + floor   # unseen states: do nothing
    probs = probs / probs.sum(axis=1, keepdims=True)
    return probs, counts


def train_and_evaluate(specs, rule_classes, c_halt=0.02, c_throttle=0.005, eps=0.3, gamma=0.97,
                       seed=0, stop=None):
    """Full loop: log behaviour trajectories on the calibration scenarios,
    fit the model, solve for the learned policy, then off policy evaluate
    the learned policy and each library rule and compare with the
    simulated on policy value."""
    sigma = specs[0].sigma
    traj = log_trajectories(specs, c_halt, c_throttle, eps, seed, stop)
    model = fit_model(traj)
    policy, V, Q = value_iteration(model, gamma)
    LearnedPolicyRule.policy = policy
    LearnedPolicyRule.sigma = sigma
    coverage = float(np.mean(model["counts"].sum(axis=1) > 0))
    estimates = {}
    targets = {"learned_policy": policy, "do_nothing": np.zeros(N_STATES, dtype=int)}
    factories = {"learned_policy": lambda sp: PolicyRule(policy, sigma).make(sp.n_agents),
                 "do_nothing": lambda sp: None}
    distilled = {}
    for R in rule_classes:
        if R.name == "learned_policy":
            continue
        probs, cnt = library_as_policy(R, specs[:6], sigma)
        distilled[R.name] = {"n_states_seen": int((cnt.sum(axis=1) > 0).sum()),
                             "action_share": (cnt.sum(axis=0) / max(cnt.sum(), 1)).tolist()}
        targets[R.name] = probs
        factories[R.name] = (lambda sp, R=R: R().make(sp.n_agents))
    for name, pol in targets.items():
        est = ope_estimates(traj, pol, model, gamma)
        on = on_policy_value(specs, factories[name], c_halt, c_throttle, gamma, stop)
        est["on_policy"] = on
        est["pdis_error"] = (None if (on is None or est["pdis"] is None) else float(est["pdis"] - on))
        est["dr_error"] = (None if (on is None or est["dr"] is None) else float(est["dr"] - on))
        est["model_error"] = (None if (on is None or est["model"] is None) else float(est["model"] - on))
        estimates[name] = est
    action_share = {ACTIONS[a]: float(np.mean(policy == a)) for a in range(3)}
    return {"policy": policy.tolist(), "state_space": {"vol_buckets": N_VOL, "dd_buckets": N_DD,
                                                       "halted_flag": 2, "n_states": N_STATES},
            "costs": {"halt_per_step": c_halt, "throttle_per_step": c_throttle},
            "gamma": gamma, "behaviour_eps": eps, "n_logged_trajectories": len(traj),
            "n_logged_steps": int(sum(len(t["steps"]) for t in traj)),
            "model_coverage": coverage, "action_share": action_share,
            "ope": estimates,
            "distilled": distilled,
            "best_estimator": min(("pdis", "dr", "model"), key=lambda k: float(np.mean(
                [abs(v[k + "_error"]) for v in estimates.values() if v.get(k + "_error") is not None]))),
            "mean_abs_error": {"pdis": float(np.mean([abs(v["pdis_error"]) for v in estimates.values()
                                                       if v.get("pdis_error") is not None])),
                               "dr": float(np.mean([abs(v["dr_error"]) for v in estimates.values()
                                                     if v.get("dr_error") is not None])),
                               "model": float(np.mean([abs(v["model_error"]) for v in estimates.values()
                                                        if v.get("model_error") is not None]))}}
