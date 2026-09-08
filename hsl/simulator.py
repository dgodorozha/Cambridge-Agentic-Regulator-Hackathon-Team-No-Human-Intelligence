"""Agent based market simulator for the Herding Scenario Lab (HSL).

Generates synthetic markets populated by noise traders, fundamentalists and
AI trading agents grouped into vendor clusters. Intra cluster correlation
(rho) and vendor monoculture share are parameterised, so scenario batteries
can sweep herding intensity. A fundamental shock can be injected mid run;
correlated momentum clusters amplify it into a dislocation.

Ground truth destabilising agents are defined generatively: members of
vendor clusters whose correlation and size place them above the
amplification threshold for the scenario. Sentinels never see these labels.

Version 2 additions (dynamics of version 1 scenarios are unchanged):
  * `evader_cohorts`: an adversarial family in which the dominant vendor
    cluster rotates trading cohorts so that pairwise flow correlation stays
    low while aggregate impact is preserved.
  * `holdout`: a held out family with a different population, shock timing
    and impact coefficient, never used to calibrate any sentinel or rule.
  * post shock drawdown and pre shock volatility, so containment measures
    the shock response rather than the whole path.
  * a cooperative `stop` event for the emergency stop.
  * `battery_hash()` so a gate approval binds to an exact battery.

Version 3 additions (dynamics of every version 1 and 2 scenario unchanged;
new agent classes and generators only draw random numbers when a scenario
switches them on):
  * `manipulator_share`, `ignition_time`, `ignition_len`, `ignition_size`:
    a colluding cluster that stays quiet, fires a coordinated sell burst to
    ignite the herd and then reverses (momentum ignition, MAR Annex II).
  * `persona`, `persona_share`, `persona_noise`, `persona_hash`: a group of
    LLM persona traders that share one distilled policy table (see
    `personas.py`), the foundation model monoculture channel.
  * `generator`: "shared_signal" (versions 1 and 2), "imitation" (herding by
    recruitment within a vendor cluster, after Kirman and Lux and Marchesi),
    "voter" (the same by local copying on a ring, the voter model) and
    "sqrt_impact" (square root price impact after Bouchaud and others).
  * `evader_period`: how often the evader cohorts rotate (default 5, as before).
"""

from dataclasses import dataclass, fields
import hashlib
import json

import numpy as np


class SimulationStopped(RuntimeError):
    """Raised when the emergency stop is set during a simulation."""


CLASS_LABELS = {-1: "noise_trader", -2: "fundamentalist", -3: "rl_policy",
                -4: "manipulator", -5: "llm_persona"}


def class_label(c: int) -> str:
    if c in CLASS_LABELS:
        return CLASS_LABELS[c]
    if c <= -10:
        return CUSTOM_CLASS_NAMES.get(c, f"custom_{-10 - c}")
    return "vendor_" + "ABCDEFGH"[c] if 0 <= c < 8 else f"vendor_{c}"


CUSTOM_CLASS_NAMES = {}      # class code -> template name, set when a population is built


