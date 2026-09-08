"""Version 3.3: quarantine, connectors behind the allowlist, security posture,
asset manifest, roles, anchoring, empirical family and observed window."""

import os

import numpy as np
import pytest

from hsl.connectors import fetch_dataset, ConnectorError, _https_get
from hsl.ingest import (quarantine, anchoring, empirical_family, observed_window, stats, export_csv,
                        dataset_summary, K_ANON)
from hsl.security import (pii_scan, sanitize_cell, classify, authorize, egress_allowed, build_manifest,
                          verify_manifest, posture)
from hsl.sentinels import ALL_SENTINELS

FIX = os.path.join(os.path.dirname(__file__), "..", "sample_data")


class _Cfg:
    ephemeral_secret = False; auth_mode = "open"; four_eyes = True; host = "127.0.0.1"; debug = False
    connectors = False; egress_allowlist = []; upload_max_mb = 25; ask_rate = 20


def _read(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()


def test_quarantine_accepts_the_fixture_and_records_provenance():
    ds = quarantine("synthetic_index.csv", _read("synthetic_index.csv"), uploader="D. G", classification="public")
    assert ds["ok"] and ds["n_rows"] == 400 and len(ds["sha256"]) == 64
    assert ds["schema"]["time"] == "timestamp" and ds["schema"]["price"] == "price"
    assert dataset_summary(ds)["packable"] is True and "rows" not in dataset_summary(ds)


def test_quarantine_refuses_pii_formulas_binary_size_and_confidential():
    assert not quarantine("a.csv", b"timestamp,price,contact\n1,100,someone@example.com\n")["ok"]
    assert "formula" in quarantine("a.csv", b"timestamp,price\n1,=SUM(A1)\n")["reason"]
    assert "binary" in quarantine("a.csv", b"\x00\x01\x02")["reason"]
    assert "MB" in quarantine("a.csv", b"x" * 100, max_bytes=50)["reason"]
    assert "refused" in quarantine("a.csv", _read("synthetic_index.csv"), classification="confidential")["reason"]
    assert "CSV or JSON" in quarantine("a.xlsx", b"abc")["reason"]
    assert "schema" in quarantine("a.csv", b"foo,bar\n1,2\n")["reason"]


def test_pii_scan_and_formula_sanitiser():
    hits = pii_scan("call 07123 456789 or write to a.b@c.org, card 4111 1111 1111 1111")
    assert hits.get("email") == 1 and hits.get("card") == 1 and hits.get("uk_phone") == 1
    assert not pii_scan("prices 100.5 and 101.2 over 2026")
    assert sanitize_cell("=1+1") == "'=1+1" and sanitize_cell("100") == "100" and sanitize_cell("-0.5") == "-0.5"
    csv_text = export_csv([{"a": "@cmd", "b": 1}], ["a", "b"])
    assert "'@cmd" in csv_text


def test_classification_and_roles():
    assert classify("public")["allowed"] and classify("licensed")["packable"] is False
    assert not classify("personal")["allowed"] and not classify("nonsense")["allowed"]
    assert authorize("approver", "gate") and not authorize("preparer", "gate")
    assert authorize("preparer", "upload") and not authorize("viewer", "plan")
    assert authorize("admin", "posture")


def test_egress_policy_and_connector_gate():
    assert egress_allowed("api.stlouisfed.org", ["api.stlouisfed.org"]) and not egress_allowed("evil.example", ["x.y"])
    with pytest.raises(ConnectorError):
        _https_get("http://api.stlouisfed.org/x", ["api.stlouisfed.org"])      # https only
    with pytest.raises(ConnectorError):
        _https_get("https://not-allowed.example/x", ["api.stlouisfed.org"])
    cfg = _Cfg()
    with pytest.raises(ConnectorError):
        fetch_dataset("fred", "DGS10", "2025-01-01", "2025-12-31", cfg)         # connectors off
    with pytest.raises(ConnectorError):
        fetch_dataset("nowhere", "x", "2025-01-01", "2025-12-31", cfg)
    ds, rec = fetch_dataset("replay", "synthetic_index", "2025-01-01", "2026-12-31", cfg)
    assert ds["ok"] and ds["source"] == "replay" and rec["sha256"] == ds["sha256"]
    assert "HSL_KEY" not in str(rec)


def test_manifest_detects_tampering(tmp_path):
    root = tmp_path
    (root / "assets" / "vendor").mkdir(parents=True)
    (root / "assets" / "vendor" / "lib.js").write_text("alert(1)")
    (root / "assets" / "hsl.css").write_text("body{}")
    n = build_manifest(str(root))
    assert len(n) == 2 and verify_manifest(str(root))[0]
    (root / "assets" / "vendor" / "lib.js").write_text("alert(2)")
    ok, det = verify_manifest(str(root))
    assert not ok and det["mismatched"] == ["assets/vendor/lib.js"]


def test_posture_fails_on_confidential_data_and_debug(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "hsl.css").write_text("body{}")
    build_manifest(str(tmp_path))
    p = posture(_Cfg(), root=str(tmp_path))
    assert p["status"] in ("pass", "warn") and p["n_fail"] == 0
    bad = posture(_Cfg(), root=str(tmp_path), datasets=[{"name": "x", "classification": "confidential"}])
    assert bad["n_fail"] >= 1
    cfg = _Cfg(); cfg.debug = True; cfg.connectors = True
    assert posture(cfg, root=str(tmp_path))["n_fail"] >= 2
    assert all(i["sev3"] for i in p["items"])


def test_anchoring_empirical_family_and_observed_window():
    ds = quarantine("synthetic_index.csv", _read("synthetic_index.csv"))
    st = stats(np.array([100 * np.exp(0.01 * np.sin(i / 5)) for i in range(200)]))
    assert st and st["n"] == 199
    an = anchoring(ds, {"vol": 0.01, "kurtosis": 3.0, "abs_autocorr_1": 0.1, "max_drawdown": 0.08})
    assert an["ok"] and set(an["ratios"]) == {"vol", "kurtosis", "abs_autocorr_1", "max_drawdown"}
    fam = empirical_family(ds, n=2)
    assert len(fam) == 2 and all(s.holdout and s.family == "empirical" for s in fam)
    assert 0.01 <= fam[0].shock_size <= 0.10
    flows = quarantine("synthetic_flows.csv", _read("synthetic_flows.csv"))
    assert flows["ok"] and flows["schema"]["participant"] == "participant"
    ow = observed_window(flows, ALL_SENTINELS[:3])
    assert ow["ok"] and ow["n_participants"] == 12 and ow["k_anon"] == K_ANON
    for v in ow["sentinels"].values():
        assert "id" not in v and (v["n_flagged"] == 0 or isinstance(v["n_flagged"], str) or v["n_flagged"] >= K_ANON)
    small = dict(flows, rows=[r for r in flows["rows"] if r["participant"] in ("P00", "P01", "P02")])
    assert not observed_window(small, ALL_SENTINELS[:1])["ok"]


def test_replay_connector_refuses_paths_and_finds_fixtures():
    from hsl.connectors import ReplayConnector, ConnectorError
    import pytest as _pt
    c = ReplayConnector()
    for bad in ("../etc/passwd", "/etc/passwd", "sample_data/synthetic_index.csv", "a\\b"):
        with _pt.raises(ConnectorError):
            c.fetch(bad, None, None, [])
    assert c.fetch("synthetic_index", None, None, []).startswith(b"timestamp")
    with _pt.raises(ConnectorError):
        c.fetch("missing_fixture", None, None, [])


def test_persisted_datasets_and_pack_respect_classification(tmp_path):
    from hsl.ingest import persist_datasets, keep_recent, MAX_DATASETS
    from hsl.evidence import build_pack
    import zipfile
    csv_bytes = open(os.path.join(FIX, "synthetic_index.csv"), "rb").read()
    pub = quarantine("synthetic_index.csv", csv_bytes, uploader="p", classification="public")
    lic = quarantine("vendor_feed.csv", csv_bytes, uploader="p", classification="licensed")
    assert pub["ok"] and lic["ok"] and pub["packable"] and not lic["packable"]
    idx = persist_datasets([pub, lic], str(tmp_path))
    assert len(idx) == 2 and all(os.path.isfile(tmp_path / "data" / e["file"]) for e in idx)
    (tmp_path / "artefacts.json").write_text("{}")
    pack, manifest = build_pack(str(tmp_path))
    names = zipfile.ZipFile(pack).namelist()
    assert "data/index.json" in names
    assert any(n.startswith("data/") and "synthetic_index" in n for n in names)
    assert not any("vendor_feed" in n for n in names), names
    assert len(keep_recent([pub] * (MAX_DATASETS + 5))) == MAX_DATASETS


def test_survival_logrank_per_arm():
    from hsl.survival import survival_analysis
    from hsl.sentinels import NetworkSentinel
    from hsl.simulator import ScenarioSpec, simulate
    specs = [ScenarioSpec(name=f"h{s}", family="herd_high", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                          shock_size=0.05, seed=s, t_steps=300, n_agents=60, shock_time=150) for s in range(4)]
    cache = {}
    for sp in specs:
        r = simulate(sp)
        cache[sp.name] = {"res": r, "outs": {"naive_threshold": NetworkSentinel().run(r)}}
    ev = {"static_circuit_breaker": {sp.name: (None, 0) for sp in specs}}
    sv = survival_analysis(specs, cache, ev, ["naive_threshold"])
    lr = sv["kaplan_meier"]["static_circuit_breaker"]["logrank_vs_untreated"]
    assert lr is not None and 0 <= lr["p_value"] <= 1


def test_calibration_families_and_hybrid_generator():
    from hsl.calibrate import calibrate, calibrated_family, hybrid_family, calibration_shift, observed_returns
    from hsl.simulator import simulate, ScenarioSpec
    import pytest
    from hsl.sentinels import CORE_SENTINELS
    from hsl.evaluate import score_row
    ds = quarantine("synthetic_index.csv", open(os.path.join(FIX, "synthetic_index.csv"), "rb").read(),
                    uploader="p", classification="public")
    cal = calibrate(ds)
    assert cal and 0.002 <= cal["params"]["sigma"] <= 0.03 and 0.01 <= cal["params"]["shock_size"] <= 0.10
    assert cal["params"]["momentum_window"] in (5, 10, 20, 40) and len(cal["params_sha256"]) == 64
    fams = calibrated_family(ds, cal)
    assert len(fams) == 2 and fams[0].family.startswith("calibrated_") and not fams[0].holdout
    r = simulate(fams[0])
    assert r.prices.shape == (600,)
    hy = hybrid_family(ds, cal)
    assert len(hy) == 2 and hy[0].generator == "hybrid" and hy[0].t_steps <= 600
    assert len(observed_returns(hy[0].hybrid_sha)) == hy[0].t_steps
    rh = simulate(hy[0])
    assert rh.prices.shape == (hy[0].t_steps,) and rh.post_shock_drawdown() >= 0
    # with participant flows the vendor split and impact are estimated
    dsf = quarantine("synthetic_flows.csv", open(os.path.join(FIX, "synthetic_flows.csv"), "rb").read(),
                     uploader="p", classification="synthetic")
    calf = calibrate(dsf)
    assert calf["diagnostics"]["n_participants"] == 12 and calf["diagnostics"]["impact_r2"] is not None
    rows = []
    for sp in fams + [ScenarioSpec(name="h", family="herd_high", vendor_shares=(0.40, 0.15), vendor_rhos=(0.90, 0.30),
                                   shock_size=0.05, seed=0)]:
        res = simulate(sp)
        for S in CORE_SENTINELS[:2]:
            rows.append(score_row(sp, res, S.name, S().run(res)))
    cs = calibration_shift(rows, [S.name for S in CORE_SENTINELS[:2]], [fams[0].family])
    assert cs and set(cs["ranking_calibrated"]) == {"naive_threshold", "corr_clustering"}
    with pytest.raises(KeyError):
        observed_returns("0" * 64)


def test_backtest_suite_episodes_sentinels_rules_and_walk_forward():
    import json
    from hsl.backtest import find_episodes, backtest_sentinels, backtest_rules, walk_forward, participant_labels
    from hsl.calibrate import calibrate
    from hsl.sentinels import ALL_SENTINELS
    from hsl.evaluate import ALL_RULES
    ds = quarantine("labelled_flows.csv", open(os.path.join(FIX, "labelled_flows.csv"), "rb").read(),
                    uploader="p", classification="synthetic")
    assert ds["ok"] and ds["schema"]["event"] == "event" and ds["schema"]["label"] == "label"
    labels = participant_labels(ds)
    assert sum(labels.values()) == 4
    eps = find_episodes(ds)
    assert len(eps) == 1 and eps[0]["source"] == "event column" and 140 <= eps[0]["event_step"] < 220
    bs = backtest_sentinels(ds, eps, ALL_SENTINELS)
    assert bs["has_flows"] and bs["labelled_positives"] == 4
    nt = bs["sentinels"]["naive_threshold"]
    assert nt["detection_rate"] in (0.0, 1.0) and nt["quiet_alerts_per_100_steps"] >= 0
    for v in bs["sentinels"].values():
        if v.get("mean_recall_on_labelled") is not None:
            assert 0 <= v["mean_recall_on_labelled"] <= 1
    cal = calibrate(ds)
    br = backtest_rules(ds, cal, eps, ALL_RULES[:2])
    assert br and set(br["rules"]) == {"static_circuit_breaker", "dynamic_throttle"}
    # price only tape: only the return based sentinels run
    dsp = quarantine("synthetic_index.csv", open(os.path.join(FIX, "synthetic_index.csv"), "rb").read(),
                     uploader="p", classification="public")
    eps2 = find_episodes(dsp)
    assert eps2 and all(e["source"].startswith("drawdown") for e in eps2)
    bs2 = backtest_sentinels(dsp, eps2, ALL_SENTINELS)
    assert not bs2["has_flows"] and bs2["sentinels"]["corr_clustering"].get("skipped")
    rows = json.load(open("sample_outputs/rows.json"))
    wf = walk_forward(rows, [S.name for S in ALL_SENTINELS])
    assert wf and 0 <= wf["mean_regret"] <= 1 and 0 <= wf["p_still_best"] <= 1
    for f in wf["folds"]:
        assert abs(f["regret"] - (f["f1_best_test"] - f["f1_certified_test"])) < 1e-9


def test_vendor_column_gives_an_observed_split():
    from hsl.ingest import participant_vendors
    from hsl.calibrate import calibrate
    ds = quarantine("labelled_flows.csv", open(os.path.join(FIX, "labelled_flows.csv"), "rb").read(),
                    uploader="p", classification="synthetic")
    assert ds["schema"]["vendor"] == "vendor" and len(participant_vendors(ds)) == 9
    cal = calibrate(ds)
    assert cal["diagnostics"]["vendor_split_source"] == "observed from the vendor column"
    obs = cal["diagnostics"]["observed_vendor_split"]
    assert set(obs) == {"vendor_A", "vendor_B"} and obs["vendor_A"]["n_participants"] == 5
    assert len(cal["params"]["vendor_shares"]) == 2
    ds2 = quarantine("synthetic_flows.csv", open(os.path.join(FIX, "synthetic_flows.csv"), "rb").read(),
                     uploader="p", classification="synthetic")
    assert calibrate(ds2)["diagnostics"]["vendor_split_source"] == "inferred from flow communities"
