"""Approvers tied to a register of regulated persons."""

import os

import pytest

from hsl.register import PersonRegister, load_register

FIX = os.path.join(os.path.dirname(__file__), "..", "sample_data", "register.csv")


def test_register_lookup_and_verdicts(monkeypatch):
    monkeypatch.delenv("HSL_REGISTER_REQUIRED", raising=False)
    reg = PersonRegister(FIX)
    assert reg.configured and reg.required and len(load_register(FIX)) == 5
    ok = reg.check("R. Ahmed", "SMF24")
    assert ok["ok"] and ok["match"]["irn"] == "RXA01234" and ok["match"]["function"].startswith("SMF24")
    assert reg.check("RXA01234")["ok"]
    assert reg.check("Rajib Ahmed", "SMF16")["match"]["note"].startswith("declared function")
    bad = reg.check("Nobody Here")
    assert not bad["ok"] and "not on the register" in bad["reason"]
    inactive = reg.check("Former Approver")
    assert not inactive["ok"] and "not active" in inactive["reason"]
    cert = reg.check("D. Godorozha", "certified function")
    assert cert["ok"] and cert["match"]["function"].startswith("Certified")
    none = PersonRegister("/no/such/file")
    assert not none.configured and none.check("anyone")["ok"] is True
    monkeypatch.setenv("HSL_REGISTER_REQUIRED", "on")
    strict = PersonRegister("/no/such/file")
    assert strict.required and strict.check("anyone")["ok"] is False


def test_cli_gate_refuses_unregistered_approver(tmp_path, monkeypatch):
    from hsl.orchestrator import run_pipeline
    monkeypatch.setenv("HSL_REGISTER", FIX)
    with pytest.raises(SystemExit) as e:
        run_pipeline("q", str(tmp_path), approve_battery=True, approve_briefing=False,
                     approver="Nobody Here", approver_role="SMF24", preparer="D. Godorozha",
                     preparer_role="certified function", register_path=FIX)
    assert "register" in str(e.value)


def test_dev_mode_identities_and_mandatory_functions(tmp_path, monkeypatch):
    from hsl.orchestrator import run_pipeline
    monkeypatch.setenv("HSL_DEV_MODE", "on")
    reg = PersonRegister(FIX)
    ok = reg.check("Developer2", "Developer2")
    assert ok["ok"] and ok["match"]["dev_mode"] and ok["match"]["source"].startswith("dev mode")
    assert reg.check("developer 1")["ok"]                 # spacing and case do not matter
    assert not reg.check("Developer3")["ok"]              # only the two identities
    monkeypatch.setenv("HSL_DEV_MODE", "off")
    assert not PersonRegister(FIX).check("Developer2")["ok"]
    monkeypatch.setenv("HSL_DEV_MODE", "on")
    # the functions are mandatory on the command line; dev identities default theirs
    with pytest.raises(SystemExit) as e:
        run_pipeline("q", str(tmp_path / "a"), approve_battery=True, approver="R. Ahmed", preparer="D. Godorozha",
                     register_path=FIX)
    assert "function is required" in str(e.value)
    with pytest.raises(SystemExit) as e2:
        run_pipeline("q", str(tmp_path / "b"), approve_battery=True, approver="R. Ahmed", approver_role="SMF24",
                     preparer="D. Godorozha", register_path=FIX)
    assert "preparer's function" in str(e2.value)
