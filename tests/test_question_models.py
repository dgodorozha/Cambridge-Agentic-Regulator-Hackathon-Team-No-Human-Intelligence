"""The deterministic question interpreter and the model providers."""

import json
import os

import pytest

from hsl.question import interpret, question_family, direct_answer
from hsl.llm import (make_client, OpenAICompatibleClient, LocalTransformersClient, AnthropicClient, ModelClient,
                     AzureOpenAIClient, GeminiClient, CustomTemplateClient, PROVIDERS, _check_endpoint, _dig)


def test_interpret_reads_numbers_mechanisms_and_tools():
    p = interpret("Would a sentinel informed dynamic throttle have contained a flash dislocation with 40 per cent of "
                  "agents on one foundation model vendor, and which surveillance candidate should be certified?")
    assert p["params"]["vendor_share"] == pytest.approx(0.40)
    assert p["rules_of_interest"] == ["dynamic_throttle"] and p["interpreted"]
    assert p["family"]["vendor_shares"][0] == pytest.approx(0.40)
    p2 = interpret("If the dominant vendor's model misfires, does a kill switch or a market wide circuit breaker "
                   "contain it better? Assume correlation 0.7 and a 3% shock.")
    assert p2["params"] == {"vendor_rho": 0.7, "shock_size": 0.03} and "vendor_fault" in p2["mechanisms"]
    assert {"kill_switch", "static_circuit_breaker", "market_wide_breaker"} <= set(p2["rules_of_interest"])
    assert p2["family"]["vendor_fault_time"] == 300 and p2["unmatched"] == []
    p3 = interpret("Which sentinel is best?")
    assert not p3["interpreted"] and p3["family"] is None and p3["unmatched"] == ["Which sentinel is best"]
    specs = question_family(p2)
    assert [s.name for s in specs] == ["question_0", "question_1"] and specs[0].vendor_fault_time == 300


def test_direct_answer_reads_only_artefacts():
    a = json.load(open("sample_outputs/artefacts.json"))
    p = interpret("does a kill switch contain a faulty model episode? and the absorption ratio?")
    da = direct_answer(p, a, {"absorption_ratio": "Absorption ratio"})
    kinds = {t["kind"] for t in da["tools"]}
    assert kinds == {"rule", "sentinel"} and da["certified"] == a["certified"]
    assert direct_answer(interpret("Which sentinel is best?"), a, {}) is None


