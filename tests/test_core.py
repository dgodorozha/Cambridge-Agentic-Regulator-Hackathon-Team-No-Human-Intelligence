"""Core tests. Run:  python -m pytest -q tests

These use a small battery (80 agents, 400 steps) so the whole file runs in
well under a minute. The full battery is exercised by test_terminal.py.
"""

import json
import os
import threading

import numpy as np
import pytest

from hsl import provenance
from hsl.ask import answer, intent_of
from hsl.autonomy import autonomy_gates, autonomy_public
from hsl.briefing import draft_briefing, to_html
from hsl.critic import critic_check, numbers_in
from hsl.evaluate import (DynamicThrottle, KillSwitch, StaticCircuitBreaker, bootstrap_ci,
                          evidence_grade, best_certifiable)
from hsl.evidence import build_pack
from hsl.ledger import Ledger, verify, read, canonical
from hsl.pipeline import run_battery
from hsl.sentinels import ALL_SENTINELS, NetworkSentinel, AbsorptionRatio
from hsl.simulator import (ScenarioSpec, SimulationStopped, battery_hash, simulate,
                           scenario_battery)


def small_specs():
    return [
        ScenarioSpec(name="herd_high_0", family="herd_high", vendor_shares=(0.40, 0.15),
                     vendor_rhos=(0.90, 0.30), shock_size=0.05, seed=0, t_steps=400,
                     n_agents=80, shock_time=200),
        ScenarioSpec(name="herd_mid_0", family="herd_mid", vendor_shares=(0.30, 0.15),
                     vendor_rhos=(0.75, 0.30), shock_size=0.05, seed=1, t_steps=400,
                     n_agents=80, shock_time=200),
        ScenarioSpec(name="evader_0", family="evader", vendor_shares=(0.40, 0.15),
                     vendor_rhos=(0.90, 0.30), shock_size=0.05, evader_cohorts=3, seed=2,
                     t_steps=400, n_agents=80, shock_time=200),
        ScenarioSpec(name="quiet_0", family="quiet", vendor_shares=(0.25, 0.15),
                     vendor_rhos=(0.45, 0.25), shock_time=None, seed=3, t_steps=400, n_agents=80),
        ScenarioSpec(name="quiet_1", family="quiet", vendor_shares=(0.25, 0.15),
                     vendor_rhos=(0.45, 0.25), shock_time=None, seed=4, t_steps=400, n_agents=80),
        ScenarioSpec(name="holdout_herd_0", family="holdout_herd", holdout=True, n_agents=90,
                     vendor_shares=(0.25, 0.20, 0.15), vendor_rhos=(0.85, 0.70, 0.30),
                     shock_time=250, kappa=0.018, seed=5, t_steps=400),
        ScenarioSpec(name="holdout_quiet_0", family="holdout_quiet", holdout=True, n_agents=90,
                     vendor_shares=(0.25, 0.20, 0.15), vendor_rhos=(0.45, 0.35, 0.25),
                     shock_time=None, kappa=0.018, seed=6, t_steps=400),
    ]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("run")
    specs = small_specs()
    log = Ledger(str(d / "ledger.jsonl"), "20260901-000000-abcd", secret="test-secret",
                 actor="orchestrator")
    art, ex = run_battery(specs, log, question="test question?", bootstrap_B=60)
    return {"dir": d, "specs": specs, "log": log, "art": art, "ex": ex}


# ---------------------------------------------------------------- ledger --

def test_ledger_chain_verifies_and_signatures(tmp_path):
    p = tmp_path / "l.jsonl"
    log = Ledger(str(p), "run-1", secret="k", actor="a")
    log("one", x=1, arr=np.array([1, 2]), flag=np.bool_(True), f=np.float64(0.5))
    log("two", actor="human", y="z")
    rep = verify(str(p), "k")
    assert rep["ok"] and rep["entries"] == 2 and rep["signed"] == 2
    recs = read(str(p))
    assert recs[0]["payload"]["arr"] == [1, 2] and recs[0]["payload"]["flag"] is True
    assert recs[1]["actor"] == "human" and recs[1]["prev_hash"] == recs[0]["hash"]
    # wrong key fails; no key verifies chain only
    assert not verify(str(p), "wrong")["ok"]
    assert verify(str(p), None)["ok"]


