"""Version 3.2: survival analysis, tail dependence sentinel, expected
shortfall, responsive ladder, voter generator, bandit adversary."""

import numpy as np
import pytest

from hsl.evaluate import expected_shortfall
from hsl.herding import TailDependenceSentinel, HERDING_SENTINELS
from hsl.redteam import adversarial_search, BANDIT_ARMS
from hsl.rules import ResponsiveLadder
from hsl.sentinels import ALL_SENTINELS, NetworkSentinel
from hsl.simulator import ScenarioSpec, simulate
from hsl.survival import kaplan_meier, cox_ph, time_to_dislocation
from hsl.audit import GENERATORS


def test_kaplan_meier_matches_hand_calculation():
    k = kaplan_meier([1, 2, 2, 3, 4], [1, 1, 0, 1, 0])
    # t=1: 4/5; t=2: one event of 4 at risk -> 3/4; t=3: 1 event of 2 -> 1/2
    assert k["times"] == [1.0, 2.0, 3.0]
    assert np.allclose(k["survival"], [0.8, 0.6, 0.3])
    assert k["median"] == 3.0 and k["events"] == 3


def test_cox_recovers_a_protective_treatment():
    rng = np.random.default_rng(0)
    n = 200
    x = rng.integers(0, 2, n).astype(float)
    t = rng.exponential(1.0 / np.exp(-1.0 * x), n)       # hazard ratio 0.37 for x = 1
    c = rng.exponential(3.0, n)
    obs, ev = np.minimum(t, c), (t <= c).astype(int)
    fit = cox_ph(x[:, None], obs, ev)
    assert fit["converged"] and 0.25 < fit["hazard_ratio"][0] < 0.55


def test_time_to_dislocation_and_censoring():
    herd = simulate(ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                                 shock_size=0.05, seed=0))
    quiet = simulate(ScenarioSpec(name="q", vendor_shares=(0.25, 0.15), vendor_rhos=(0.45, 0.25),
                                  shock_time=None, seed=901))
    t, e = time_to_dislocation(herd)
    assert e == 1 and 1 <= t <= 300
    assert time_to_dislocation(quiet) == (None, 0)


def test_expected_shortfall_is_the_worst_quarter_mean():
    x = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    assert expected_shortfall(x, 0.75) == pytest.approx(0.75)
    assert expected_shortfall([], 0.75) is None


def test_tail_dependence_sentinel_detects_and_stays_quiet():
    assert len(ALL_SENTINELS) == 8 and TailDependenceSentinel in HERDING_SENTINELS
    herd = simulate(ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                                 shock_size=0.05, seed=7))
    out = TailDependenceSentinel().run(herd)
    from hsl.evaluate import decision_scores
    assert out["first_alert"] is not None and decision_scores(herd, out)["f1"] > 0.7
    quiet = simulate(ScenarioSpec(name="q", vendor_shares=(0.25, 0.15), vendor_rhos=(0.45, 0.25),
                                  shock_time=None, seed=907))
    assert TailDependenceSentinel().run(quiet)["first_alert"] is None
    fo = out["flags_online"]
    assert not fo[:out["first_alert"]].any() and np.array_equal(fo[-1], out["flags"])


def test_responsive_ladder_escalates_only_under_stress():
    sp = ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30), shock_size=0.08,
                      seed=0, t_steps=400, n_agents=80, shock_time=200)
    res = simulate(sp)
    fo = NetworkSentinel().run(res)["flags_online"]
    treated = simulate(sp, intervention=ResponsiveLadder().make(sp.n_agents, flags_online=fo))
    assert treated.post_shock_drawdown() <= res.post_shock_drawdown() + 1e-9
    assert (treated.throttled < 1).any()
    quiet = ScenarioSpec(name="q", vendor_shares=(0.25, 0.15), vendor_rhos=(0.45, 0.25), shock_time=None,
                         seed=901, t_steps=300, n_agents=80)
    qres = simulate(quiet)
    qfo = NetworkSentinel().run(qres)["flags_online"]
    qt = simulate(quiet, intervention=ResponsiveLadder().make(quiet.n_agents, flags_online=qfo))
    assert not qt.halted.any()


def test_voter_generator_herds_and_is_audited():
    assert "voter" in GENERATORS
    v = simulate(ScenarioSpec(name="v", generator="voter", vendor_shares=(0.40, 0.15),
                              vendor_rhos=(0.90, 0.30), shock_size=0.05, seed=0))
    assert v.post_shock_drawdown() > 0.08


