"""Version 3 tests: new agent classes and generators, personas, herding
sentinels, conformal certification, attribution, audits, red team, rule
library, frontier, critic, briefing and ASK. Small batteries throughout."""

import json

import numpy as np
import pytest

from hsl.ask import answer, intent_of
from hsl.attribution import shapley_attribution, groups_of
from hsl.briefing import draft_briefing
from hsl.conformal import certify, conformal_p, conformal_threshold
from hsl.critic import critic_check, numbers_in
from hsl.evaluate import ALL_RULES, decision_scores
from hsl.frontier import sentinel_frontier, rule_frontier
from hsl.herding import HERDING_SENTINELS, hawkes_branching_ratio, ImbalanceSentinel, LeadLagSentinel
from hsl.ledger import Ledger
from hsl.personas import (PersonaPolicy, elicit_persona, get_persona, offline_persona, reset_registry,
                          bind_persona_hashes)
from hsl.pipeline import run_battery
from hsl.redteam import adversarial_search, _FakeClient
from hsl.rules import LULDStyleBand, MarketWideBreaker, VenueVolatilityHalt, RULE_LIBRARY
from hsl.sentinels import ALL_SENTINELS, CORE_SENTINELS, SENTINEL_LABELS
from hsl.simulator import ScenarioSpec, simulate, scenario_battery, battery_hash, class_label

from test_core import small_specs


def v3_specs():
    specs = small_specs()
    specs.append(ScenarioSpec(name="ignition_0", family="ignition", vendor_shares=(0.20, 0.15),
                              vendor_rhos=(0.65, 0.30), shock_size=0.04, manipulator_share=0.08,
                              ignition_time=195, ignition_len=10, ignition_size=8.0, seed=600,
                              t_steps=400, n_agents=80, shock_time=200))
    specs.append(ScenarioSpec(name="persona_llm_0", family="persona_llm", vendor_shares=(0.15,),
                              vendor_rhos=(0.30,), frac_fundamental=0.15, persona="momentum_follower",
                              persona_share=0.35, shock_size=0.05, seed=650, t_steps=400, n_agents=80,
                              shock_time=200))
    for s in range(6):
        specs.append(ScenarioSpec(name=f"quiet_{s + 2}", family="quiet", vendor_shares=(0.25, 0.15),
                                  vendor_rhos=(0.45, 0.25), shock_time=None, seed=903 + s,
                                  t_steps=400, n_agents=80))
    reset_registry()
    bind_persona_hashes(specs)
    return specs


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("run3")
    specs = v3_specs()
    log = Ledger(str(d / "ledger.jsonl"), "20260905-000000-abcd", secret="test-secret",
                 actor="orchestrator")
    art, ex = run_battery(specs, log, question="v3 test?", bootstrap_B=60,
                          assurance={"truth_families": ["herd_high", "herd_mid"], "truth_n_quiet": 2,
                                     "redteam_budget": 4, "dose_seeds": (0,)})
    return {"dir": d, "specs": specs, "log": log, "art": art, "ex": ex}


# ------------------------------------------------------------ simulator --

def test_new_fields_default_preserve_v2_hash_semantics():
    a = ScenarioSpec(name="x", seed=1)
    d = a.describe()
    assert d["generator"] == "shared_signal" and d["manipulator_share"] == 0.0 and d["persona"] == ""
    assert simulate(a).agent_cluster.min() >= -2


def test_manipulators_ignite_and_are_positives():
    sp = ScenarioSpec(name="ig", vendor_shares=(0.20, 0.15), vendor_rhos=(0.65, 0.30), shock_size=0.04,
                      manipulator_share=0.08, ignition_time=295, ignition_len=10, ignition_size=8.0,
                      seed=600)
    res = simulate(sp)
    m = res.agent_cluster == -4
    assert m.sum() == round(0.08 * sp.n_agents) and res.destabilising[m].all()
    burst = res.flows[295:305][:, m].mean()
    rev = res.flows[305:325][:, m].mean()
    assert burst < -6 and rev > 3
    assert class_label(-4) == "manipulator" and class_label(-5) == "llm_persona"


def test_persona_group_shares_one_table_and_is_labelled():
    reset_registry()
    sp = ScenarioSpec(name="p", vendor_shares=(0.15,), vendor_rhos=(0.30,), persona="momentum_follower",
                      persona_share=0.35, shock_size=0.05, seed=650)
    res = simulate(sp)
    p = res.agent_cluster == -5
    assert p.sum() == round(0.35 * sp.n_agents) and res.destabilising[p].all()
    C = np.corrcoef(res.flows[100:, p].T)
    iu = np.triu_indices(p.sum(), 1)
    assert np.nanmean(C[iu]) > 0.5