def test_ledger_tamper_detected(tmp_path):
    p = tmp_path / "l.jsonl"
    log = Ledger(str(p), "run-1", secret="k")
    for i in range(5):
        log("step", i=i, value=0.1 * i)
    lines = p.read_text().splitlines()
    rec = json.loads(lines[2])
    rec["payload"]["value"] = 9.9
    lines[2] = json.dumps(rec)
    p.write_text("\n".join(lines) + "\n")
    rep = verify(str(p), "k")
    assert not rep["ok"] and any("hash mismatch" in e for e in rep["errors"])
    # deletion breaks the chain
    lines2 = p.read_text().splitlines()
    del lines2[1]
    p.write_text("\n".join(lines2) + "\n")
    rep = verify(str(p), "k")
    assert not rep["ok"] and any("chain broken" in e or "seq" in e for e in rep["errors"])


def test_ledger_reopen_continues_chain(tmp_path):
    p = tmp_path / "l.jsonl"
    Ledger(str(p), "run-1", secret="k")("a")
    log2 = Ledger(str(p), "run-1", secret="k")
    assert log2.seq == 1
    log2("b")
    rep = verify(str(p), "k")
    assert rep["ok"] and rep["entries"] == 2


def test_canonical_is_deterministic():
    a = canonical({"b": 1, "a": [1.5, np.float32(2)]})
    b = canonical({"a": [1.5, 2.0], "b": 1})
    assert a == b


# ------------------------------------------------------------- simulator --

def test_v1_dynamics_preserved():
    q = simulate(ScenarioSpec(name="tw_quiet", vendor_rhos=(0.45, 0.25), shock_time=None, seed=7))
    h = simulate(ScenarioSpec(name="tw_herd", vendor_shares=(0.40, 0.15),
                              vendor_rhos=(0.90, 0.30), seed=7))
    assert abs(q.max_drawdown() - 0.06708) < 1e-4
    assert abs(h.max_drawdown() - 0.26779) < 1e-4
    assert h.post_shock_drawdown() <= h.max_drawdown() + 1e-12
    assert h.pre_shock_vol() > q.pre_shock_vol()


def test_determinism_and_battery_hash():
    s = small_specs()[0]
    a, b = simulate(s), simulate(s)
    assert np.array_equal(a.prices, b.prices)
    h1 = battery_hash(small_specs())
    s2 = small_specs()
    s2[0].seed = 99
    assert h1 == battery_hash(small_specs()) and h1 != battery_hash(s2)


def test_evader_keeps_aggregate_impact_but_lowers_pairwise_correlation():
    base = simulate(ScenarioSpec(name="h", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                                 seed=1, t_steps=400, n_agents=80, shock_time=200))
    ev = simulate(ScenarioSpec(name="e", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                               seed=1, t_steps=400, n_agents=80, shock_time=200, evader_cohorts=3))
    m = base.agent_cluster == 0
    C_b = np.corrcoef(base.flows[100:, m].T)
    C_e = np.corrcoef(ev.flows[100:, m].T)
    iu = np.triu_indices(m.sum(), 1)
    assert np.nanmean(C_e[iu]) < 0.6 * np.nanmean(C_b[iu])
    assert ev.destabilising[m].all()
    assert ev.post_shock_drawdown() > 0.5 * base.post_shock_drawdown()


def test_emergency_stop_raises():
    ev = threading.Event()
    ev.set()
    with pytest.raises(SimulationStopped):
        simulate(small_specs()[0], stop=ev)


def test_full_battery_shape():
    specs = scenario_battery(include_rl=False)
    fams = {s.family for s in specs}
    assert {"herd_high", "evader", "quiet", "holdout_herd", "holdout_quiet"} <= fams
    assert sum(s.holdout for s in specs) == 5


# ------------------------------------------------------------- sentinels --

