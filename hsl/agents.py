"""Agents defined by the authority.

The built in classes (noise traders, fundamentalists, vendor clusters, RL
policies, LLM personas, colluding manipulators) cover the herding
literature. A supervisor may want an agent that is not there: an AI
liquidity provider that withdraws above a volatility level, a slow
momentum follower with a two step lag, a contrarian subscribed to vendor
A's model, a strategy that fires a burst at a time. This module lets them
define one as a JSON document in a small declarative language, with no
code execution: an agent's order flow at each step is a bounded linear
combination of named market signals, gated, lagged, capped and noised.

    {"name": "ai_liquidity_provider", "note": "provides liquidity, withdraws in stress",
     "terms": {"mispricing": -0.8, "crowd": -0.3},
     "noise": 0.4, "cap": 3.0, "threshold": 0.0, "lag": 0,
     "withdraw_if_vol_above": 2.5,
     "active_from": null, "active_until": null,
     "burst": {"start": null, "len": 0, "size": 0.0},
     "destabilising": "auto"}

Signals (each a number at step t, standardised where noted):
  momentum         recent mean return over its standard deviation, clipped
                   to plus or minus three (the signal vendor clusters and
                   personas read)
  mispricing       (log price minus fundamental) / 0.02, positive when the
                   market is above fundamental
  last_return      the previous step's return over sigma
  vol              recent volatility over normal volatility (1 is normal)
  crowd            mean order flow of every agent at the previous step
  inventory        the agent's own decayed cumulative flow
  vendor_signal_0  the shared signal of vendor cluster 0 (1, 2 likewise):
                   subscribing to a vendor's model is the monoculture channel
  time             steps since the shock, or 0 before it

Flow = clip(sum of coefficient times signal, -cap, cap) + noise * z, with z
a standard normal per agent per step; zero when the gate is off (below the
threshold, outside the active window, or withdrawn above the volatility
level); a burst adds a fixed size for `len` steps from `start`. Every
coefficient and parameter is bounded and clamps are reported.

Ground truth: `destabilising` may be true, false or "auto". Auto labels the
class destabilising when it is large (share at or above the battery's
threshold) and its realised behaviour amplifies the shock (its flows
after the shock move with the returns) with its members acting together
(mean pairwise flow correlation at least 0.5), the same test the RL class
faces. The definition is hashed, stored with author and time, bound into
the battery at Gate 1 and written to the ledger.
"""

import datetime
import hashlib
import json
import os
import re

import numpy as np

SIGNALS = ("momentum", "mispricing", "last_return", "vol", "crowd", "inventory",
           "vendor_signal_0", "vendor_signal_1", "vendor_signal_2", "time")
BOUNDS = {"coef": (-5.0, 5.0), "noise": (0.0, 2.0), "cap": (0.5, 8.0), "threshold": (0.0, 3.0),
          "lag": (0, 10), "withdraw_if_vol_above": (1.0, 6.0), "active_from": (0, 999), "active_until": (1, 1000),
          "burst_len": (0, 60), "burst_size": (-8.0, 8.0), "burst_start": (1, 999), "share": (0.02, 0.45)}
_NAME = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
RESERVED = {"noise_trader", "fundamentalist", "rl_policy", "manipulator", "llm_persona", "vendor"}
MAX_AGENTS = 12
CUSTOM_BASE = -10        # class codes -10, -11, ... are custom agent groups

DEFAULTS = {"note": "", "terms": {"momentum": 1.0}, "noise": 0.5, "cap": 3.0, "threshold": 0.0, "lag": 0,
            "withdraw_if_vol_above": None, "active_from": None, "active_until": None,
            "burst": {"start": None, "len": 0, "size": 0.0}, "destabilising": "auto"}


def _clamp(name, value, lo, hi, notes):
    try:
        v = float(value)
    except (TypeError, ValueError):
        notes.append(f"{name}: not a number, default used")
        return None
    c = min(hi, max(lo, v))
    if c != v:
        notes.append(f"{name}: {v} clamped to {c}")
    return c