@dataclass
class ScenarioSpec:
    name: str
    family: str = ""
    n_agents: int = 120
    t_steps: int = 600
    vendor_shares: tuple = (0.35, 0.15)   # fraction of agents per AI vendor cluster
    vendor_rhos: tuple = (0.85, 0.30)     # intra cluster signal correlation
    frac_fundamental: float = 0.20
    shock_time: int = 300                 # None for quiet scenarios
    shock_size: float = 0.08              # fundamental drop (log units)
    kappa: float = 0.015                  # price impact coefficient
    sigma: float = 0.002                  # exogenous noise vol
    momentum_window: int = 20
    rl_share: float = 0.0                 # fraction of agents driven by RL policies
    seed: int = 0
    rho_crit: float = 0.6                 # destabilising label threshold
    share_crit: float = 0.10
    rl_n: int = 0                         # agents driven by trained RL policies
    rl_seed: int = 0
    rl_destab: bool = False               # set by the battery builder from
                                          # measured policy convergence
    evader_cohorts: int = 0               # >0: cluster 0 rotates this many cohorts
    holdout: bool = False                 # held out family, never calibrated on
    # version 3
    generator: str = "shared_signal"      # shared_signal | imitation | sqrt_impact
    evader_period: int = 5                # steps between cohort rotations
    manipulator_share: float = 0.0        # colluding ignition cluster (0 = none)
    ignition_time: int = None             # first step of the sell burst
    ignition_len: int = 8                 # burst length; reversal lasts twice as long
    ignition_size: float = 4.0            # order size during the burst
    persona: str = ""                     # LLM persona name (see personas.py)
    persona_share: float = 0.0            # share of agents driven by that persona
    persona_noise: float = 0.35           # idiosyncratic execution noise of persona agents
    persona_hash: str = ""                # sha256 of the policy table bound at planning
    # version 3.4: risks named by the FSB, IOSCO, Bank of England and IMF reports
    vendor_fault_time: int = None         # step at which the dominant vendor's model starts misfiring
    vendor_fault_len: int = 25            # length of the faulty output episode
    vendor_fault_signal: float = -2.0     # the erroneous shared signal it emits (sell)
    liquidity_withdrawal_time: int = None # step from which fundamentalists cut their liquidity provision
    liquidity_withdrawal_scale: float = 0.3  # fraction of their normal flow that remains
    false_shock_len: int = 0              # >0: the shock is misinformation and reverts after this many steps
    # version 3.6: agent templates defined by the authority, (name, share) pairs, hashes bound at Gate 1
    custom_agents: tuple = ()
    custom_agent_hashes: tuple = ()
    # version 3.7: hybrid generator, the observed return path as the market's news
    hybrid_sha: str = ""

    @property
    def quiet(self) -> bool:
        return self.shock_time is None

    def describe(self) -> dict:
        d = {}
        for f in fields(self):
            v = getattr(self, f.name)
            d[f.name] = ([list(x) if isinstance(x, tuple) else x for x in v] if isinstance(v, tuple) else v)
        return d


