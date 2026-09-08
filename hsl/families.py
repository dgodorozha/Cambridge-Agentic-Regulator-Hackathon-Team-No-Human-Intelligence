"""Scenario families defined by the authority.

The demonstration battery encodes the families the reports name. A
regulator's own question is often more specific: a market structure they
supervise, a vendor split they have observed, a shock they want to see
repeated with a faulty model or a liquidity withdrawal. This module lets
them define a family as a small JSON document, validated against the same
hard bounds the model planner obeys, expanded into seeded scenarios, and
stored with provenance (who added it, when, the sha256 of the definition)
so that every later battery that includes it says so in its hash and its
ledger.

A family document:

    {"name": "gilt_repo_vendor_split", "note": "two vendors as observed in Q2",
     "seeds": 3, "generator": "shared_signal",
     "vendor_shares": [0.30, 0.20], "vendor_rhos": [0.85, 0.60],
     "shock_size": 0.05, "shock_time": 300,
     "n_agents": 120, "t_steps": 600,
     "frac_fundamental": 0.15, "kappa": 0.015, "sigma": 0.01,
     "evader_cohorts": 0, "manipulator_share": 0.0,
     "persona": "", "persona_share": 0.0,
     "vendor_fault_time": null, "vendor_fault_len": 25, "vendor_fault_signal": -2.0,
     "liquidity_withdrawal_time": null, "liquidity_withdrawal_scale": 0.3,
     "false_shock_len": 0, "quiet": false, "holdout": false}

Only `name` is required; every other key has the default of the
demonstration herd. Names are lower case letters, digits and underscores,
must not collide with a built in family, and every numeric value is
clamped to the bounds below, with the clamping reported so nothing is
changed silently. A family marked `holdout` is never used for calibration
and joins the held out summary; one marked `quiet` has no shock and joins
the false alert measurement (the conformal guarantee is computed on the
built in quiet family only, so a custom quiet family sharpens the
measurement without altering the guarantee).
"""

import datetime
import hashlib
import json
import os
import re

from .simulator import ScenarioSpec, FAMILY_NOTES

BOUNDS = {
    "seeds": (1, 5), "n_agents": (40, 200), "t_steps": (200, 1000),
    "shock_size": (0.0, 0.10), "shock_time": (50, 900),
    "vendor_share": (0.0, 0.45), "vendor_share_sum": (0.0, 0.70), "vendor_rho": (0.0, 0.95),
    "frac_fundamental": (0.05, 0.40), "kappa": (0.005, 0.03), "sigma": (0.005, 0.02),
    "evader_cohorts": (0, 8), "evader_period": (1, 20), "manipulator_share": (0.0, 0.15),
    "ignition_len": (2, 40), "ignition_size": (1.0, 12.0),
    "persona_share": (0.0, 0.45), "persona_noise": (0.05, 1.0),
    "vendor_fault_len": (5, 100), "vendor_fault_signal": (-6.0, 6.0),
    "liquidity_withdrawal_scale": (0.0, 1.0), "false_shock_len": (0, 80),
    "rl_share": (0.0, 0.45),
}
GENERATORS = ("shared_signal", "imitation", "sqrt_impact", "voter")
PERSONAS = ("", "momentum_follower", "trend_vol_capped", "contrarian")
_NAME = re.compile(r"^[a-z][a-z0-9_]{2,31}$")
MAX_VENDORS = 3
MAX_FAMILIES = 12

DEFAULTS = {
    "note": "", "seeds": 3, "generator": "shared_signal",
    "vendor_shares": [0.30, 0.15], "vendor_rhos": [0.80, 0.30],
    "shock_size": 0.05, "shock_time": 300, "n_agents": 120, "t_steps": 600,
    "frac_fundamental": 0.15, "kappa": 0.015, "sigma": 0.01,
    "evader_cohorts": 0, "evader_period": 5, "manipulator_share": 0.0, "ignition_time": None,
    "ignition_len": 8, "ignition_size": 4.0, "persona": "", "persona_share": 0.0, "persona_noise": 0.35,
    "rl_share": 0.0, "vendor_fault_time": None, "vendor_fault_len": 25, "vendor_fault_signal": -2.0,
    "liquidity_withdrawal_time": None, "liquidity_withdrawal_scale": 0.3, "false_shock_len": 0,
    "quiet": False, "holdout": False, "custom_agents": [],
}


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