def test_online_flags_never_precede_first_alert_and_match_final():
    res = simulate(small_specs()[0])
    for S in ALL_SENTINELS:
        out = S().run(res)
        fo = out["flags_online"]
        assert fo.shape == res.flows.shape
        if out["first_alert"] is None:
            assert not fo.any()
        else:
            assert not fo[:out["first_alert"]].any()
            assert np.array_equal(fo[-1], out["flags"])


def test_absorption_ratio_localises_dominant_cluster():
    res = simulate(small_specs()[0])
    out = AbsorptionRatio().run(res)
    assert out["first_alert"] is not None
    truth = res.destabilising
    flagged = out["flags"]
    assert (flagged & truth).sum() / truth.sum() > 0.8


# ------------------------------------------------------------ evaluation --

def test_rules_no_lookahead_and_kill_switch_disconnects():
    spec = small_specs()[0]
    res = simulate(spec)
    fo = NetworkSentinel().run(res)["flags_online"]
    for R in (DynamicThrottle, KillSwitch):
        r = R()
        rule = r.make(spec.n_agents, flags_online=fo)
        treated = simulate(spec, intervention=rule)
        assert r.lookahead is False
        assert treated.throttled.min() >= 0.0
        if R is KillSwitch and (treated.throttled < 1).any():
            assert (treated.throttled[treated.throttled < 1] == 0).all()
    cb = StaticCircuitBreaker().make(spec.n_agents)
    t2 = simulate(spec, intervention=cb)
    assert t2.halted.any()


def test_artefacts_contents(run):
    a = run["art"]
    assert set(a["sentinels"]) == {S.name for S in ALL_SENTINELS}
    for v in a["sentinels"].values():
        lo, hi = v["ci"]["decision_f1"]
        assert lo - 1e-9 <= v["decision_f1"] <= hi + 1e-9
        assert v["grade"]["decision_f1"] in "ABC"
        assert "within_budget" in v
    assert a["sentinels_holdout"], "held out families must be scored separately"
    assert 0 <= a["decision_gap"]["decision_gap"] <= 1
    assert 0 <= a["decision_gap_bootstrap"]["p_inversion"] <= 1
    for v in a["rules"].values():
        assert v["lookahead"] is False
        assert v["false_halt_rate"] is not None
        assert "fundamentalist" in v["burden_by_class"]
        assert abs((1 - v["mean_post_shock_dd_treated"] / v["mean_post_shock_dd_untreated"])
                   - v["containment"]) < 1e-9
    assert a["provenance"]["battery_hash"] == battery_hash(run["specs"])
    assert a["provenance"]["code_fingerprint"] == provenance()["code_fingerprint"]


def test_bootstrap_and_grades():
    assert bootstrap_ci([]) == [None, None]
    assert bootstrap_ci([0.3]) == [0.3, 0.3]
    lo, hi = bootstrap_ci([0.1, 0.2, 0.3, 0.4] * 4)
    assert lo <= 0.25 <= hi
    assert evidence_grade(20, [0.4, 0.5]) == "A"
    assert evidence_grade(8, [0.3, 0.6]) == "B"
    assert evidence_grade(2, [0.0, 1.0]) == "C"


# ------------------------------------------------------------- autonomy --

def test_autonomy_loo(run):
    aut = autonomy_gates(run["ex"]["rows"], [S.name for S in ALL_SENTINELS])
    for v in aut.values():
        assert abs(v["breadth"] - (v["clear"] + v["throttle"])) < 1e-9
        assert v["throttle_ok"] == (v["lift"] >= v["lift_bar"])
        loo = v["loo"]
        assert 0 <= loo["claim_rate"] <= 1 and len(loo["decisions"]) == len(v["scores"])
        assert {d["decision"] for d in loo["decisions"]} <= {"auto_clear", "auto_throttle", "escalate"}
    pub = autonomy_public(aut)
    assert "scores" not in next(iter(pub.values()))


# --------------------------------------------------------------- critic --

