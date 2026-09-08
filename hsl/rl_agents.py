"""RL trading agents for HSL, built on the ST455 lecture notes.

Three agent families, spanning the course's method space:

  DoubleQTrader     Double Q-learning (Lecture 5, s1.3): two tabular Q
                    estimates, one selects the argmax action, the other
                    evaluates it, removing maximisation bias.
  SarsaLambdaTrader SARSA(lambda) with eligibility traces and linear
                    function approximation (Lecture 5, s1.2 and s2.2),
                    with a slowly updated target weight vector in the
                    spirit of DQN's stabilisation tricks (Lecture 7).
  A2CTrader         Advantage actor-critic (Lecture 8, s4): softmax policy
                    over discrete order sizes, linear TD(0) critic, the
                    advantage as the policy gradient signal, plus an
                    entropy bonus to delay premature convergence.

The population is trained independently, one learner per agent, on the same
execution reward inside a shared market environment whose price their own
aggregate flow moves. No correlation is imposed anywhere: because the
agents share the objective and the environment, their learned policies
converge, and herding EMERGES. That is the monoculture channel the FSB and
Bank of England describe, produced by learning rather than assumed via a
correlation parameter.

Integration surface for an external sandbox: implement ExternalPolicy
(reset/act on the observation dict) and return your policies from
an ExternalPolicy object (act, reset) and assign it via ScenarioSpec.rl_n.

Observation per step:
    {"momentum": float,   # standardised recent return, clipped to [-3,3]
     "vol": float,        # rolling volatility ratio vs baseline
     "inventory": float}  # the agent's cumulative signed flow
Action: float order flow (positive = buy).
"""

import numpy as np

ACTIONS = np.array([-1.5, -0.5, 0.0, 0.5, 1.5])


class ExternalPolicy:
    """Implement this to plug an external RL sandbox into HSL."""

    def reset(self, seed=None):
        raise NotImplementedError

    def act(self, obs: dict) -> float:
        raise NotImplementedError


def _mom_bucket(m):
    return int(np.clip(np.digitize(m, [-1.5, -0.5, 0.5, 1.5]), 0, 4))


def _inv_bucket(i):
    return int(np.clip(np.digitize(i, [-3.0, 3.0]), 0, 2))


def _features(obs, inventory):
    """Linear function approximation features (Lecture 5, s2): momentum,
    its square and sign, volatility, inventory and interactions."""
    m = float(np.clip(obs["momentum"], -3, 3)) / 3.0
    v = float(np.clip(obs.get("vol", 1.0), 0, 4)) / 4.0
    i = float(np.clip(inventory, -6, 6)) / 6.0
    return np.array([1.0, m, m * m, np.sign(m), v, i, m * v, m * i])


class DoubleQTrader(ExternalPolicy):
    """Double Q-learning (Lecture 5, s1.3). State: momentum x inventory
    buckets. On each update a coin flip decides which table is updated;
    the other evaluates the selected action."""

    def __init__(self, seed=0, alpha=0.15, gamma=0.9, eps=0.9):
        self.rng = np.random.default_rng(seed)
        self.QA = np.zeros((5, 3, len(ACTIONS)))
        self.QB = np.zeros((5, 3, len(ACTIONS)))
        self.alpha, self.gamma, self.eps = alpha, gamma, eps
        self.inventory = 0.0

    def reset(self, seed=None):
        self.inventory = 0.0

    def _state(self, obs):
        return _mom_bucket(obs["momentum"]), _inv_bucket(self.inventory)

    def act(self, obs):
        s = self._state(obs)
        if self.rng.random() < self.eps:
            a = int(self.rng.integers(len(ACTIONS)))
        else:
            a = int(np.argmax(self.QA[s] + self.QB[s]))
        self._last = (s, a)
        self.inventory = 0.7 * self.inventory + ACTIONS[a]
        return float(ACTIONS[a])

    def learn(self, obs_next, reward):
        s, a = self._last
        s2 = self._state(obs_next)
        if self.rng.random() < 0.5:
            a_star = int(np.argmax(self.QA[s2]))
            td = reward + self.gamma * self.QB[s2][a_star] - self.QA[s][a]
            self.QA[s][a] += self.alpha * td
        else:
            a_star = int(np.argmax(self.QB[s2]))
            td = reward + self.gamma * self.QA[s2][a_star] - self.QB[s][a]
            self.QB[s][a] += self.alpha * td