def test_persona_hash_binding_refuses_changed_table():
    reset_registry()
    sp = ScenarioSpec(name="p", vendor_shares=(0.15,), vendor_rhos=(0.30,), persona="momentum_follower",
                      persona_share=0.35, seed=1, t_steps=200, n_agents=60, shock_time=100)
    bind_persona_hashes([sp])
    assert len(sp.persona_hash) == 64
    simulate(sp)
    sp.persona_hash = "0" * 64
    with pytest.raises(ValueError):
        simulate(sp)


def test_generators_differ_and_imitation_herds():
    base = ScenarioSpec(name="g", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30), shock_size=0.05,
                        seed=0)
    a = simulate(base)
    b = simulate(ScenarioSpec(**dict(base.describe(), generator="imitation", vendor_shares=(0.40, 0.15),
                                     vendor_rhos=(0.90, 0.30))))
    c = simulate(ScenarioSpec(**dict(base.describe(), generator="sqrt_impact", vendor_shares=(0.40, 0.15),
                                     vendor_rhos=(0.90, 0.30))))
    assert not np.allclose(a.prices, b.prices) and not np.allclose(a.prices, c.prices)
    assert b.post_shock_drawdown() > 0.08 and b.pre_shock_vol() > a.pre_shock_vol() * 0.5
    with pytest.raises(ValueError):
        simulate(ScenarioSpec(name="bad", generator="nope"))


def test_battery_has_v3_families_and_eight_quiet():
    specs = scenario_battery(include_rl=False)
    fams = {s.family for s in specs}
    assert {"ignition", "persona_llm", "evader", "holdout_herd"} <= fams
    assert sum(1 for s in specs if s.quiet and not s.holdout) == 8


# ------------------------------------------------------------- personas --

def test_persona_elicitation_validates_and_falls_back():
    reset_registry()
    good = json.dumps({"table": [["strong_sell", "sell", "hold", "buy", "strong_buy"]] * 3})
    pol = elicit_persona("momentum_follower", "d", _FakeClient(good))
    assert pol.source == "model_distilled" and pol.momentum_slope() > 0 and len(pol.table_sha256) == 64
    reset_registry()
    bad = elicit_persona("momentum_follower", "d", _FakeClient("garbage"))
    assert bad.source == "offline_surrogate"
    assert get_persona("contrarian").momentum_slope() < 0
    with pytest.raises(ValueError):
        PersonaPolicy("x", [[0.0] * 5] * 2, "offline_surrogate")
    with pytest.raises(ValueError):
        PersonaPolicy("x", [[0.3] * 5] * 3, "offline_surrogate")
    assert offline_persona("trend_vol_capped").action(2.5, 3.0) == 0.0
    reset_registry()


# ------------------------------------------------------------ sentinels --

def test_seven_sentinels_registered_with_labels():
    assert len(ALL_SENTINELS) == 8 and len(CORE_SENTINELS) == 4
    assert {S.name for S in HERDING_SENTINELS} == {"imbalance", "endogeneity", "lead_lag", "tail_dependence"}
    assert all(S.name in SENTINEL_LABELS for S in ALL_SENTINELS)


def test_herding_sentinels_online_flags_and_detection():
    res = simulate(ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                                shock_size=0.05, seed=1))
    for S in HERDING_SENTINELS:
        out = S().run(res)
        fo = out["flags_online"]
        assert fo.shape == res.flows.shape
        if out["first_alert"] is None:
            assert not fo.any()
        else:
            assert not fo[:out["first_alert"]].any() and np.array_equal(fo[-1], out["flags"])
    imb = ImbalanceSentinel().run(res)
    assert imb["first_alert"] is not None and decision_scores(res, imb)["f1"] > 0.9
    quiet = simulate(ScenarioSpec(name="q", vendor_shares=(0.25, 0.15), vendor_rhos=(0.45, 0.25),
                                  shock_time=None, seed=901))
    assert ImbalanceSentinel().run(quiet)["first_alert"] is None
    assert LeadLagSentinel().run(quiet)["first_alert"] is None


