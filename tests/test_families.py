"""Authority defined scenario families."""

import json
import os

from hsl.families import (validate_family, expand_family, FamilyStore, family_hash, template, MAX_FAMILIES,
                          load_family_file)
from hsl.ledger import Ledger
from hsl.orchestrator import include_families
from hsl.simulator import scenario_battery, simulate, battery_hash, CUSTOM_NOTES


def test_validate_clamps_and_refuses():
    ok, fam, err, notes = validate_family({"name": "my_market", "vendor_shares": [0.6, 0.2], "vendor_rhos": [1.4, 0.5],
                                           "shock_size": 0.5, "seeds": 9})
    assert ok and fam["vendor_shares"][0] == 0.45 and fam["vendor_rhos"][0] == 0.95
    assert fam["shock_size"] == 0.10 and fam["seeds"] == 5 and len(notes) >= 4
    for bad, needle in [({"name": "quiet"}, "built in"), ({"name": "Bad Name"}, "name must"),
                        ({"name": "x_y_z", "generator": "nope"}, "generator"),
                        ({"name": "x_y_z", "vendor_shares": [0.4, 0.4], "vendor_rhos": [0.5, 0.5]}, "sum"),
                        ({"name": "x_y_z", "persona_share": 0.2}, "persona"),
                        ({"name": "x_y_z", "unknown_key": 1}, "unknown key"),
                        ({"name": "x_y_z", "shock_time": 595}, "before the end")]:
        ok, fam, err, notes = validate_family(bad)
        assert not ok and any(needle in e for e in err), (bad, err)
    ok, fam, err, notes = validate_family({"name": "quiet_custom", "quiet": True})
    assert ok and fam["shock_size"] == 0.0


def test_expand_is_deterministic_and_simulates():
    ok, fam, _, _ = validate_family({"name": "faulty_vendor", "seeds": 2, "vendor_shares": [0.35, 0.15],
                                     "vendor_rhos": [0.6, 0.3], "vendor_fault_time": 300, "shock_size": 0.02})
    a, b = expand_family(fam), expand_family(fam)
    assert [s.seed for s in a] == [s.seed for s in b] and a[0].seed != a[1].seed
    assert a[0].family == "faulty_vendor" and a[0].vendor_fault_time == 300
    r = simulate(a[0])
    assert r.destabilising[r.agent_cluster == 0].all()
    ok2, fam2, _, _ = validate_family({"name": "faulty_vendor_b", "seeds": 2, "vendor_shares": [0.35, 0.15],
                                       "vendor_rhos": [0.6, 0.3], "vendor_fault_time": 300, "shock_size": 0.02})
    assert expand_family(fam2)[0].seed != a[0].seed          # same parameters, different name, different draws


def test_store_provenance_and_limits(tmp_path):
    st = FamilyStore(str(tmp_path))
    res = st.add({"name": "gilt_split", "note": "two vendors"}, author="D. Godorozha")
    assert res["ok"] and res["record"]["author"] == "D. Godorozha" and len(res["record"]["sha256"]) == 64
    assert res["record"]["sha256"] == family_hash(res["record"]["family"])
    assert st.add({"name": "quiet"}, "x")["ok"] is False
    specs, notes = st.specs()
    assert len(specs) == 3 and notes["gilt_split"] == "two vendors"
    st.set_enabled("gilt_split", False)
    assert st.specs()[0] == []
    for i in range(MAX_FAMILIES):
        st.add({"name": f"fam_{i}"}, "x")
    assert not st.add({"name": "one_too_many"}, "x")["ok"]
    assert st.remove("fam_0") and not st.remove("fam_0")


def test_include_families_extends_battery_and_hash(tmp_path):
    log = Ledger(str(tmp_path / "l.jsonl"), "20260905-000000-abcd", secret="k")
    specs = scenario_battery(include_rl=False, include_reports=False)
    h0 = battery_hash(specs)
    st = FamilyStore(str(tmp_path))
    st.add({"name": "authority_market", "note": "supervised structure", "seeds": 2}, "D. Godorozha")
    added = include_families(specs, log, family_docs=[{"name": "cli_family", "seeds": 1, "holdout": True}],
                             store=st, author="D. Godorozha")
    assert added == ["cli_family", "authority_market"]
    assert battery_hash(specs) != h0 and sum(1 for s in specs if s.family == "authority_market") == 2
    assert next(s for s in specs if s.family == "cli_family").holdout
    assert "authority_market" in CUSTOM_NOTES and "defined by the authority" in CUSTOM_NOTES["authority_market"]
    include_families(specs, log, family_docs=[{"name": "bad name"}])
    events = [json.loads(l)["event"] for l in open(log.path)]
    assert "family_included" in events and "family_rejected" in events


def test_template_file_validates():
    docs = load_family_file(os.path.join(os.path.dirname(__file__), "..", "sample_data", "family_template.json"))
    ok, fam, err, notes = validate_family(docs[0])
    assert ok and fam["name"] == "my_family"
    assert template()["name"] == "my_family"