class SarsaLambdaTrader(ExternalPolicy):
    """SARSA(lambda) with accumulating eligibility traces over linear
    features (Lecture 5, s1.2 and s2.2). A target weight copy, refreshed
    every `target_every` updates, stabilises bootstrapping (Lecture 7)."""

    def __init__(self, seed=0, alpha=0.03, gamma=0.9, lam=0.8, eps=0.9,
                 target_every=200):
        self.rng = np.random.default_rng(seed)
        d = len(_features({"momentum": 0.0, "vol": 1.0}, 0.0))
        self.W = np.zeros((len(ACTIONS), d))
        self.W_target = self.W.copy()
        self.E = np.zeros_like(self.W)
        self.alpha, self.gamma, self.lam, self.eps = alpha, gamma, lam, eps
        self.target_every, self._updates = target_every, 0
        self.inventory = 0.0

    def reset(self, seed=None):
        self.inventory = 0.0
        self.E[:] = 0.0

    def _q(self, x, W=None):
        return (self.W if W is None else W) @ x

    def act(self, obs):
        x = _features(obs, self.inventory)
        if self.rng.random() < self.eps:
            a = int(self.rng.integers(len(ACTIONS)))
        else:
            a = int(np.argmax(self._q(x)))
        self._last = (x, a)
        self.inventory = 0.7 * self.inventory + ACTIONS[a]
        return float(ACTIONS[a])

    def learn(self, obs_next, reward):
        x, a = self._last
        x2 = _features(obs_next, self.inventory)
        if self.rng.random() < self.eps:
            a2 = int(self.rng.integers(len(ACTIONS)))
        else:
            a2 = int(np.argmax(self._q(x2)))
        td = reward + self.gamma * self._q(x2, self.W_target)[a2] - self._q(x)[a]
        self.E *= self.gamma * self.lam
        self.E[a] += x
        self.W += self.alpha * np.clip(td, -5, 5) * self.E
        self._updates += 1
        if self._updates % self.target_every == 0:
            self.W_target = self.W.copy()


class A2CTrader(ExternalPolicy):
    """Advantage actor-critic (Lecture 8, s4). Softmax policy over discrete
    order sizes with linear preferences; linear TD(0) critic supplies the
    advantage; entropy regularisation keeps exploration alive."""

    def __init__(self, seed=0, alpha_pi=0.02, alpha_v=0.05, gamma=0.9,
                 entropy=0.01):
        self.rng = np.random.default_rng(seed)
        d = len(_features({"momentum": 0.0, "vol": 1.0}, 0.0))
        self.theta = np.zeros((len(ACTIONS), d))
        self.w = np.zeros(d)
        self.alpha_pi, self.alpha_v = alpha_pi, alpha_v
        self.gamma, self.entropy = gamma, entropy
        self.inventory = 0.0
        self.eps = 0.0      # unused; exploration comes from the softmax

    def reset(self, seed=None):
        self.inventory = 0.0

    def _policy(self, x):
        z = self.theta @ x
        z -= z.max()
        p = np.exp(z)
        return p / p.sum()

    def act(self, obs):
        x = _features(obs, self.inventory)
        p = self._policy(x)
        a = int(self.rng.choice(len(ACTIONS), p=p))
        self._last = (x, a, p)
        self.inventory = 0.7 * self.inventory + ACTIONS[a]
        return float(ACTIONS[a])

    def learn(self, obs_next, reward):
        x, a, p = self._last
        x2 = _features(obs_next, self.inventory)
        td = reward + self.gamma * (self.w @ x2) - (self.w @ x)
        adv = np.clip(td, -5, 5)
        self.w += self.alpha_v * adv * x
        grad = -np.outer(p, x)
        grad[a] += x
        ent_grad = -np.outer(p * (np.log(p + 1e-9) + 1.0), x)
        self.theta += self.alpha_pi * (adv * grad + self.entropy * ent_grad)