def validate_agent(doc):
    """Validate and normalise an agent document. Returns (ok, agent,
    errors, notes)."""
    errors, notes = [], []
    if not isinstance(doc, dict):
        return False, None, ["an agent is a JSON object"], notes
    name = str(doc.get("name", "")).strip().lower()
    if not _NAME.match(name):
        errors.append("name must be 3 to 32 lower case letters, digits or underscores, starting with a letter")
    if name in RESERVED or name.startswith("vendor_"):
        errors.append(f"name {name!r} is a built in class")
    for k in doc:
        if k not in DEFAULTS and k != "name":
            errors.append(f"unknown key {k!r}")
    ag = json.loads(json.dumps(DEFAULTS))
    ag["name"] = name
    ag["note"] = str(doc.get("note", ""))[:240]
    terms = doc.get("terms", DEFAULTS["terms"])
    if not isinstance(terms, dict) or not terms:
        errors.append("terms must be a non empty object of signal: coefficient")
        terms = {}
    clean = {}
    for sig, coef in terms.items():
        if sig not in SIGNALS:
            errors.append(f"unknown signal {sig!r}; known: {', '.join(SIGNALS)}")
            continue
        v = _clamp(f"terms.{sig}", coef, *BOUNDS["coef"], notes)
        if v is not None:
            clean[sig] = v
    ag["terms"] = clean
    for key in ("noise", "cap", "threshold"):
        if key in doc and doc[key] is not None:
            v = _clamp(key, doc[key], *BOUNDS[key], notes)
            if v is not None:
                ag[key] = v
    if "lag" in doc and doc["lag"] is not None:
        v = _clamp("lag", doc["lag"], *BOUNDS["lag"], notes)
        ag["lag"] = int(round(v)) if v is not None else 0
    for key in ("withdraw_if_vol_above", "active_from", "active_until"):
        if key in doc and doc[key] is not None:
            v = _clamp(key, doc[key], *BOUNDS[key], notes)
            ag[key] = (None if v is None else (float(v) if key == "withdraw_if_vol_above" else int(round(v))))
    burst = doc.get("burst") or {}
    if not isinstance(burst, dict):
        errors.append("burst must be an object with start, len and size")
        burst = {}
    b = dict(DEFAULTS["burst"])
    if burst.get("start") is not None:
        v = _clamp("burst.start", burst["start"], *BOUNDS["burst_start"], notes)
        b["start"] = int(round(v)) if v is not None else None
    if burst.get("len") is not None:
        v = _clamp("burst.len", burst["len"], *BOUNDS["burst_len"], notes)
        b["len"] = int(round(v)) if v is not None else 0
    if burst.get("size") is not None:
        v = _clamp("burst.size", burst["size"], *BOUNDS["burst_size"], notes)
        b["size"] = float(v) if v is not None else 0.0
    ag["burst"] = b
    dz = doc.get("destabilising", "auto")
    if dz not in (True, False, "auto"):
        errors.append("destabilising must be true, false or 'auto'")
    ag["destabilising"] = dz
    if ag["active_from"] is not None and ag["active_until"] is not None and ag["active_until"] <= ag["active_from"]:
        errors.append("active_until must be after active_from")
    return (not errors), (ag if not errors else None), errors, notes