def validate_family(doc, allow_reserved=False):
    """Validate and normalise a family document. Returns (ok, family,
    errors, notes); `notes` lists every clamped value. `allow_reserved` is
    for the system's own families (the question family), never for the
    library."""
    errors, notes = [], []
    if not isinstance(doc, dict):
        return False, None, ["a family is a JSON object"], notes
    name = str(doc.get("name", "")).strip().lower()
    if not _NAME.match(name):
        errors.append("name must be 3 to 32 lower case letters, digits or underscores, starting with a letter")
    if not allow_reserved and (name in FAMILY_NOTES
                               or name in ("empirical", "quiet", "holdout_herd", "holdout_quiet", "question", "backtest")
                               or name.startswith(("calibrated_", "hybrid_", "backtest_"))):
        errors.append(f"name {name!r} is a built in family")
    fam = dict(DEFAULTS)
    for k in doc:
        if k not in DEFAULTS and k != "name":
            errors.append(f"unknown key {k!r}")
    fam["name"] = name
    fam["note"] = str(doc.get("note", ""))[:240]
    gen = str(doc.get("generator", DEFAULTS["generator"]))
    if gen not in GENERATORS:
        errors.append(f"generator must be one of {GENERATORS}")
    fam["generator"] = gen
    pers = str(doc.get("persona", ""))
    if pers not in PERSONAS:
        errors.append(f"persona must be one of {PERSONAS}")
    fam["persona"] = pers
    shares = doc.get("vendor_shares", DEFAULTS["vendor_shares"])
    rhos = doc.get("vendor_rhos", DEFAULTS["vendor_rhos"])
    if not isinstance(shares, (list, tuple)) or not isinstance(rhos, (list, tuple)) or len(shares) != len(rhos):
        errors.append("vendor_shares and vendor_rhos must be lists of the same length")
        shares, rhos = DEFAULTS["vendor_shares"], DEFAULTS["vendor_rhos"]
    if len(shares) > MAX_VENDORS:
        errors.append(f"at most {MAX_VENDORS} vendors")
    lo, hi = BOUNDS["vendor_share"]
    shares = [_clamp("vendor_share", s, lo, hi, notes) for s in shares]
    lo, hi = BOUNDS["vendor_rho"]
    rhos = [_clamp("vendor_rho", r, lo, hi, notes) for r in rhos]
    if any(v is None for v in shares + rhos):
        errors.append("vendor shares and rhos must be numbers")
    else:
        if sum(shares) > BOUNDS["vendor_share_sum"][1]:
            errors.append(f"vendor shares sum to {sum(shares):.2f}, above {BOUNDS['vendor_share_sum'][1]}")
        fam["vendor_shares"], fam["vendor_rhos"] = [float(s) for s in shares], [float(r) for r in rhos]
    for key in ("seeds", "n_agents", "t_steps", "shock_time", "evader_cohorts", "evader_period",
                "ignition_len", "vendor_fault_len", "false_shock_len"):
        if key in doc and doc[key] is not None:
            v = _clamp(key, doc[key], *BOUNDS[key], notes)
            if v is not None:
                fam[key] = int(round(v))
    for key in ("shock_size", "frac_fundamental", "kappa", "sigma", "manipulator_share", "ignition_size",
                "persona_share", "persona_noise", "vendor_fault_signal", "liquidity_withdrawal_scale", "rl_share"):
        if key in doc and doc[key] is not None:
            v = _clamp(key, doc[key], *BOUNDS[key], notes)
            if v is not None:
                fam[key] = float(v)
    for key in ("ignition_time", "vendor_fault_time", "liquidity_withdrawal_time"):
        if key in doc and doc[key] is not None:
            v = _clamp(key, doc[key], 1, fam["t_steps"] - 1, notes)
            fam[key] = None if v is None else int(round(v))
    agents = doc.get("custom_agents", []) or []
    if not isinstance(agents, list):
        errors.append("custom_agents must be a list of {agent, share}")
        agents = []
    ca = []
    for item in agents:
        # accepted as {"agent": name, "share": x} or as the stored form [name, x]
        if isinstance(item, (list, tuple)) and len(item) == 2:
            item = {"agent": item[0], "share": item[1]}
        if not isinstance(item, dict) or "agent" not in item:
            errors.append("each custom agent needs an agent name and a share")
            continue
        try:
            from .agents import get_agent, BOUNDS as ABOUNDS
            get_agent(str(item["agent"]))
        except KeyError as e:
            errors.append(str(e))
            continue
        sh = _clamp(f"custom_agents.{item['agent']}.share", item.get("share", 0.1), *ABOUNDS["share"], notes)
        if sh is not None:
            ca.append([str(item["agent"]), float(sh)])
    fam["custom_agents"] = ca
    fam["quiet"] = bool(doc.get("quiet", False))
    fam["holdout"] = bool(doc.get("holdout", False))
    if fam["quiet"]:
        fam["shock_size"] = 0.0
    if fam["persona_share"] > 0 and not fam["persona"]:
        errors.append("persona_share needs a persona")
    if fam["manipulator_share"] > 0 and fam["ignition_time"] is None:
        fam["ignition_time"] = max(1, fam["shock_time"] - 5)
        notes.append("ignition_time defaulted to five steps before the shock")
    total = sum(fam["vendor_shares"]) + fam["frac_fundamental"] + fam["manipulator_share"] + \
        fam["persona_share"] + fam["rl_share"] + sum(x[1] for x in fam.get("custom_agents", []))
    if total > 0.95:
        errors.append(f"agent shares sum to {total:.2f}; leave at least 5% for noise traders")
    for t_key in ("shock_time", "vendor_fault_time", "liquidity_withdrawal_time", "ignition_time"):
        if fam.get(t_key) is not None and fam[t_key] >= fam["t_steps"] - 10:
            errors.append(f"{t_key} must be at least ten steps before the end of the run")
    return (not errors), (fam if not errors else None), errors, notes