def train_population(n_agents=48, episodes=30, t_steps=250, seed=0,
                     mix=(0.34, 0.33, 0.33)):
    """Train a mixed population (DoubleQ, SARSA(lambda), A2C) of independent
    learners on the same reward in a shared environment whose price their
    aggregate flow moves. Exploration is annealed across episodes."""
    rng = np.random.default_rng(seed)
    agents = []
    kinds = [DoubleQTrader, SarsaLambdaTrader, A2CTrader]
    counts = [int(round(m * n_agents)) for m in mix]
    counts[-1] = n_agents - sum(counts[:-1])
    k = 0
    for K, c in zip(kinds, counts):
        for _ in range(c):
            agents.append(K(seed=seed + 1000 + k)); k += 1
    kappa, sigma = 0.02, 0.003
    for ep in range(episodes):
        eps = max(0.05, 0.9 * (1 - ep / episodes))
        for ag in agents:
            ag.eps = eps
            ag.reset()
        returns = np.zeros(t_steps)
        vol_base = sigma
        mu = 0.0
        for t in range(1, t_steps):
            if rng.random() < 0.02:           # regime switching drift
                mu = rng.choice([-0.004, 0.0, 0.004])
            w0 = max(0, t - 20)
            seg = returns[w0:t]
            mom = seg.mean() / (seg.std() + 1e-6) if t > 5 else 0.0
            vol = seg.std() / vol_base if t > 5 else 1.0
            obs = {"momentum": float(np.clip(mom, -3, 3)), "vol": vol}
            acts = np.array([ag.act(obs) for ag in agents])
            r = 0.35 * returns[t - 1] + mu + kappa * acts.mean() \
                + sigma * rng.normal()
            # AR(1) persistence makes momentum genuinely predictive, so
            # momentum following is the optimal policy every learner can
            # discover independently
            returns[t] = r
            seg2 = returns[max(0, t - 19):t + 1]
            obs2 = {"momentum": float(np.clip(
                seg2.mean() / (seg2.std() + 1e-6), -3, 3)),
                "vol": seg2.std() / vol_base}
            for ag, a in zip(agents, acts):
                reward = a * r * 100 - 0.01 * ag.inventory ** 2
                ag.learn(obs2, reward)
    for ag in agents:
        ag.eps = 0.15   # residual exploration = execution noise at deployment
    return agents


_CACHE = {}


def get_trained_population(n_agents, seed=0):
    key = (n_agents, seed)
    if key not in _CACHE:
        _CACHE[key] = train_population(n_agents=n_agents, seed=seed)
    return _CACHE[key]




def policy_convergence(agents, grid=None):
    """Policy convergence in state space: for a grid of momentum states,
    each agent's expected action (softmax mean for A2C, greedy for value
    based methods). Returns mean pairwise correlation of action profiles
    (1 = identical policies) and the population mean slope of action
    against momentum (positive = momentum following, the herding channel)."""
    if grid is None:
        grid = np.linspace(-3, 3, 13)
    profiles = np.zeros((len(agents), len(grid)))
    for k, ag in enumerate(agents):
        for j, m in enumerate(grid):
            obs = {"momentum": float(m), "vol": 1.5}
            if isinstance(ag, A2CTrader):
                x = _features(obs, 0.0)
                profiles[k, j] = float(ag._policy(x) @ ACTIONS)
            elif isinstance(ag, SarsaLambdaTrader):
                x = _features(obs, 0.0)
                profiles[k, j] = float(ACTIONS[int(np.argmax(ag._q(x)))])
            else:
                sst = (_mom_bucket(m), 1)
                profiles[k, j] = float(ACTIONS[int(np.argmax(
                    ag.QA[sst] + ag.QB[sst]))])
    prof_std = profiles.std(axis=1)
    ok = prof_std > 1e-9
    C = np.corrcoef(profiles[ok]) if ok.sum() > 1 else np.array([[1.0]])
    iu = np.triu_indices_from(C, k=1)
    conv = float(np.nanmean(C[iu])) if len(iu[0]) else 0.0
    slopes = [np.polyfit(grid, p, 1)[0] for p in profiles]
    return {"policy_convergence": conv,
            "momentum_slope": float(np.mean(slopes)),
            "frac_active": float(ok.mean())}


def mean_action(agent, obs, tau=0.5):
    """Expected action under the agent's deployed policy: the position
    target it trades toward. A2C uses its own softmax; value based agents
    are deployed as Boltzmann (softmax over Q at temperature tau), the
    standard stochastic deployment of a learned Q function (Lecture 8)."""
    x = _features(obs, agent.inventory)
    if isinstance(agent, A2CTrader):
        return float(agent._policy(x) @ ACTIONS)
    if isinstance(agent, SarsaLambdaTrader):
        qv = agent._q(x)
    else:
        sst = (_mom_bucket(obs["momentum"]), _inv_bucket(agent.inventory))
        qv = agent.QA[sst] + agent.QB[sst]
    z = np.asarray(qv, dtype=float) / tau
    z -= z.max()
    p = np.exp(z); p /= p.sum()
    return float(p @ ACTIONS)