def test_model_providers_and_endpoint_rules(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("HSL_LLM_PROVIDER", raising=False)
    assert make_client().provider == "off" and not make_client().available
    monkeypatch.setenv("HSL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("HSL_LLM_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("HSL_LLM_MODEL", "local-model")
    c = make_client()
    assert isinstance(c, OpenAICompatibleClient) and c.available
    _check_endpoint("http://127.0.0.1:11434/v1/chat/completions")            # loopback may be http
    with pytest.raises(RuntimeError):
        _check_endpoint("http://gateway.bank.internal/v1/chat/completions")     # remote must be https
    with pytest.raises(RuntimeError):
        _check_endpoint("https://gateway.bank.internal/v1/chat/completions", ["api.anthropic.com"])
    _check_endpoint("https://gateway.bank.internal/v1/chat/completions", ["gateway.bank.internal"])
    # a fake OpenAI compatible server response is parsed
    import hsl.llm as L
    monkeypatch.setattr(L, "_post_json", lambda url, body, headers, timeout, allowlist=None:
                        {"choices": [{"message": {"content": "hello from " + body["model"]}}]})
    assert c.complete("hi") == "hello from local-model"
    lc = LocalTransformersClient("/definitely/not/a/model")
    assert not lc.available
    with pytest.raises(RuntimeError):
        ModelClient().complete("x")
    assert AnthropicClient(api_key="", enabled="auto").available is False


def test_azure_gemini_and_custom_providers(monkeypatch):
    import hsl.llm as L
    calls = []

    def fake_post(url, body, headers, timeout, allowlist=None):
        calls.append((url, body, headers))
        if "openai/deployments" in url:
            return {"choices": [{"message": {"content": "azure says hi"}}]}
        if ":generateContent" in url:
            return {"candidates": [{"content": {"parts": [{"text": "gemini "}, {"text": "says hi"}]}}]}
        return {"result": {"answer": {"text": "custom says " + body["input"]["question"]}}}
    monkeypatch.setattr(L, "_post_json", fake_post)
    az = AzureOpenAIClient(base="https://res.openai.azure.com", model="gpt-deploy", api_key="k")
    assert az.available and az.complete("q", system="s") == "azure says hi"
    assert "api-version=2024-10-21" in calls[-1][0] and calls[-1][2]["api-key"] == "k"
    ge = GeminiClient(model="gemini-2.0", api_key="k")
    assert ge.available and ge.complete("q", system="s") == "gemini says hi"
    assert calls[-1][1]["systemInstruction"]["parts"][0]["text"] == "s" and calls[-1][2]["x-goog-api-key"] == "k"
    cu = CustomTemplateClient(base="https://models.bank.internal/ask",
                              template='{"input": {"question": "{prompt}", "context": "{system}"}, "max": {max_tokens}}',
                              headers='{"Authorization": "Bearer ${HSL_LLM_KEY}"}', response_path="result.answer.text",
                              api_key="tok")
    assert cu.available and cu.complete('say "hi"', system="s", max_tokens=7) == 'custom says say "hi"'
    assert calls[-1][1]["max"] == 7 and calls[-1][2]["Authorization"] == "Bearer tok"
    assert _dig({"a": [{"b": "x"}]}, "a.0.b") == "x"
    monkeypatch.setenv("HSL_LLM_PROVIDER", "azure"); monkeypatch.setenv("HSL_LLM_BASE", "https://r.openai.azure.com")
    monkeypatch.setenv("HSL_LLM_MODEL", "d"); monkeypatch.setenv("HSL_LLM_KEY", "k")
    assert make_client().provider == "azure"
    monkeypatch.setenv("HSL_LLM_PROVIDER", "gemini")
    assert make_client().provider == "gemini"
    assert set(PROVIDERS) == {"off", "anthropic", "openai", "azure", "gemini", "custom", "local"}


def test_model_touchpoints_end_to_end_with_a_fake_openai_server(monkeypatch, tmp_path):
    """The configured client reaches planning, persona distillation, the
    briefing draft (with critic vetting) and ASK, through a real HTTP
    client against a loopback OpenAI compatible server."""
    import json
    from tests.fake_model_server import FakeModelServer
    from hsl.ledger import Ledger
    from hsl.orchestrator import plan_battery
    from hsl.llm import make_client, ask_llm, draft_briefing_llm
    from hsl.personas import bind_persona_hashes
    from hsl.simulator import scenario_battery
    srv = FakeModelServer().start()
    try:
        monkeypatch.setenv("HSL_LLM_PROVIDER", "openai")
        monkeypatch.setenv("HSL_LLM_BASE", srv.base)
        monkeypatch.setenv("HSL_LLM_MODEL", "fake-model")
        monkeypatch.setenv("HSL_LLM_KEY", "secret-token")
        client = make_client()
        assert client.provider == "openai" and client.available
        log = Ledger(str(tmp_path / "l.jsonl"), "20260907-000000-abcd", secret="k")
        # 1. planning: the model's valid family is used, the invalid and reserved ones rejected,
        #    the guardrail and report families kept, and the question family added by the parser
        specs = plan_battery("does a kill switch contain a faulty vendor model with 40 per cent on one vendor?",
                             log, client)
        fams = {s.family for s in specs}
        assert "planned_vendor_fault" in fams and "question" in fams
        assert {"quiet", "holdout_herd", "rl_emergent", "vendor_fault", "liquidity_withdrawal"} <= fams
        events = [json.loads(l) for l in open(log.path)]
        used = next(e for e in events if e["event"] == "llm_plan_used")
        assert used["payload"]["provider"] == "openai" and used["payload"]["model"] == "fake-model"
        acc = {a["name"]: a["clamped"] for a in used["payload"]["accepted"]}
        assert set(acc) == {"planned_vendor_fault", "planned_out_of_bounds"} and acc["planned_out_of_bounds"]
        assert {r["name"] for r in used["payload"]["rejected"]} == {"quiet"}
        assert any(c["auth"] == "Bearer secret-token" for c in srv.calls)
        # 2. persona distillation went through the model
        persona_specs = [s for s in scenario_battery() if s.persona_share > 0][:1]
        used_p = bind_persona_hashes(persona_specs, client, log)
        assert used_p and any("trading agent" in c["system"].lower() or "foundation model" in c["system"] for c in srv.calls)
        # 3. briefing draft: accepted when its numbers are in the artefacts, rejected otherwise
        art = json.load(open("sample_outputs/artefacts.json"))
        text, used_llm = draft_briefing_llm(art, client, "deterministic text", log)
        assert used_llm and text.startswith("# Model draft")
        srv.set_rogue_briefing(True)
        text2, used2 = draft_briefing_llm(art, client, "deterministic text", log)
        assert not used2 and text2 == "deterministic text"
        srv.set_rogue_briefing(False)
        assert any(json.loads(l)["event"] == "llm_draft_rejected" for l in open(log.path))
        # 4. ASK phrasing
        out = ask_llm("which sentinel should be certified?", [{"id": "s1", "title": "t", "text": "x"}],
                      "Tail dependence is certified.", client, log)
        assert out.startswith("[model phrased]") and "Tail dependence is certified." in out
    finally:
        srv.stop()


def test_ask_intents_reach_the_question_and_backtest_chunks():
    import json
    from hsl.ask import intent_of, answer
    assert intent_of("what does the run say about my question?") == "question"
    assert intent_of("what did the backtest show?") == "backtest"
    a = json.load(open("sample_outputs/artefacts.json"))
    snap = {"artefacts": a, "summary": a.get("sentinels"), "rules": a.get("rules"), "gap": a.get("decision_gap"),
            "aut": None, "run_id": "r", "stage": "released", "ledger_n": 0, "question": a.get("question")}
    out = answer(snap, "what does the run say about my question?")
    assert any(s["id"] == "question" for s in out["sources"]) and "Matched" in out["text"]
    out2 = answer(snap, "what did the backtest show?")
    assert any(s["id"] == "backtest" for s in out2["sources"])