def test_critic_passes_and_catches_tampering(run):
    a, ex, log = run["art"], run["ex"], run["log"]
    bh = battery_hash(run["specs"])
    rep = critic_check(a, rows=ex["rows"], approved_battery_hash=bh, ledger_path=log.path,
                       secret="test-secret")
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    tampered = json.loads(json.dumps(a))
    name = next(iter(tampered["sentinels"]))
    tampered["sentinels"][name]["decision_f1"] += 0.05
    rep2 = critic_check(tampered, rows=ex["rows"], approved_battery_hash=bh)
    assert not rep2["ok"]
    rep3 = critic_check(a, rows=ex["rows"], approved_battery_hash="0" * 64)
    assert any(c["name"].startswith("battery hash") and not c["ok"] for c in rep3["checks"])


def test_numbers_in_ignores_identifiers():
    n = numbers_in("run 20260901-221144-91fa hash f36ae6b1e839ea5f numpy 2.4.4 at 21:44:01 gap 0.83")
    assert n == {0.83}


# ------------------------------------------------------------- briefing --

def test_briefing_numbers_vetted_and_html(run):
    a, ex, log = run["art"], run["ex"], run["log"]
    crit = critic_check(a, rows=ex["rows"], approved_battery_hash=battery_hash(run["specs"]))
    text = draft_briefing(a, crit, {"preparer": "D. Godorozha",
                                    "gate1": {"actor": "R. Ahmed", "ts": "2026-09-01T21:00:00+00:00"}},
                          "20260901-210000-ab12")
    rep = critic_check(a, rows=ex["rows"], approved_battery_hash=battery_hash(run["specs"]),
                       briefing_text=text)
    bad = [c for c in rep["checks"] if not c["ok"]]
    assert not bad, bad
    assert "Held out" in text or "held out" in text
    assert "—" not in text and "–" not in text, "no dashes in the briefing"
    html = to_html(text)
    assert "<table>" in html and "<h1>" in html
    cert = best_certifiable(a["sentinels"])
    assert cert is None or a["sentinels"][cert]["within_budget"]


# ------------------------------------------------------------- evidence --

def test_evidence_pack(run):
    d = run["dir"]
    (d / "artefacts.json").write_text(json.dumps(run["art"], default=str))
    (d / "rows.json").write_text(json.dumps(run["ex"]["rows"], default=str))
    (d / "meta.json").write_text(json.dumps({"run_id": "x"}))
    path, manifest = build_pack(str(d))
    assert os.path.exists(path)
    assert set(manifest["files"]) >= {"artefacts.json", "rows.json", "ledger.jsonl", "meta.json"}
    import zipfile
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert "manifest.json" in names and "VERIFY.md" in names


# ------------------------------------------------------------------ ask --

def test_ask_answers_supervisory_questions(run):
    a = run["art"]
    snap = {"stage": "evaluated", "question": "q", "run_id": "r", "preparer": "p",
            "specs": [s.describe() for s in run["specs"]], "summary": a["sentinels"],
            "holdout": a["sentinels_holdout"], "gap": a["decision_gap"],
            "gap_moments": a["decision_gap_moments"], "gap_bootstrap": a["decision_gap_bootstrap"],
            "gap_bootstrap_moments": a["decision_gap_bootstrap_moments"], "rules": a["rules"],
            "aut": a["autonomy"], "rl": None, "three": a["three_worlds"], "critic": None,
            "ledger": verify(run["log"].path, "test-secret")}
    for q, it in [("which sentinel should the authority certify?", "certify"),
                  ("how big is the decision gap?", "gap"),
                  ("does the throttle hurt fundamentalists?", "rules"),
                  ("how much execution can be backed?", "autonomy"),
                  ("is the ledger intact?", "ledger"),
                  ("tell me about herd_mid_0", "retrieval")]:
        assert intent_of(q) == it
        r = answer(snap, q)
        assert r["text"] and r["sources"]
        assert "n/a" not in r["text"][:80]
    r = answer(snap, "which sentinel should the authority certify?")
    assert "decision F1" in r["text"] and "supervisor" in r["text"]
    empty = answer({"stage": "idle", "summary": None}, "certify?")
    assert "No battery" in empty["text"]