def test_bandit_adversary_pulls_sum_to_budget():
    from hsl.herding import LeadLagSentinel, ImbalanceSentinel
    red = adversarial_search("lead_lag", [LeadLagSentinel, ImbalanceSentinel], budget=len(BANDIT_ARMS) + 2,
                             seed=1, base=ScenarioSpec(name="r", vendor_shares=(0.40, 0.15),
                                                       vendor_rhos=(0.90, 0.30), shock_size=0.05, seed=7,
                                                       t_steps=400, n_agents=80, shock_time=200))
    assert red["method"] == "ucb1" and sum(a["pulls"] for a in red["arms"]) == len(red["trials"])
    assert all(a["pulls"] >= 1 for a in red["arms"])


# ------------------------------------------------ 3.2 additions: risk, games, learned policy, appraisal --

from hsl.risk import value_at_risk, expected_shortfall as es_risk, gpd_tail
from hsl.games import matrix_game, game_from_trials
from hsl.rl_supervisor import (train_and_evaluate, fit_model, value_iteration, log_trajectories,
                               N_STATES, LearnedPolicyRule)
from hsl.appraisal import appraise
from hsl.survival import survival_analysis, logrank_test, weibull_fit
from hsl.evaluate import ALL_RULES


def test_risk_measures_and_gpd_tail():
    x = np.linspace(0.01, 0.30, 40)
    assert es_risk(x, 0.9) >= value_at_risk(x, 0.9)
    g = gpd_tail(x, threshold_q=0.7)
    assert g["n_excess"] >= 5 and g["shape"] is not None and 0 <= g["tail_prob"] <= 1
    assert gpd_tail([0.1, 0.2])["shape"] is None


def test_matrix_game_value_lies_between_maximin_and_minimax():
    A = [[0.9, 0.1], [0.2, 0.8]]
    g = matrix_game(A, ["a", "b"], ["c1", "c2"])
    assert g["maximin_value"] == pytest.approx(0.2) and g["minimax_value"] == pytest.approx(0.8)
    assert g["maximin_value"] - 1e-9 <= g["mixed_value"] <= g["minimax_value"] + 1e-9
    assert abs(sum(g["mixture"].values()) - 1) < 1e-6 and g["value_of_mixing"] > 0
    red = {"certified": "a", "trials": [{"k": 0, "dislocates": True, "f1_all": {"a": 0.9, "b": 0.2},
                                          "params": {"evader_cohorts": 2, "evader_period": 5, "rho": 0.9, "share": 0.4}},
                                         {"k": 1, "dislocates": True, "f1_all": {"a": 0.1, "b": 0.8},
                                          "params": {"evader_cohorts": 6, "evader_period": 5, "rho": 0.9, "share": 0.4}},
                                         {"k": 2, "dislocates": False, "f1_all": {"a": 0.0, "b": 0.0},
                                          "params": {"evader_cohorts": 3, "evader_period": 2, "rho": 0.9, "share": 0.4}}]}
    gg = game_from_trials(red, ["a", "b"])
    assert gg["n_trials"] == 2 and gg["certified_worst"] == pytest.approx(0.1)


def test_learned_policy_trains_and_ope_tracks_simulation():
    specs = [ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30), shock_size=0.05,
                          seed=0, t_steps=300, n_agents=60, shock_time=150),
             ScenarioSpec(name="m", vendor_shares=(0.30, 0.15), vendor_rhos=(0.75, 0.30), shock_size=0.05,
                          seed=1, t_steps=300, n_agents=60, shock_time=150),
             ScenarioSpec(name="q", vendor_shares=(0.25, 0.15), vendor_rhos=(0.45, 0.25), shock_time=None,
                          seed=901, t_steps=300, n_agents=60)]
    traj = log_trajectories(specs, seed=0)
    assert len(traj) == 3 and all(len(t["steps"]) == 299 for t in traj)
    model = fit_model(traj)
    assert np.allclose(model["P"].sum(axis=2), 1.0)
    policy, V, Q = value_iteration(model)
    assert policy.shape == (N_STATES,) and policy.min() >= 0 and policy.max() <= 2
    lp = train_and_evaluate(specs, [R for R in ALL_RULES if R.name not in ("learned_policy",)][:3], seed=0)
    assert set(lp["ope"]) >= {"learned_policy", "do_nothing"}
    for v in lp["ope"].values():
        assert v["dr"] is not None and np.isfinite(v["dr"]) and np.isfinite(v["on_policy"])
    assert lp["mean_abs_error"]["dr"] <= lp["mean_abs_error"]["pdis"] + 0.05
    assert LearnedPolicyRule.policy.shape == (N_STATES,)
    treated = simulate(specs[0], intervention=LearnedPolicyRule().make(specs[0].n_agents))
    assert treated.prices.shape == (300,)


