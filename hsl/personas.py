"""LLM persona traders by policy distillation.

The foundation model monoculture channel described by the FSB, the Bank of
England and Project Logos (BIS Innovation Hub, Bank of England and Deutsche
Bundesbank, 2026) is that many agents built on one model make the same call
in the same state. Calling a model at every step for every agent would be
slow, non deterministic and unauditable. HSL distils instead: a persona is
asked once, at planning time, for its action in each of fifteen market
states (five momentum buckets by three volatility regimes). The answer is a
policy table that is hashed, logged and bound into the battery, and every
agent that shares the persona trades from the same table plus its own
execution noise. Correlation is therefore a consequence of a shared model,
not a parameter.

With no model configured, or when a model's answer fails validation, a
documented offline surrogate table is used and the source is recorded as
such. Lopez-Lira (2025) shows that prompts generate correlated behaviours
in LLM agent markets; this module makes that mechanism reproducible.
"""

import hashlib
import json
import re

import numpy as np

from .rl_agents import ACTIONS, _mom_bucket

MOM_LABELS = ["strongly negative", "negative", "flat", "positive", "strongly positive"]
VOL_LABELS = ["calm", "elevated", "stressed"]
ACTION_WORDS = {"strong_sell": -1.5, "sell": -0.5, "hold": 0.0, "buy": 0.5, "strong_buy": 1.5}

# Offline surrogate tables, rows = volatility regime, columns = momentum
# bucket, entries = order size. They are synthetic and documented; nothing
# here is a claim about any real model's behaviour.
_OFFLINE = {
    "momentum_follower": {
        "description": "follows recent momentum and trades larger when volatility is elevated",
        "table": [[-1.5, -0.5, 0.0, 0.5, 1.5],
                  [-1.5, -1.5, 0.0, 1.5, 1.5],
                  [-1.5, -1.5, 0.0, 1.5, 1.5]],
    },
    "trend_vol_capped": {
        "description": "follows momentum in calm markets and stands aside when stressed",
        "table": [[-1.5, -0.5, 0.0, 0.5, 1.5],
                  [-0.5, -0.5, 0.0, 0.5, 0.5],
                  [0.0, 0.0, 0.0, 0.0, 0.0]],
    },
    "contrarian": {
        "description": "fades momentum, buying weakness and selling strength",
        "table": [[1.5, 0.5, 0.0, -0.5, -1.5],
                  [1.5, 0.5, 0.0, -0.5, -1.5],
                  [0.5, 0.5, 0.0, -0.5, -0.5]],
    },
}


class PersonaPolicy:
    def __init__(self, name, table, source, description="", prompt_sha256="", model=None):
        table = np.asarray(table, dtype=float)
        if table.shape != (3, 5):
            raise ValueError("persona table must be 3 volatility regimes by 5 momentum buckets")
        if not np.all(np.isin(table, ACTIONS)):
            raise ValueError("persona table entries must be in the action set")
        self.name, self.table, self.source = name, table, source
        self.description, self.prompt_sha256, self.model = description, prompt_sha256, model
        self.table_sha256 = hashlib.sha256(
            json.dumps(table.tolist(), separators=(",", ":")).encode()).hexdigest()

    def action(self, momentum, vol_ratio):
        m = _mom_bucket(momentum)
        v = 0 if vol_ratio < 1.5 else (1 if vol_ratio < 2.5 else 2)
        return float(self.table[v, m])

    def momentum_slope(self):
        """Mean slope of the action against the momentum bucket index; positive
        means the persona follows momentum, the herding channel."""
        grid = np.arange(5, dtype=float)
        return float(np.mean([np.polyfit(grid, row, 1)[0] for row in self.table]))

    def describe(self):
        return {"name": self.name, "source": self.source, "model": self.model,
                "description": self.description, "table": self.table.tolist(),
                "table_sha256": self.table_sha256, "prompt_sha256": self.prompt_sha256,
                "momentum_slope": round(self.momentum_slope(), 4)}