def agent_hash(ag):
    return hashlib.sha256(json.dumps(ag, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def template():
    return {"name": "my_agent", "note": "describe the strategy and why it matters",
            "terms": {"momentum": 1.0, "crowd": 0.5, "mispricing": -0.2}, "noise": 0.5, "cap": 3.0,
            "threshold": 0.0, "lag": 0, "withdraw_if_vol_above": None, "active_from": None,
            "active_until": None, "burst": {"start": None, "len": 0, "size": 0.0}, "destabilising": "auto"}


class AgentRegistry:
    """Agent templates the authority has defined, in `<runs_dir>/agents.json`
    with provenance. The simulator resolves names through the module level
    registry, which the store loads."""

    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "agents.json")

    def _load(self):
        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def _save(self, items):
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(items, f, indent=1)
        os.replace(tmp, self.path)

    def list(self):
        return self._load()

    def get(self, name):
        for x in self._load():
            if x["agent"]["name"] == name:
                return x
        return None

    def add(self, doc, author=""):
        ok, ag, errors, notes = validate_agent(doc)
        if not ok:
            return {"ok": False, "errors": errors, "notes": notes}
        items = [x for x in self._load() if x["agent"]["name"] != ag["name"]]
        if len(items) >= MAX_AGENTS:
            return {"ok": False, "errors": [f"at most {MAX_AGENTS} agents; remove one first"], "notes": notes}
        rec = {"agent": ag, "sha256": agent_hash(ag), "author": (author or "")[:80],
               "added": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        items.append(rec)
        self._save(items)
        register(ag)
        return {"ok": True, "record": rec, "notes": notes, "errors": []}

    def remove(self, name):
        items = self._load()
        keep = [x for x in items if x["agent"]["name"] != name]
        self._save(keep)
        _REGISTRY.pop(name, None)
        return len(keep) < len(items)

    def load_all(self):
        for x in self._load():
            register(x["agent"])
        return list(_REGISTRY)


_REGISTRY = {}


def register(ag):
    _REGISTRY[ag["name"]] = ag
    return ag


def get_agent(name):
    if name not in _REGISTRY:
        raise KeyError(f"unknown agent {name!r}; define it in the agent workshop or pass --agent")
    return _REGISTRY[name]


def registry_snapshot():
    return {k: dict(v, sha256=agent_hash(v)) for k, v in sorted(_REGISTRY.items())}


def reset_registry():
    _REGISTRY.clear()


def step_flows(ag, n, t, signals, rng, inventory, shock_time):
    """Order flow of n agents of one template at step t. `signals` is the
    dict of scalar signals; `inventory` the per agent decayed cumulative
    flow (updated in place). Draws exactly n standard normals."""
    z = rng.normal(0.0, 1.0, size=n)
    s = 0.0
    for sig, coef in ag["terms"].items():
        if sig == "inventory":
            continue
        s += coef * float(signals.get(sig, 0.0))
    base = np.full(n, s) + ag["terms"].get("inventory", 0.0) * inventory
    base = np.clip(base, -ag["cap"], ag["cap"])
    gate = np.ones(n, dtype=bool)
    if ag["threshold"] > 0:
        gate &= np.abs(base) >= ag["threshold"]
    if ag["withdraw_if_vol_above"] is not None and signals.get("vol", 1.0) > ag["withdraw_if_vol_above"]:
        gate[:] = False
    if ag["active_from"] is not None and t < ag["active_from"]:
        gate[:] = False
    if ag["active_until"] is not None and t > ag["active_until"]:
        gate[:] = False
    q = np.where(gate, base + ag["noise"] * z, 0.0)
    b = ag["burst"]
    if b.get("start") is not None and b.get("len", 0) > 0 and b["start"] <= t < b["start"] + b["len"]:
        q = q + b["size"]
    inventory *= 0.9
    inventory += q
    return q


def auto_destabilising(flows, prices, fund_path, slots, shock_time, share, share_crit):
    """Ground truth for an auto labelled class: large (share at or above the
    battery threshold), acting together (mean pairwise flow correlation at
    least 0.5) and pushing the price away from fundamental after the shock
    (its flow has the sign of the mispricing: buying above fundamental,
    selling below it). Trading the price toward fundamental, however hard,
    is liquidity provision, not herding."""
    if share < share_crit or shock_time is None or len(slots) < 2:
        return False
    T = len(prices)
    w = slice(shock_time, min(T, shock_time + 80))
    mp = prices[max(0, shock_time - 1):min(T, shock_time + 80) - 1] - fund_path[w]   # price minus fundamental, lagged
    push = float((flows[w][:, slots] * np.sign(mp)[:, None]).sum())   # with the mispricing: away from fundamental
    C = np.corrcoef(flows[100:, slots].T)
    iu = np.triu_indices(len(slots), 1)
    vals = C[iu][np.isfinite(C[iu])]
    mean_corr = float(vals.mean()) if len(vals) else 0.0
    return bool(push > 0 and mean_corr >= 0.5)


def probe(ag, share=0.20, seed=0):
    """What does this agent do? One herd market with the agent at `share`:
    its behaviour signature and whether auto labelling would mark it
    destabilising. Imported lazily to avoid a cycle with the simulator."""
    from .simulator import ScenarioSpec, simulate
    register(ag)
    sp = ScenarioSpec(name="probe", vendor_shares=(0.30, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                      custom_agents=((ag["name"], float(share)),), seed=seed)
    base = ScenarioSpec(name="probe_base", vendor_shares=(0.30, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                        seed=seed)
    r, r0 = simulate(sp), simulate(base)
    slots = np.where(r.agent_cluster <= CUSTOM_BASE)[0]
    f = r.flows[:, slots]
    mom = np.array([r.returns[max(0, t - 20):t].mean() / (r.returns[max(0, t - 20):t].std() + 1e-6)
                    if t > 5 else 0.0 for t in range(r.flows.shape[0])])
    corr_mom = float(np.corrcoef(f.mean(axis=1)[100:], mom[100:])[0, 1]) if f.shape[1] else None
    C = np.corrcoef(f[100:].T) if f.shape[1] > 1 else np.array([[1.0]])
    iu = np.triu_indices(f.shape[1], 1)
    w = slice(sp.shock_time, sp.shock_time + 80)
    return {"share": float(share), "n_agents": int(len(slots)),
            "mean_abs_flow": float(np.abs(f).mean()),
            "corr_with_momentum": None if corr_mom is None or corr_mom != corr_mom else corr_mom,
            "mean_pairwise_corr": float(np.nanmean(C[iu])) if len(iu[0]) else None,
            "amplification_after_shock": float((f[w] * r.returns[w, None]).sum()),
            "overshoot_push": float((f[w] * np.sign(r.prices[sp.shock_time - 1:sp.shock_time + 79] -
                                                  r.fund_path[w])[:, None]).sum()),
            "post_shock_drawdown_with": float(r.post_shock_drawdown()),
            "post_shock_drawdown_without": float(r0.post_shock_drawdown()),
            "auto_label_destabilising": bool(r.destabilising[slots].all()) if len(slots) else False,
            "active_share_of_steps": float((np.abs(f) > 1e-9).mean())}


def load_agent_file(path):
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def main(argv=None):
    import argparse
    import importlib
    import sys
    # under `python -m hsl.agents` this file runs as __main__ while the simulator
    # imports hsl.agents: delegate so one registry serves both
    real = importlib.import_module("hsl.agents")
    if real is not sys.modules[__name__]:
        return real.main(argv)
    ap = argparse.ArgumentParser(prog="python -m hsl.agents")
    ap.add_argument("command", choices=["validate", "template", "probe"])
    ap.add_argument("path", nargs="?")
    args = ap.parse_args(argv)
    if args.command == "template":
        print(json.dumps(template(), indent=1))
        return 0
    rc = 0
    for doc in load_agent_file(args.path):
        ok, ag, errors, notes = validate_agent(doc)
        out = {"name": doc.get("name"), "ok": ok, "errors": errors, "notes": notes,
               "sha256": agent_hash(ag) if ok else None}
        if ok and args.command == "probe":
            out["probe"] = probe(ag)
        print(json.dumps(out, indent=1))
        rc |= 0 if ok else 1
    sys.exit(rc)


if __name__ == "__main__":
    main()


def bind_agent_hashes(specs, log=None):
    """At planning: write the hash of every referenced agent definition into
    the specs, so Gate 1 covers the definitions and the simulator refuses
    one that has changed. Returns the definitions used."""
    used = {}
    for sp in specs:
        if not sp.custom_agents:
            continue
        hashes = []
        for name, _share in sp.custom_agents:
            ag = get_agent(str(name))
            used[ag["name"]] = dict(ag, sha256=agent_hash(ag))
            hashes.append(agent_hash(ag))
        sp.custom_agent_hashes = tuple(hashes)
    if log is not None and used:
        log("agents_bound", agents={k: v["sha256"] for k, v in used.items()})
    return used
