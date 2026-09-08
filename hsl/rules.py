"""Jurisdiction rule library: intervention rules stylised after published
mechanisms, so one scenario battery can compare regimes side by side.

Each rule has the same interface as the version 2 rules (`make(n_agents,
flags_online, sentinel_flags)` returning a per step callable), a
`jurisdiction` tag and a `basis` sentence naming the public rule it is
modelled on. The simulator has no clock, so durations are expressed in
simulation steps and the mapping is declared on the rule; nothing here
claims to reproduce a venue's actual parameters.

  LULDStyleBand          after the US Limit Up-Limit Down Plan (Reg NMS):
                         price bands of 5% around a reference price equal
                         to the mean price of the preceding five minutes;
                         a limit state that lasts 15 seconds before a five
                         minute trading pause. Mapped to a 25 step
                         reference window, a 3 step limit state and a 20
                         step pause.
  MarketWideBreaker      after the US market wide circuit breaker levels
                         (7%, 13% and 20% declines from the reference
                         close): 15 step halts at levels one and two and a
                         halt for the rest of the session at level three.
  VenueVolatilityHalt    after MiFID II Article 48(5) (venues must be able
                         to halt or constrain trading on a significant
                         price movement) and the ESMA guidelines on the
                         calibration of circuit breakers: a dynamic collar
                         on the last price and a static collar on a
                         reference price; a breach calls a volatility
                         interruption (halt) of a set length.
  FirmKillFunctionality  after MiFID II RTS 6 Article 12 (a firm must be
                         able to cancel its unexecuted orders immediately):
                         the version 2 kill switch is the sentinel informed
                         form of this at market level and is kept as is.

Sources: SEC press release 2011-84 and the LULD Plan FAQ (Nasdaq, Cboe);
NYSE market wide circuit breaker levels; Directive 2014/65/EU Article 48(5);
Commission Delegated Regulation (EU) 2017/589 (RTS 6) Article 12; ESMA
Guidelines on the calibration of circuit breakers (2017).
"""

import numpy as np


class LULDStyleBand:
    name = "luld_style_band"
    label = "LULD style price band (US)"
    jurisdiction = "US"
    basis = ("Limit Up-Limit Down Plan: 5% band around a five minute reference price, "
             "15 second limit state, five minute pause; mapped to steps")
    targeted = False

    def __init__(self, band=0.05, ref_window=25, limit_steps=3, pause_steps=20):
        self.band, self.ref_window = band, ref_window
        self.limit_steps, self.pause_steps = limit_steps, pause_steps
        self._pause_until, self._limit_count = -1, 0

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._pause_until, self._limit_count = -1, 0

        def rule(t, state):
            p = state["prices"]
            if t < self._pause_until:
                return {"halt": True}
            if len(p) < self.ref_window + 1:
                return {}
            ref = float(np.exp(p[-self.ref_window:]).mean())
            last = float(np.exp(p[-1]))
            if abs(last / ref - 1.0) > self.band:
                self._limit_count += 1
                if self._limit_count >= self.limit_steps:
                    self._limit_count = 0
                    self._pause_until = t + self.pause_steps
                    return {"halt": True}
                return {}
            self._limit_count = 0
            return {}
        return rule


class MarketWideBreaker:
    name = "market_wide_breaker"
    label = "Market wide circuit breaker (US)"
    jurisdiction = "US"
    basis = ("Market wide circuit breaker levels of 7%, 13% and 20% decline from the reference "
             "close: 15 minute halts at levels one and two, halt for the day at level three; "
             "mapped to steps")
    targeted = False

    def __init__(self, levels=(0.07, 0.13, 0.20), halt_steps=15):
        self.levels, self.halt_steps = levels, halt_steps
        self._halt_until, self._fired = -1, 0

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._halt_until, self._fired = -1, 0

        def rule(t, state):
            p = state["prices"]
            if t < self._halt_until:
                return {"halt": True}
            if len(p) < 2 or self._fired >= len(self.levels):
                return {}
            decline = 1.0 - float(np.exp(p[-1] - p[0]))
            if decline >= self.levels[self._fired]:
                self._fired += 1
                self._halt_until = t + (self.halt_steps if self._fired < len(self.levels) else 10 ** 9)
                return {"halt": True}
            return {}
        return rule


