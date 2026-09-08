"""Transparency record and role fields."""

import json

from hsl.atrs import atrs_record, render_markdown
from hsl.critic import critic_check, numbers_in, numbers_in_artefacts


def _art():
    return json.load(open("sample_outputs/artefacts.json"))


def test_record_has_atrs_tiers_and_sections():
    a = _art()
    rec = atrs_record(a, {"preparer": "D. Godorozha", "preparer_role": "certified function",
                          "gate1": {"actor": "R. Ahmed", "role": "SMF24", "ts": "t"},
                          "gate2": {"actor": "R. Ahmed", "role": "SMF24", "ts": "t"}}, "20260905-000000-abcd")
    assert set(rec) >= {"tier_1", "tier_2", "run_id", "standard", "status"}
    t2 = rec["tier_2"]
    assert set(t2) == {"owner_and_responsibility", "description_and_rationale", "decision_making_process",
                       "tool_specification", "data", "risks_mitigations_and_impact_assessments"}
    assert t2["owner_and_responsibility"]["senior_responsible_owner"] == "R. Ahmed"
    assert t2["owner_and_responsibility"]["senior_responsible_owner_role"] == "SMF24"
    assert t2["data"]["sensitive_attributes"].startswith("None")
    assert len(t2["risks_mitigations_and_impact_assessments"]["risks"]) >= 6
    md = render_markdown(rec)
    assert "## Tier 1" in md and "### Risks mitigations and impact assessments" in md
    assert "SMF24" in md and "—" not in md


def test_record_numbers_are_vetted_against_the_artefacts():
    a = _art()
    rec = atrs_record(a, {"preparer": "p", "gate2": {"actor": "q", "ts": "t"}}, "20260905-000000-abcd")
    md = render_markdown(rec)
    allowed = numbers_in_artefacts(a)
    assert all(x in allowed for x in numbers_in(md)), [x for x in numbers_in(md) if x not in allowed]
    rep = critic_check(a, atrs_text=md)
    names = [c["name"] for c in rep["checks"]]
    assert "every number in the transparency record appears in the artefacts" in names
    assert next(c for c in rep["checks"] if c["name"].startswith("every number in the transparency"))["ok"]
    bad = critic_check(a, atrs_text=md + "\nDecision gap 0.9731.")
    assert not next(c for c in bad["checks"] if c["name"].startswith("every number in the transparency"))["ok"]