def test_appraisal_recommends_lowest_eligible_tier():
    rules = {"static_circuit_breaker": {"label": "Market wide circuit breaker", "containment": 0.4,
                                        "false_halt_rate": 0.0, "targeted": False,
                                        "burden_by_class": {"destabilising": 0.3, "non_destabilising": 0.3}},
             "dynamic_throttle": {"label": "Sentinel informed dynamic throttle", "containment": 0.35,
                                  "false_halt_rate": 0.0, "targeted": True,
                                  "burden_by_class": {"destabilising": 0.4, "non_destabilising": 0.1}},
             "kill_switch": {"label": "Sentinel informed kill switch", "containment": 0.1,
                             "false_halt_rate": 0.0, "targeted": True,
                             "burden_by_class": {"destabilising": 0.4, "non_destabilising": 0.4}}}
    ap = appraise(rules, containment_target=0.3)
    assert ap["recommended"]["rule"] == "dynamic_throttle" and ap["recommended"]["tier"] == 1
    assert ap["n_eligible"] == 2
    kill = next(o for o in ap["options"] if o["rule"] == "kill_switch")
    assert not kill["passes"]["containment"] and not kill["passes"]["proportionality"]


def test_logrank_and_weibull_sanity():
    rng = np.random.default_rng(1)
    a = rng.exponential(1.0, 80); b = rng.exponential(3.0, 80)
    lr = logrank_test(a, np.ones(80), b, np.ones(80))
    assert lr["p_value"] < 0.01
    wf = weibull_fit(b, np.ones(80))
    assert 2.0 < wf["scale"] < 4.5 and 0.6 < wf["shape"] < 1.5


def test_survival_analysis_contract():
    specs = [ScenarioSpec(name=f"h{s}", family="herd_high", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                          shock_size=0.05, seed=s, t_steps=300, n_agents=60, shock_time=150) for s in range(3)]
    cache = {sp.name: {"res": simulate(sp), "outs": {"naive_threshold": NetworkSentinel().run(simulate(sp))}}
             for sp in specs}
    from hsl.survival import time_to_dislocation
    ev = {"static_circuit_breaker": {sp.name: time_to_dislocation(cache[sp.name]["res"]) for sp in specs}}
    sv = survival_analysis(specs, cache, ev, ["naive_threshold"])
    assert sv["arms"] == ["untreated", "static_circuit_breaker"]
    for k in sv["kaplan_meier"].values():
        assert 0 <= k["survival_at_20"] <= 1 and k["n"] == 3
    assert "naive_threshold" in sv["sentinel_alerts"]


def test_reports_coverage_indicators_and_families():
    import json
    from hsl.reports import coverage, indicators, exchange_record, NEEDS, RULE_OVERSIGHT
    from hsl.simulator import scenario_battery, ScenarioSpec, simulate
    a = json.load(open("sample_outputs/artefacts.json"))
    cov = coverage(a)
    assert len(cov["needs"]) == len(NEEDS) == 15
    assert cov["n_answered"] + cov["n_partial"] + cov["n_open"] == 15
    ind = indicators(a)
    tc = ind["third_party_concentration"]
    assert 0 <= tc["vendor_hhi_max"] <= 1 and 0 <= tc["top_vendor_share_max"] <= 1
    assert len(ind["data_gaps"]) == 5
    x = exchange_record(a, "20260905-000000-abcd", "test authority")
    assert x["schema"] == "hsl.exchange/1" and set(x["needs_coverage"]) == {n["id"] for n in NEEDS}
    assert all(k in RULE_OVERSIGHT for k in ("kill_switch", "learned_policy"))
    fams = {s.family for s in scenario_battery(include_rl=False)}
    assert {"vendor_fault", "liquidity_withdrawal", "misinformation"} <= fams
    vf = next(s for s in scenario_battery(include_rl=False) if s.family == "vendor_fault")
    r = simulate(vf)
    assert r.destabilising[r.agent_cluster == 0].all()
    lw = simulate(ScenarioSpec(name="lw", vendor_shares=(0.35, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                               liquidity_withdrawal_time=312, seed=760))
    base = simulate(ScenarioSpec(name="b", vendor_shares=(0.35, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                                 seed=760))
    assert lw.post_shock_drawdown() > base.post_shock_drawdown() + 0.1
    mi = simulate(ScenarioSpec(name="mi", vendor_shares=(0.35, 0.15), vendor_rhos=(0.85, 0.30), shock_size=0.05,
                               false_shock_len=20, seed=770))
    assert mi.post_shock_drawdown() > 0.03