def family_hash(fam):
    return hashlib.sha256(json.dumps(fam, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def expand_family(fam, seed0=0):
    """Seeded scenarios for a validated family. Seeds are derived from the
    family hash so two families with the same parameters and different
    names still get different draws, and the same family always gets the
    same seeds."""
    base = int(family_hash(fam)[:6], 16) % 100000
    specs = []
    for s in range(int(fam["seeds"])):
        specs.append(ScenarioSpec(
            name=f"{fam['name']}_{s}", family=fam["name"],
            n_agents=fam["n_agents"], t_steps=fam["t_steps"],
            vendor_shares=tuple(fam["vendor_shares"]), vendor_rhos=tuple(fam["vendor_rhos"]),
            frac_fundamental=fam["frac_fundamental"], kappa=fam["kappa"], sigma=fam["sigma"],
            shock_time=None if fam["quiet"] else fam["shock_time"], shock_size=fam["shock_size"],
            generator=fam["generator"], evader_cohorts=fam["evader_cohorts"], evader_period=fam["evader_period"],
            manipulator_share=fam["manipulator_share"], ignition_time=fam["ignition_time"],
            ignition_len=fam["ignition_len"], ignition_size=fam["ignition_size"],
            persona=fam["persona"], persona_share=fam["persona_share"], persona_noise=fam["persona_noise"],
            rl_share=fam["rl_share"], rl_seed=seed0 + base + s,
            vendor_fault_time=fam["vendor_fault_time"], vendor_fault_len=fam["vendor_fault_len"],
            vendor_fault_signal=fam["vendor_fault_signal"],
            liquidity_withdrawal_time=fam["liquidity_withdrawal_time"],
            liquidity_withdrawal_scale=fam["liquidity_withdrawal_scale"],
            false_shock_len=fam["false_shock_len"], holdout=fam["holdout"],
            custom_agents=tuple((a, sh) for a, sh in fam.get("custom_agents", [])),
            seed=seed0 + base + s))
    return specs


def template():
    return dict(DEFAULTS, name="my_family", note="describe the market structure and why it matters")


class FamilyStore:
    """Families the authority has defined, kept in `<runs_dir>/families.json`
    with provenance. `enabled` families join every later plan."""

    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "families.json")

    def _load(self):
        if not os.path.isfile(self.path):
            return []
        with open(self.path) as f:
            try:
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

    def add(self, doc, author=""):
        ok, fam, errors, notes = validate_family(doc)
        if not ok:
            return {"ok": False, "errors": errors, "notes": notes}
        items = [x for x in self._load() if x["family"]["name"] != fam["name"]]
        if len(items) >= MAX_FAMILIES:
            return {"ok": False, "errors": [f"at most {MAX_FAMILIES} families; remove one first"], "notes": notes}
        rec = {"family": fam, "sha256": family_hash(fam), "author": (author or "")[:80],
               "added": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "enabled": True}
        items.append(rec)
        self._save(items)
        return {"ok": True, "record": rec, "notes": notes, "errors": []}

    def remove(self, name):
        items = self._load()
        keep = [x for x in items if x["family"]["name"] != name]
        self._save(keep)
        return len(keep) < len(items)

    def set_enabled(self, name, enabled):
        items = self._load()
        for x in items:
            if x["family"]["name"] == name:
                x["enabled"] = bool(enabled)
        self._save(items)

    def enabled(self):
        return [x for x in self._load() if x.get("enabled", True)]

    def specs(self, seed0=0):
        out, notes = [], {}
        for x in self.enabled():
            out.extend(expand_family(x["family"], seed0))
            notes[x["family"]["name"]] = x["family"]["note"] or "custom family"
        return out, notes


def load_family_file(path):
    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def main(argv=None):
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="python -m hsl.families")
    ap.add_argument("command", choices=["validate", "template", "expand"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--agent", action="append", default=None,
                    help="agent template file(s) the family references; repeatable")
    ap.add_argument("--store", default=None, help="directory whose agents.json holds stored agent templates")
    args = ap.parse_args(argv)
    if args.command == "template":
        print(json.dumps(template(), indent=1))
        return 0
    from .agents import AgentRegistry, load_agent_file, validate_agent, register
    if args.store:
        AgentRegistry(args.store).load_all()
    for p in (args.agent or []):
        for d in load_agent_file(p):
            ok, ag, errors, notes = validate_agent(d)
            if ok:
                register(ag)
    docs = load_family_file(args.path)
    rc = 0
    for doc in docs:
        ok, fam, errors, notes = validate_family(doc)
        print(json.dumps({"name": doc.get("name"), "ok": ok, "errors": errors, "notes": notes,
                          "sha256": family_hash(fam) if ok else None,
                          "scenarios": [s.name for s in expand_family(fam)] if (ok and args.command == "expand") else None},
                         indent=1))
        rc |= 0 if ok else 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