class VenueVolatilityHalt:
    name = "venue_volatility_halt"
    label = "Venue volatility interruption (EU)"
    jurisdiction = "EU"
    basis = ("MiFID II Article 48(5) and the ESMA guidelines on circuit breaker calibration: "
             "dynamic collar on the last price and static collar on a reference price; a breach "
             "triggers a volatility interruption of set length; parameters are illustrative")
    targeted = False

    def __init__(self, dynamic=0.02, static=0.06, ref_window=50, halt_steps=10):
        self.dynamic, self.static = dynamic, static
        self.ref_window, self.halt_steps = ref_window, halt_steps
        self._halt_until = -1

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        self._halt_until = -1

        def rule(t, state):
            p = state["prices"]
            if t < self._halt_until:
                return {"halt": True}
            if len(p) < 3:
                return {}
            last, prev = float(np.exp(p[-1])), float(np.exp(p[-2]))
            ref = float(np.exp(p[-self.ref_window:]).mean()) if len(p) >= self.ref_window \
                else float(np.exp(p).mean())
            if abs(last / prev - 1.0) > self.dynamic or abs(last / ref - 1.0) > self.static:
                self._halt_until = t + self.halt_steps
                return {"halt": True}
            return {}
        return rule


class ResponsiveLadder:
    """An enforcement pyramid as an intervention rule (Ayres and Braithwaite
    1992, Responsive Regulation; Baldwin and Black 2008 on really responsive
    regulation). The rule starts at the least intrusive rung and escalates
    only when the lower rung has failed to contain the market:

      rung 1  targeted throttle of the agents the sentinel flags
      rung 2  kill functionality for the flagged agents when the rolling
              return keeps deteriorating under the throttle
      rung 3  a market wide halt when rungs 1 and 2 have not held

    De escalation follows recovery: when the rolling return is back inside
    the limit the rule steps down one rung per dwell period. The ladder is
    sentinel informed and therefore carries the sentinel's targeting error,
    which the burden by class makes visible."""
    name = "responsive_ladder"
    label = "Responsive enforcement ladder"
    jurisdiction = "generic (enforcement pyramid)"
    basis = ("Ayres and Braithwaite 1992 enforcement pyramid: escalate from a targeted throttle to "
             "kill functionality to a market wide halt only when the lower rung fails; step down on "
             "recovery")
    targeted = True

    def __init__(self, throttle=0.4, window=10, limit=-0.03, dwell=10, halt_steps=15):
        self.throttle, self.window, self.limit = throttle, window, limit
        self.dwell, self.halt_steps = dwell, halt_steps

    def make(self, n_agents, flags_online=None, sentinel_flags=None):
        state = {"rung": 0, "since": -10 ** 9, "halt_until": -1}

        def rule(t, state_):
            r = state_["returns"]
            fo = flags_online[t - 1] if flags_online is not None and t - 1 < len(flags_online) else None
            flagged = fo if fo is not None else np.zeros(n_agents, dtype=bool)
            roll = float(r[-self.window:].sum()) if len(r) >= self.window else 0.0
            stressed = roll < self.limit and flagged.any()
            if t < state["halt_until"]:
                return {"halt": True}
            if stressed:
                if state["rung"] == 0:
                    state["rung"], state["since"] = 1, t
                elif t - state["since"] >= self.dwell:
                    state["rung"] = min(3, state["rung"] + 1)
                    state["since"] = t
            elif state["rung"] > 0 and t - state["since"] >= self.dwell:
                state["rung"] -= 1
                state["since"] = t
            if state["rung"] == 0:
                return {}
            if state["rung"] == 3:
                state["halt_until"] = t + self.halt_steps
                state["rung"], state["since"] = 2, t
                return {"halt": True}
            scale = np.ones(n_agents)
            scale[flagged] = self.throttle if state["rung"] == 1 else 0.0
            return {"throttle": scale}
        return rule


LIBRARY_RULES = [LULDStyleBand, MarketWideBreaker, VenueVolatilityHalt, ResponsiveLadder]

RULE_LIBRARY = {
    "static_circuit_breaker": {"jurisdiction": "generic",
                               "basis": "rolling return limit halting the whole market"},
    "dynamic_throttle": {"jurisdiction": "generic",
                         "basis": "sentinel informed targeted throttle of flagged agents"},
    "kill_switch": {"jurisdiction": "EU (firm level analogue)",
                    "basis": "RTS 6 Article 12 kill functionality applied to sentinel flagged "
                             "agents: immediate cancellation for a dwell period"},
}
for R in LIBRARY_RULES:
    RULE_LIBRARY[R.name] = {"jurisdiction": R.jurisdiction, "basis": R.basis}