def battery_hash(specs) -> str:
    """SHA-256 over the canonical description of every scenario. Gate 1
    approves this value; the critic checks the run used the same battery."""
    blob = json.dumps([s.describe() for s in specs], sort_keys=True,
                      separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


@dataclass
class SimResult:
    spec: ScenarioSpec
    prices: np.ndarray          # (T,) log prices
    returns: np.ndarray         # (T,)
    flows: np.ndarray           # (T, N) agent order flows
    agent_cluster: np.ndarray   # (N,) cluster id, -1 noise, -2 fundamentalist, -3 RL
    destabilising: np.ndarray   # (N,) bool ground truth
    halted: np.ndarray = None   # (T,) bool, set by interventions
    throttled: np.ndarray = None
    fund_path: np.ndarray = None  # (T,) the fundamental value at each step

    @property
    def crash_onset(self):
        return self.spec.shock_time

    def max_drawdown(self) -> float:
        p = np.exp(self.prices)
        peak = np.maximum.accumulate(p)
        return float(np.max((peak - p) / peak))

    def first_crossing(self, threshold):
        """Steps after the shock at which the drawdown from the pre shock
        price first exceeds `threshold`; None if it never does. Quiet
        scenarios measure from the start."""
        t0 = max(0, self.spec.shock_time - 1) if self.spec.shock_time is not None else 0
        p = np.exp(self.prices[t0:])
        peak = np.maximum.accumulate(p)
        dd = (peak - p) / peak
        hit = np.where(dd > threshold)[0]
        return int(hit[0]) if len(hit) else None

    def post_shock_drawdown(self) -> float:
        """Maximum drawdown measured from the step before the shock. For a
        quiet scenario this is the whole path drawdown."""
        if self.spec.shock_time is None:
            return self.max_drawdown()
        t0 = max(0, self.spec.shock_time - 1)
        p = np.exp(self.prices[t0:])
        peak = np.maximum.accumulate(p)
        return float(np.max((peak - p) / peak))

    def shock_trough(self, window=150) -> float:
        """Depth of the post shock trough relative to the price just before
        the shock: 1 minus the minimum price in the window over the pre
        shock price. Zero for quiet scenarios."""
        if self.spec.shock_time is None:
            return 0.0
        s = self.spec.shock_time
        p = np.exp(self.prices)
        return float(max(0.0, 1.0 - p[s:s + window].min() / p[s - 1]))

    def pre_shock_vol(self) -> float:
        """Realised return volatility before the shock, relative to the
        exogenous noise scale. Well above 1 means the herd is generating its
        own instability before any shock lands."""
        t1 = self.spec.shock_time if self.spec.shock_time is not None \
            else self.spec.t_steps
        seg = self.returns[1:t1]
        return float(seg.std() / self.spec.sigma) if len(seg) > 2 else 0.0


def _build_population(spec: ScenarioSpec, rng):
    n = spec.n_agents
    cluster = np.full(n, -1, dtype=int)
    idx = 0
    for c, share in enumerate(spec.vendor_shares):
        k = int(round(share * n))
        cluster[idx:idx + k] = c
        idx += k
    k_f = int(round(spec.frac_fundamental * n))
    cluster[idx:idx + k_f] = -2
    idx += k_f
    k_m = int(round(spec.manipulator_share * n))      # version 3: colluding cluster
    if k_m > 0:
        cluster[idx:idx + k_m] = -4
        idx += k_m
    k_p = int(round(spec.persona_share * n))          # version 3: LLM persona group
    if k_p > 0:
        cluster[idx:idx + k_p] = -5
        idx += k_p
    for j, (name, share) in enumerate(spec.custom_agents):   # version 3.6: authority defined agents
        k_c = int(round(float(share) * n))
        if k_c > 0:
            cluster[idx:idx + k_c] = -10 - j
            CUSTOM_CLASS_NAMES[-10 - j] = str(name)
            idx += k_c
    if spec.rl_n > 0:
        cluster[n - spec.rl_n:] = -3      # RL policy driven agents
    return cluster


def _impact(spec: ScenarioSpec, mean_flow: float) -> float:
    """Price impact of the aggregate order flow. The shared signal and
    imitation generators use the linear impact of versions 1 and 2. The
    square root generator follows the empirical square root law (Bouchaud,
    Farmer and Lillo 2009; Toth and others 2011): impact is concave in the
    flow, normalised so that a mean flow of 0.5 has the same impact as under
    the linear rule."""
    if spec.generator == "sqrt_impact":
        return spec.kappa * float(np.sign(mean_flow)) * float(np.sqrt(abs(mean_flow) * 0.5))
    return spec.kappa * mean_flow


def simulate(spec: ScenarioSpec, intervention=None, stop=None) -> SimResult:
    """Run one scenario. `intervention` is an optional callable
    (t, state) -> dict with keys halt(bool), throttle(array N of scale
    factors), called each step. `stop` is an optional threading.Event; when
    set, the run raises SimulationStopped at the next check.

    Every random draw of the version 1 and 2 dynamics is made in the same
    order as before; the version 3 classes and generators draw only when a
    scenario enables them, so earlier batteries reproduce their numbers."""
    if spec.generator not in ("shared_signal", "imitation", "sqrt_impact", "voter", "hybrid"):
        raise ValueError(f"unknown generator {spec.generator!r}")
    rng = np.random.default_rng(spec.seed)
    n, T = spec.n_agents, spec.t_steps
    cluster = _build_population(spec, rng)
    n_clusters = len(spec.vendor_shares)

    prices = np.zeros(T)
    returns = np.zeros(T)
    flows = np.zeros((T, n))
    halted = np.zeros(T, dtype=bool)
    throttled = np.ones((T, n))

    fundamental = 0.0
    fund_path = np.zeros(T)                # the fundamental at each step, for the overshoot test
    hybrid = None
    if spec.generator == "hybrid":
        from .calibrate import observed_returns
        hybrid = observed_returns(spec.hybrid_sha)
        if len(hybrid) < T:
            raise ValueError(f"hybrid series has {len(hybrid)} steps, the scenario needs {T}")
    common = np.zeros(n_clusters)          # AR(1) vendor factors
    idio_scale = 0.8

    rl_agents = None
    rl_slots = np.where(cluster == -3)[0]
    if len(rl_slots):
        from .rl_agents import get_trained_population, mean_action
        rl_agents = get_trained_population(len(rl_slots), seed=spec.rl_seed)
        for ag in rl_agents:
            ag.reset()

    # version 3: LLM persona group sharing one distilled policy table
    persona_slots = np.where(cluster == -5)[0]
    persona_policy = None
    if len(persona_slots):
        from .personas import get_persona
        persona_policy = get_persona(spec.persona)
        if spec.persona_hash and spec.persona_hash != persona_policy.table_sha256:
            raise ValueError(f"persona {spec.persona!r} table hash {persona_policy.table_sha256[:12]} "
                             f"does not match the hash bound at planning {spec.persona_hash[:12]}")
    custom = []                                    # (code, template, slots, inventory)
    if spec.custom_agents:
        from .agents import get_agent, agent_hash
        for j, (name, _share) in enumerate(spec.custom_agents):
            slots = np.where(cluster == -10 - j)[0]
            if not len(slots):
                continue
            ag = get_agent(str(name))
            if len(spec.custom_agent_hashes) > j and spec.custom_agent_hashes[j] and \
                    spec.custom_agent_hashes[j] != agent_hash(ag):
                raise ValueError(f"agent {name!r} definition hash {agent_hash(ag)[:12]} does not match the hash "
                                 f"bound at planning {spec.custom_agent_hashes[j][:12]}")
            custom.append((-10 - j, ag, slots, np.zeros(len(slots))))
    manip_slots = np.where(cluster == -4)[0]
    ign_t0 = spec.ignition_time if len(manip_slots) else None
    ign_t1 = (ign_t0 + spec.ignition_len) if ign_t0 is not None else None
    ign_t2 = (ign_t1 + 2 * spec.ignition_len) if ign_t0 is not None else None

    # version 3: imitation generator state. Vendor members are chartists or
    # fundamentalists and recruit one another within their cluster.
    imitation = spec.generator in ("imitation", "voter")
    voter = spec.generator == "voter"
    mode = None
    if imitation:
        mode = np.zeros(n, dtype=bool)      # True = chartist
        for c in range(n_clusters):
            members = np.where(cluster == c)[0]
            k0 = int(round(0.5 * len(members)))
            mode[members[:k0]] = True

    # evader cohorts: members of cluster 0 take turns carrying the shared
    # signal, scaled so the cluster's aggregate flow is unchanged
    k_ev = int(spec.evader_cohorts)
    cohort = None
    if k_ev > 0:
        members0 = np.where(cluster == 0)[0]
        cohort = np.full(n, -1, dtype=int)
        cohort[members0] = np.arange(len(members0)) % k_ev
    period = max(1, int(spec.evader_period))

    loop_idx = np.where((cluster != -3) & (cluster != -5) & (cluster > -10))[0]
    loop_cl = cluster[loop_idx]
    m_noise, m_fund, m_manip = loop_cl == -1, loop_cl == -2, loop_cl == -4
    m_vendor = loop_cl >= 0
    rhos_arr = np.asarray(spec.vendor_rhos, dtype=float)

    for t in range(1, T):
        if stop is not None and (t % 50 == 0) and stop.is_set():
            raise SimulationStopped(spec.name)
        if hybrid is not None:
            fundamental += float(hybrid[t])      # the observed path is the news the fundamentalists anchor to
        if spec.shock_time is not None and t == spec.shock_time:
            fundamental -= spec.shock_size
        if spec.false_shock_len and spec.shock_time is not None and t == spec.shock_time + spec.false_shock_len:
            fundamental += spec.shock_size            # misinformation: the news is retracted

        # vendor common factors follow AR(1)
        common = 0.9 * common + rng.normal(0, 0.3, n_clusters)

        # momentum signal from recent returns
        w0 = max(0, t - spec.momentum_window)
        momentum = returns[w0:t].mean() / (returns[w0:t].std() + 1e-6) if t > 5 else 0.0
        momentum = float(np.clip(momentum, -3, 3))

        q = np.zeros(n)
        if rl_agents is not None:
            vol_ratio = (returns[w0:t].std() / spec.sigma) if t > 5 else 1.0
            obs = {"momentum": momentum, "vol": float(min(vol_ratio, 4.0))}
            for slot, ag in zip(rl_slots, rl_agents):
                q[slot] = 1.8 * mean_action(ag, obs) + 0.35 * rng.normal()
                ag.inventory = 0.7 * ag.inventory + q[slot]
        if persona_policy is not None:
            vol_ratio = (returns[w0:t].std() / spec.sigma) if t > 5 else 1.0
            a = persona_policy.action(momentum, float(min(vol_ratio, 4.0)))
            for slot in persona_slots:
                q[slot] = 1.8 * a + spec.persona_noise * rng.normal()
        if imitation:
            # recruitment: each vendor member meets a random member of its
            # cluster and adopts that member's mode with probability rho;
            # a small rate of spontaneous switching keeps both modes alive
            for c in range(n_clusters):
                members = np.where(cluster == c)[0]
                if len(members) < 2:
                    continue
                if voter:
                    # voter model on a ring: each member copies one of its four ring
                    # neighbours within the cluster (Kohan Marzagao, 6CCS3AIN week 9:
                    # consensus by local copying), so herding spreads by contact
                    k = len(members)
                    offs = rng.choice(np.array([-2, -1, 1, 2]), size=k)
                    partners = members[(np.arange(k) + offs) % k]
                else:
                    partners = members[rng.integers(0, len(members), size=len(members))]
                # a chartist recruits at rate rho; a fundamentalist recruits
                # less the stronger the trend (Lux and Marchesi 1999: the
                # profitable strategy spreads), so trends tip a cluster into
                # a chartist herd
                rate = np.where(mode[partners], spec.vendor_rhos[c],
                                spec.vendor_rhos[c] * (1.0 - min(1.0, abs(momentum) / 2.0)))
                adopt = rng.random(len(members)) < rate
                new_mode = np.where(adopt, mode[partners], mode[members])
                flip = rng.random(len(members)) < 0.02
                mode[members] = np.where(flip, ~new_mode, new_mode)
        active_cohort = (t // period) % k_ev if k_ev > 0 else -1
        # One standard normal per agent outside the RL and persona groups, in
        # index order, exactly as the scalar loop of versions 1 to 3.2 drew
        # them; each class then scales and shifts its own draws. Vectorised
        # in 3.3 for speed with bit identical output.
        z = rng.normal(0, 1.0, size=len(loop_idx))
        ql = np.empty(len(loop_idx))
        ql[m_noise] = z[m_noise]
        if m_fund.any():
            ql[m_fund] = -1.5 * (prices[t - 1] - fundamental) / 0.02 + 0.5 * z[m_fund]
            if spec.liquidity_withdrawal_time is not None and t >= spec.liquidity_withdrawal_time:
                ql[m_fund] *= spec.liquidity_withdrawal_scale   # liquidity providers pull back in stress
        if m_manip.any():
            if ign_t0 is not None and ign_t0 <= t < ign_t1:
                ql[m_manip] = -spec.ignition_size + 0.2 * z[m_manip]
            elif ign_t1 is not None and ign_t1 <= t < ign_t2:
                ql[m_manip] = 0.5 * spec.ignition_size + 0.2 * z[m_manip]
            else:
                ql[m_manip] = 0.3 * z[m_manip]
        if m_vendor.any():
            cv = loop_cl[m_vendor]
            if imitation:
                chart = mode[loop_idx[m_vendor]]
                out_v = np.where(chart, 1.4 * momentum + common[cv],
                                 -0.8 * (prices[t - 1] - fundamental) / 0.02) + idio_scale * z[m_vendor]
            else:
                rho_v = rhos_arr[cv]
                shared_v = 1.4 * momentum + common[cv]
                if spec.vendor_fault_time is not None and \
                        spec.vendor_fault_time <= t < spec.vendor_fault_time + spec.vendor_fault_len:
                    # a faulty third party model: every agent on vendor A receives
                    # the same erroneous signal instead of the market signal
                    shared_v = np.where(cv == 0, spec.vendor_fault_signal, shared_v)
                out_v = rho_v * shared_v + (1 - rho_v) * idio_scale * z[m_vendor]
                if cohort is not None:
                    c0 = cv == 0
                    coh = cohort[loop_idx[m_vendor]]
                    on = c0 & (coh == active_cohort)
                    off = c0 & (coh != active_cohort)
                    out_v = np.where(on, rho_v * shared_v * k_ev + (1 - rho_v) * idio_scale * z[m_vendor], out_v)
                    out_v = np.where(off, (1 - rho_v) * idio_scale * z[m_vendor], out_v)
            ql[m_vendor] = out_v
        q[loop_idx] = ql
        if custom:
            from .agents import step_flows
            sig = {"momentum": momentum,
                   "mispricing": float((prices[t - 1] - fundamental) / 0.02),
                   "last_return": float(returns[t - 1] / spec.sigma) if t >= 1 else 0.0,
                   "vol": float(min((returns[w0:t].std() / spec.sigma) if t > 5 else 1.0, 6.0)),
                   "crowd": float(flows[t - 1].mean()) if t >= 1 else 0.0,
                   "time": float(max(0, t - spec.shock_time)) if spec.shock_time is not None else 0.0}
            for c in range(n_clusters):
                sig[f"vendor_signal_{c}"] = float(1.4 * momentum + common[c])
            for _code, ag, slots, inv in custom:
                lag = int(ag.get("lag", 0))
                sg = sig
                if lag > 0 and t - lag > 5:
                    seg = returns[max(0, t - lag - spec.momentum_window):t - lag]
                    sg = dict(sig, momentum=float(np.clip(seg.mean() / (seg.std() + 1e-6), -3, 3)),
                              last_return=float(returns[t - 1 - lag] / spec.sigma))
                q[slots] = step_flows(ag, len(slots), t, sg, rng, inv, spec.shock_time)

        scale = np.ones(n)
        halt = False
        if intervention is not None:
            act = intervention(t, {"returns": returns[:t], "flows": flows[:t],
                                   "prices": prices[:t]})
            halt = bool(act.get("halt", False))
            scale = np.asarray(act.get("throttle", np.ones(n)), dtype=float)

        throttled[t] = scale
        if halt:
            halted[t] = True
            q[:] = 0.0
        else:
            q = q * scale

        flows[t] = q
        fund_path[t] = fundamental
        if hybrid is not None:
            r = _impact(spec, q.mean()) + float(hybrid[t])      # real news plus the synthetic crowd's impact
        else:
            r = _impact(spec, q.mean()) + spec.sigma * rng.normal()
        returns[t] = r
        prices[t] = prices[t - 1] + r

    destab = np.zeros(n, dtype=bool)
    for c, (share, rho) in enumerate(zip(spec.vendor_shares, spec.vendor_rhos)):
        if rho >= spec.rho_crit and share >= spec.share_crit:
            destab[cluster == c] = True
    if spec.rl_n > 0 and spec.rl_destab \
            and spec.rl_n / n >= spec.share_crit:
        destab[cluster == -3] = True
    if len(rl_slots) and spec.shock_time is not None:
        w = slice(spec.shock_time, min(T, spec.shock_time + 80))
        amp = (flows[w][:, rl_slots] * returns[w, None]).sum(axis=0)
        rl_flows = flows[100:, rl_slots]
        with np.errstate(invalid="ignore", divide="ignore"):
            C = np.atleast_2d(np.corrcoef(rl_flows.T))
        iu = np.triu_indices_from(C, k=1)
        vals = C[iu][np.isfinite(C[iu])] if len(iu[0]) else np.array([])
        mean_corr = float(vals.mean()) if len(vals) else 0.0
        if mean_corr >= 0.5 and spec.rl_share >= spec.share_crit:
            destab[rl_slots[amp > 0]] = True
    if len(manip_slots):
        destab[manip_slots] = True                        # manipulators are always positives
    if spec.vendor_fault_time is not None and len(spec.vendor_shares):
        destab[cluster == 0] = True                       # the faulty vendor's agents drive the episode
    for _code, ag, slots, _inv in custom:
        dz = ag.get("destabilising", "auto")
        if dz is True:
            destab[slots] = True
        elif dz == "auto":
            from .agents import auto_destabilising
            share = float(dict((str(k), float(v)) for k, v in spec.custom_agents).get(ag["name"], 0.0))
            destab[slots] = auto_destabilising(flows, prices, fund_path, slots, spec.shock_time,
                                               share, spec.share_crit)
    if persona_policy is not None and spec.persona_share >= spec.share_crit \
            and persona_policy.momentum_slope() > 0.05:
        destab[persona_slots] = True                      # a large momentum following persona group

    return SimResult(spec, prices, returns, flows, cluster, destab,
                     halted=halted, throttled=throttled, fund_path=fund_path)


CUSTOM_NOTES = {}          # notes of families defined by the authority, filled at planning

FAMILY_NOTES = {
    "herd_high": "40% of agents on one vendor, signal correlation 0.90",
    "herd_mid": "30% on one vendor, correlation 0.75",
    "herd_low": "20% on one vendor, correlation 0.65 (near the label threshold)",
    "mixed": "two vendors of 25% each, correlations 0.80 and 0.20",
    "rl_emergent": "48 independently trained RL traders; herding is learned, not imposed",
    "evader": "dominant vendor rotates three cohorts to defeat correlation based sentinels",
    "quiet": "no shock; vendor correlation below the destabilising threshold",
    "holdout_herd": "held out: 150 agents, three vendors, later shock, higher impact",
    "holdout_quiet": "held out: 150 agents, three vendors, no shock",
    "ignition": "colluding cluster of 8% ignites momentum with a sell burst across the shock, "
                "then reverses; a 20% vendor at correlation 0.65 follows",
    "persona_llm": "35% of agents trade from one distilled LLM persona table (momentum follower); "
                   "the foundation model monoculture channel",
    "empirical": "held out: shock and volatility taken from an observed dataset brought through quarantine",
    "vendor_fault": "a faulty third party model: for 25 steps every agent on the 35% vendor receives the "
                    "same erroneous sell signal (Bank of England 2026 kill switch case; IOSCO 2026 "
                    "contingency planning)",
    "liquidity_withdrawal": "liquidity providers step away after the shock, the IMF (2024) channel of AI "
                            "market makers withdrawing in stress",
    "misinformation": "the shock is disinformation retracted after 20 steps (FSB 2024 and IOSCO 2025 "
                      "deepfake and disinformation channel); the herd amplifies a false move",
}


def fixed_battery():
    """The fixed demonstration battery as the fallback of every planner path.
    The three minute profile leaves the RL population untrained, since it
    is not in that battery and training it is the one slow step."""
    import os
    return scenario_battery(include_rl=os.environ.get("HSL_ASSURANCE", "").strip().lower() != "demo")


def scenario_battery(seed0: int = 0, include_evader=True, include_holdout=True,
                     include_rl=True, include_ignition=True, include_persona=True,
                     n_quiet=8, seeds_per=3, include_reports=True):
    """The demo battery: herding scenarios of varying intensity, an emergent
    RL herd, an adversarial evader family, a colluding ignition family, an
    LLM persona family, quiet scenarios for false alert and false halt
    measurement (eight, so the conformal guarantee at the 0.25 budget is
    achievable) and a held out family for generalisation."""
    specs = []
    grids = [
        ("herd_high", (0.40, 0.15), (0.90, 0.30), 0.05),
        ("herd_mid",  (0.30, 0.15), (0.75, 0.30), 0.05),
        ("herd_low",  (0.20, 0.15), (0.65, 0.30), 0.04),
        ("mixed",     (0.25, 0.25), (0.80, 0.20), 0.05),
    ]
    for j, (nm, shares, rhos, sh) in enumerate(grids):
        for s in range(seeds_per):
            specs.append(ScenarioSpec(name=f"{nm}_{s}", family=nm,
                                      vendor_shares=shares, vendor_rhos=rhos,
                                      shock_size=sh, seed=seed0 + 10 * j + s))
    if include_rl:
        from .rl_agents import get_trained_population, policy_convergence
        rl_n = 48
        conv = policy_convergence(get_trained_population(rl_n, seed=0))
        rl_destab = conv["policy_convergence"] >= 0.6 \
            and conv["momentum_slope"] > 0.05
        for s in range(seeds_per):
            specs.append(ScenarioSpec(
                name=f"rl_emergent_{s}", family="rl_emergent",
                vendor_shares=(0.15,), vendor_rhos=(0.30,),
                frac_fundamental=0.15, rl_n=rl_n, rl_destab=rl_destab,
                shock_size=0.05, seed=seed0 + 500 + s))
    if include_evader:
        for s in range(seeds_per):
            specs.append(ScenarioSpec(
                name=f"evader_{s}", family="evader",
                vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                shock_size=0.05, evader_cohorts=3, seed=seed0 + 700 + s))
    if include_ignition:
        for s in range(seeds_per):
            specs.append(ScenarioSpec(
                name=f"ignition_{s}", family="ignition",
                vendor_shares=(0.20, 0.15), vendor_rhos=(0.65, 0.30),
                shock_size=0.04, manipulator_share=0.08, ignition_time=295,
                ignition_len=10, ignition_size=8.0, seed=seed0 + 600 + s))
    if include_persona:
        for s in range(seeds_per):
            specs.append(ScenarioSpec(
                name=f"persona_llm_{s}", family="persona_llm",
                vendor_shares=(0.15,), vendor_rhos=(0.30,), frac_fundamental=0.15,
                persona="momentum_follower", persona_share=0.35,
                shock_size=0.05, seed=seed0 + 650 + s))
    if include_reports:
        for s in range(2):
            specs.append(ScenarioSpec(
                name=f"vendor_fault_{s}", family="vendor_fault",
                vendor_shares=(0.35, 0.15), vendor_rhos=(0.60, 0.30),
                shock_size=0.02, vendor_fault_time=300, vendor_fault_len=25,
                seed=seed0 + 750 + s))
            specs.append(ScenarioSpec(
                name=f"liquidity_withdrawal_{s}", family="liquidity_withdrawal",
                vendor_shares=(0.35, 0.15), vendor_rhos=(0.85, 0.30),
                shock_size=0.05, liquidity_withdrawal_time=312, seed=seed0 + 760 + s))
            specs.append(ScenarioSpec(
                name=f"misinformation_{s}", family="misinformation",
                vendor_shares=(0.35, 0.15), vendor_rhos=(0.85, 0.30),
                shock_size=0.05, false_shock_len=20, seed=seed0 + 770 + s))
    for s in range(n_quiet):
        specs.append(ScenarioSpec(name=f"quiet_{s}", family="quiet",
                                  vendor_shares=(0.25, 0.15),
                                  vendor_rhos=(0.45, 0.25), shock_time=None,
                                  seed=seed0 + 900 + s))
    if include_holdout:
        for s in range(3):
            specs.append(ScenarioSpec(
                name=f"holdout_herd_{s}", family="holdout_herd", holdout=True,
                n_agents=150, vendor_shares=(0.25, 0.20, 0.15),
                vendor_rhos=(0.85, 0.70, 0.30), shock_time=400,
                shock_size=0.05, kappa=0.018, seed=seed0 + 800 + s))
        for s in range(2):
            specs.append(ScenarioSpec(
                name=f"holdout_quiet_{s}", family="holdout_quiet", holdout=True,
                n_agents=150, vendor_shares=(0.25, 0.20, 0.15),
                vendor_rhos=(0.45, 0.35, 0.25), shock_time=None,
                kappa=0.018, seed=seed0 + 950 + s))
    return specs
