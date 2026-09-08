"""Authority defined agent templates."""

import json

import numpy as np
import pytest

from hsl.agents import (validate_agent, AgentRegistry, register, get_agent, reset_registry, probe, step_flows,
                        agent_hash, bind_agent_hashes, template, MAX_AGENTS)
from hsl.families import validate_family, expand_family
from hsl.simulator import ScenarioSpec, simulate, class_label, scenario_battery, battery_hash


def test_validate_bounds_and_refusals():
    ok, ag, err, notes = validate_agent({"name": "fast_follower", "terms": {"momentum": 9.0, "crowd": 0.5},
                                         "noise": 5.0, "lag": 40})
    assert ok and ag["terms"]["momentum"] == 5.0 and ag["noise"] == 2.0 and ag["lag"] == 10 and len(notes) == 3
    for bad, needle in [({"name": "vendor_x"}, "built in"), ({"name": "bad name"}, "name must"),
                        ({"name": "abc_d", "terms": {"unknown": 1}}, "unknown signal"),
                        ({"name": "abc_d", "terms": {}}, "non empty"),
                        ({"name": "abc_d", "destabilising": "maybe"}, "destabilising"),
                        ({"name": "abc_d", "active_from": 300, "active_until": 200}, "after"),
                        ({"name": "abc_d", "weird": 1}, "unknown key")]:
        ok, ag, err, notes = validate_agent(bad)
        assert not ok and any(needle in e for e in err), (bad, err)
    assert validate_agent(template())[0]


def test_step_flows_gates_bursts_and_draws():
    ok, ag, _, _ = validate_agent({"name": "gated", "terms": {"momentum": 1.0}, "noise": 0.0, "threshold": 0.5,
                                   "withdraw_if_vol_above": 2.0, "burst": {"start": 10, "len": 2, "size": -3.0}})
    rng = np.random.default_rng(0)
    inv = np.zeros(4)
    q = step_flows(ag, 4, 5, {"momentum": 0.2, "vol": 1.0}, rng, inv, 300)
    assert np.allclose(q, 0.0)                                  # below threshold
    q = step_flows(ag, 4, 5, {"momentum": 2.0, "vol": 1.0}, rng, inv, 300)
    assert np.allclose(q, 2.0)                                  # above threshold, no noise
    q = step_flows(ag, 4, 5, {"momentum": 2.0, "vol": 3.0}, rng, inv, 300)
    assert np.allclose(q, 0.0)                                  # withdrawn
    q = step_flows(ag, 4, 11, {"momentum": 0.0, "vol": 1.0}, rng, inv, 300)
    assert np.allclose(q, -3.0)                                 # burst
    r1 = np.random.default_rng(1); r2 = np.random.default_rng(1)
    step_flows(ag, 3, 5, {"momentum": 2.0, "vol": 1.0}, r1, np.zeros(3), 300); r2.normal(0, 1, size=3)
    assert r1.normal() == r2.normal()                           # exactly n draws per step


def test_custom_agents_simulate_label_and_bind():
    reset_registry()
    ok, lp, _, _ = validate_agent({"name": "liq_provider", "terms": {"mispricing": -0.8, "crowd": -0.3}, "noise": 0.4,
                                   "withdraw_if_vol_above": 2.5})
    ok, mom, _, _ = validate_agent({"name": "slow_mom", "terms": {"momentum": 1.5, "vendor_signal_0": 0.8}, "lag": 2,
                                    "noise": 0.3})
    register(lp); register(mom)
    sp = ScenarioSpec(name="c", vendor_shares=(0.30, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                      custom_agents=(("liq_provider", 0.10), ("slow_mom", 0.15)), seed=1)
    bind_agent_hashes([sp])
    assert len(sp.custom_agent_hashes) == 2 and sp.custom_agent_hashes[0] == agent_hash(lp)
    r = simulate(sp)
    assert class_label(-10) == "liq_provider" and (r.agent_cluster == -10).sum() == 12
    assert not r.destabilising[r.agent_cluster == -10].any()      # liquidity provision is not herding
    assert r.destabilising[r.agent_cluster == -11].all()          # a lagged momentum herd is
    sp.custom_agent_hashes = ("0" * 64, sp.custom_agent_hashes[1])
    with pytest.raises(ValueError):
        simulate(sp)
    d = sp.describe()
    assert d["custom_agents"] == [["liq_provider", 0.1], ["slow_mom", 0.15]]
    p = probe(lp)
    assert p["auto_label_destabilising"] is False and p["post_shock_drawdown_with"] < p["post_shock_drawdown_without"]


def test_registry_store_and_family_reference(tmp_path):
    reset_registry()
    reg = AgentRegistry(str(tmp_path))
    res = reg.add({"name": "copier", "terms": {"crowd": 2.0}}, author="D. Godorozha")
    assert res["ok"] and res["record"]["sha256"] == agent_hash(res["record"]["agent"])
    assert get_agent("copier")["terms"]["crowd"] == 2.0
    for i in range(MAX_AGENTS):
        reg.add({"name": f"ag_{i}", "terms": {"momentum": 1.0}}, "x")
    assert not reg.add({"name": "one_more", "terms": {"momentum": 1.0}}, "x")["ok"]
    ok, fam, err, notes = validate_family({"name": "copier_market", "vendor_shares": [0.1, 0.1], "vendor_rhos": [0.8, 0.3],
                                           "frac_fundamental": 0.1, "custom_agents": [{"agent": "copier", "share": 0.9}]})
    assert ok and fam["custom_agents"] == [["copier", 0.45]] and any("clamped" in n for n in notes)
    ok2, fam2, _, _ = validate_family(dict(fam, name="copier_market_b"))          # the stored form round trips
    assert ok2 and fam2["custom_agents"] == [["copier", 0.45]]
    bad = validate_family({"name": "ghost_market", "custom_agents": [{"agent": "ghost", "share": 0.1}]})
    assert not bad[0] and any("unknown agent" in e for e in bad[2])
    specs = expand_family(fam)
    assert specs[0].custom_agents == (("copier", 0.45),)
    reg.remove("copier")
    with pytest.raises(KeyError):
        get_agent("copier")
    reset_registry()


def test_earlier_dynamics_unchanged_without_custom_agents():
    ref = json.load(open("/tmp/sim_ref.json")) if __import__("os").path.exists("/tmp/sim_ref.json") else None
    sp = scenario_battery(include_rl=False, include_reports=False)[0]
    r = simulate(sp)
    assert r.fund_path is not None and r.fund_path[sp.shock_time] == pytest.approx(-sp.shock_size)
    if ref:
        import hashlib
        assert hashlib.sha256(r.prices.tobytes() + r.flows.tobytes() + r.destabilising.tobytes()).hexdigest() == ref[sp.name]