def test_lead_lag_finds_ignitors():
    sp = ScenarioSpec(name="ig", vendor_shares=(0.20, 0.15), vendor_rhos=(0.65, 0.30), shock_size=0.04,
                      manipulator_share=0.08, ignition_time=295, ignition_len=10, ignition_size=8.0,
                      seed=601)
    res = simulate(sp)
    out = LeadLagSentinel().run(res)
    assert out["first_alert"] is not None
    m = res.agent_cluster == -4
    assert out["flags"][m].mean() > 0.5


def test_hawkes_branching_ratio_orders_clustered_before_poisson():
    rng = np.random.default_rng(0)
    poisson = np.sort(rng.uniform(0, 300, 60))
    n_p = hawkes_branching_ratio(poisson, 300.0)[0]
    # self excited: each parent spawns a cluster of children just after it
    parents = np.sort(rng.uniform(0, 300, 15))
    kids = np.concatenate([p + rng.exponential(2.0, 3) for p in parents])
    clustered = np.sort(np.concatenate([parents, kids]))
    n_c = hawkes_branching_ratio(clustered, 300.0)[0]
    assert 0 <= n_p < 0.99 and n_c > n_p and n_c > 0.4


# ------------------------------------------------------------- conformal --

def test_conformal_p_and_threshold_arithmetic():
    cal = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    assert conformal_p(0.9, cal) == pytest.approx(1 / 9)
    assert conformal_p(0.05, cal) == pytest.approx(1.0)
    thr = conformal_threshold(cal, 0.25)     # k = floor(0.25 * 9) - 1 = 1 -> second largest
    assert thr == 0.7
    assert conformal_threshold(cal[:2], 0.25) is None


def test_certify_reports_guarantee_and_power(run):
    cert = certify(run["ex"]["rows"], [S.name for S in ALL_SENTINELS])
    for v in cert.values():
        assert v["n_calibration"] == 8 and v["guarantee_achievable"]
        assert v["guaranteed_false_alert_bound"] == 0.25
        assert 0 <= v["power_calibration_herd"] <= 1
        assert v["n_holdout_quiet"] == 1


# ----------------------------------------------------------- attribution --

def test_shapley_efficiency_and_top_group():
    sp = ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30), shock_size=0.05,
                      seed=0, t_steps=400, n_agents=80, shock_time=200)
    res = simulate(sp)
    attr = shapley_attribution(sp, res)
    assert set(attr["groups"]) == {"vendor_A", "vendor_B"}
    assert abs(attr["efficiency_residual"]) < 1e-9
    assert attr["impact_ordering"][0] == "vendor_A"
    assert set(groups_of(res)) == {"vendor_A", "vendor_B"}


# ---------------------------------------------------------------- audits --

def test_truth_dependence_and_dose_response(run):
    ta = run["art"]["truth_audit"]
    assert set(ta["generators"]) == {"shared_signal", "imitation", "voter", "sqrt_impact"}
    for c in ta["comparison"].values():
        assert -1 <= c["tau_vs_shared_signal"] <= 1 and c["max_rank_shift"] >= 0
    dose = run["art"]["concentration"]
    assert len(dose["levels"]) == 9 and dose["levels"][0]["share"] == 0.10
    assert all(0 <= l["dislocation_prob"] <= 1 for l in dose["levels"])
    assert "curvature" in dose and isinstance(dose["convex"], bool)


# -------------------------------------------------------------- red team --

def test_adversarial_search_bounds_and_worst_case():
    red = adversarial_search("imbalance", [ImbalanceSentinel, LeadLagSentinel], budget=3, seed=1,
                             base=ScenarioSpec(name="r", vendor_shares=(0.40, 0.15),
                                               vendor_rhos=(0.90, 0.30), shock_size=0.05, seed=7,
                                               t_steps=400, n_agents=80, shock_time=200))
    assert len(red["trials"]) == 3
    for t in red["trials"]:
        assert t["params"]["evader_cohorts"] in (2, 3, 4, 6, 8)
    if red["worst_case"]:
        assert set(red["worst_case"]["f1_all"]) == {"imbalance", "lead_lag"}


def test_injection_suite_all_contained(run):
    a = run["art"]
    inj = a["redteam"]["injection"]
    assert inj["all_contained"], [c for c in inj["cases"] if not c["contained"]]
    assert inj["n_cases"] >= 11


# ------------------------------------------------------- rules and frontier --