_REGISTRY = {}


def offline_persona(name):
    if name not in _OFFLINE:
        raise KeyError(f"unknown offline persona {name!r}; known: {sorted(_OFFLINE)}")
    spec = _OFFLINE[name]
    return PersonaPolicy(name, spec["table"], "offline_surrogate", spec["description"])


def register(policy):
    _REGISTRY[policy.name] = policy
    return policy


def get_persona(name):
    if name not in _REGISTRY:
        _REGISTRY[name] = offline_persona(name)
    return _REGISTRY[name]


def registry_snapshot():
    return {k: v.describe() for k, v in sorted(_REGISTRY.items())}


def reset_registry():
    _REGISTRY.clear()


ELICIT_SYSTEM = (
    "You are a trading agent built on a foundation model. You are given a market state "
    "and must choose exactly one action from: strong_sell, sell, hold, buy, strong_buy. "
    "Respond ONLY with JSON, no preamble and no markdown fences.")

ELICIT_PROMPT = """Persona: {description}

For every combination of momentum bucket and volatility regime give your action.
Momentum buckets, in order: {mom}.
Volatility regimes, in order: {vol}.

Return {{"table": [[a1..a5 for calm], [a1..a5 for elevated], [a1..a5 for stressed]]}}
where each a is one of strong_sell, sell, hold, buy, strong_buy."""


def elicit_persona(name, description, client, log=None):
    """Ask the configured model for the persona's policy table once, validate
    it, hash it and register it. Any failure registers the offline surrogate
    and records why. Returns the registered PersonaPolicy."""
    prompt = ELICIT_PROMPT.format(description=description, mom=", ".join(MOM_LABELS),
                                  vol=", ".join(VOL_LABELS))
    psha = hashlib.sha256((ELICIT_SYSTEM + "\n" + prompt).encode()).hexdigest()
    if client is None or not getattr(client, "available", False):
        pol = register(offline_persona(name) if name in _OFFLINE else
                       PersonaPolicy(name, _OFFLINE["momentum_follower"]["table"],
                                     "offline_surrogate", description))
        if log is not None:
            log("persona_offline", persona=name, reason="no model configured",
                table_sha256=pol.table_sha256)
        return pol
    try:
        raw = client.complete(prompt, system=ELICIT_SYSTEM, max_tokens=400)
        data = json.loads(re.sub(r"```(json)?", "", raw).strip())
        rows = data["table"]
        table = [[ACTION_WORDS[str(a).strip().lower()] for a in row] for row in rows]
        pol = register(PersonaPolicy(name, table, "model_distilled", description,
                                     prompt_sha256=psha, model=getattr(client, "model", None)))
        if log is not None:
            log("persona_distilled", persona=name, model=pol.model, prompt_sha256=psha,
                table_sha256=pol.table_sha256, momentum_slope=pol.momentum_slope())
        return pol
    except Exception as e:  # noqa: BLE001 - any failure falls back and is recorded
        pol = register(offline_persona(name) if name in _OFFLINE else
                       PersonaPolicy(name, _OFFLINE["momentum_follower"]["table"],
                                     "offline_surrogate", description))
        if log is not None:
            log("persona_elicitation_failed", persona=name, error=str(e)[:200],
                fallback_table_sha256=pol.table_sha256)
        return pol


def bind_persona_hashes(specs, client=None, log=None):
    """At planning time: elicit (or load) every persona the battery names and
    write the table hash into each spec, so a gate approval covers the exact
    policy tables and the simulator refuses a table that has changed."""
    seen = {}
    for sp in specs:
        if sp.persona_share > 0 and sp.persona:
            if sp.persona not in seen:
                desc = _OFFLINE.get(sp.persona, {}).get("description", sp.persona)
                seen[sp.persona] = elicit_persona(sp.persona, desc, client, log) \
                    if client is not None else register(get_persona(sp.persona))
            sp.persona_hash = seen[sp.persona].table_sha256
    return {k: v.describe() for k, v in seen.items()}