def test_rule_library_halts_on_breaches():
    sp = ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30), shock_size=0.08,
                      seed=0, t_steps=400, n_agents=80, shock_time=200)
    for R in (LULDStyleBand, VenueVolatilityHalt):
        treated = simulate(sp, intervention=R().make(sp.n_agents))
        assert treated.halted.any(), R.name
    mw = MarketWideBreaker(levels=(0.02, 0.05, 0.08)).make(sp.n_agents)
    treated = simulate(sp, intervention=mw)
    assert treated.halted.any()
    assert {R.name for R in ALL_RULES} >= {"luld_style_band", "market_wide_breaker", "venue_volatility_halt"}
    assert all(k in RULE_LIBRARY for k in ("luld_style_band", "kill_switch"))


def test_frontier_endpoints(run):
    s, r = run["art"]["sentinels"], run["art"]["rules"]
    fs, fr = sentinel_frontier(s), rule_frontier(r)
    assert fs["segments"][0]["c_from"] == 0.0 and fs["segments"][-1]["c_to"] == 1.0
    assert fs["best_at_declared"] in s and fr["best_at_declared"] in r
    fa = {n: (v["false_alert_rate"] or 0.0) for n, v in s.items()}
    assert fa[fs["segments"][-1]["tool"]] == min(fa.values())


# ------------------------------------------------------ critic and briefing --

def test_numbers_in_keeps_printed_precision():
    assert numbers_in("gap 0.83 margin 0.9731 97% 2026-09-05 12:00 run 20260905-000000-abcd") == {0.83, 0.9731, 97.0}


def test_v3_artefacts_critic_and_briefing(run):
    a, ex, log = run["art"], run["ex"], run["log"]
    assert a["decision_gap"]["n_tools"] == 8 and len(a["rules"]) == 8
    assert a["attribution"]["n_scenarios"] >= 4 and a["personas"]["momentum_follower"]["table_sha256"]
    bh = battery_hash(run["specs"])
    rep = critic_check(a, rows=ex["rows"], approved_battery_hash=bh, ledger_path=log.path,
                       secret="test-secret")
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    assert rep["n_checks"] >= 18
    text = draft_briefing(a, rep, {"preparer": "D. Godorozha",
                                   "gate1": {"actor": "R. Ahmed", "ts": "2026-09-05T10:00:00+00:00"}},
                          "20260905-100000-ab12")
    rep2 = critic_check(a, rows=ex["rows"], approved_battery_hash=bh, briefing_text=text)
    assert rep2["ok"], [c for c in rep2["checks"] if not c["ok"]]
    for head in ("false alert guarantee", "cost frontier", "Counterfactual attribution",
                 "Truth dependence", "Concentration dose response", "Red team", "LLM personas",
                 "Rule library"):
        assert head in text, head
    assert "—" not in text and "–" not in text
    tampered = json.loads(json.dumps(a))
    tampered["attribution"]["scenarios"][0]["shapley"][tampered["attribution"]["scenarios"][0]["groups"][0]] += 0.01
    assert not critic_check(tampered, rows=ex["rows"], approved_battery_hash=bh)["ok"]


def test_ask_v3_intents(run):
    a = run["art"]
    snap = {"stage": "evaluated", "question": "q", "run_id": "r", "preparer": "p",
            "specs": [s.describe() for s in run["specs"]], "summary": a["sentinels"],
            "holdout": a["sentinels_holdout"], "gap": a["decision_gap"],
            "gap_moments": a["decision_gap_moments"], "gap_bootstrap": a["decision_gap_bootstrap"],
            "gap_bootstrap_moments": a["decision_gap_bootstrap_moments"], "rules": a["rules"],
            "aut": a["autonomy"], "rl": None, "three": a["three_worlds"], "critic": None,
            "ledger": None, "artefacts": a}
    for q, it, needle in [("what is the worst case evasion?", "redteam", "worst case"),
                          ("does the guarantee hold?", "conformal", "guaranteed"),
                          ("which group caused the dislocation?", "attribution", "impact ordering"),
                          ("show the cost frontier", "frontier", "optimal for c"),
                          ("does the ranking survive a change of generator?", "truth", "ranking"),
                          ("how much concentration is too much?", "concentration", "share"),
                          ("which persona is in the battery?", "persona", "table hash")]:
        assert intent_of(q) == it
        r = answer(snap, q)
        assert needle in r["text"] and r["sources"], q
    assert intent_of("which sentinel should the authority certify?") == "certify"
