"""Model layer: three providers behind one interface, every path boxed by a
fixed server side prompt and verified by the critic afterwards.

Providers (HSL_LLM_PROVIDER):
  anthropic  the Anthropic Messages API, or a gateway that proxies it
             (HSL_API_BASE); key from ANTHROPIC_API_KEY.
  azure      Azure OpenAI Service, the platform behind Microsoft Copilot for
             enterprises: HSL_LLM_BASE is the resource endpoint, HSL_LLM_MODEL
             the deployment name, HSL_LLM_KEY the key.
  gemini     the Google Gemini API: HSL_LLM_MODEL and HSL_LLM_KEY.
  custom     any JSON API the authority runs, described without code by a
             request template, headers and a response path.
  openai     any OpenAI compatible chat completions endpoint: an
             institutional gateway, Azure style deployments behind such a
             gateway, or a local server (vLLM, llama.cpp, Ollama, LM Studio)
             on the loopback interface. HSL_LLM_BASE is the base URL ending
             in /v1, HSL_LLM_MODEL the model name, HSL_LLM_KEY the bearer
             token (optional for local servers).
  local      a model the authority has installed itself, loaded from a
             directory with the transformers library (HSL_LLM_PATH). HSL
             never downloads a model; the authority obtains it through its
             own channel, places it on disk and installs `transformers` and
             `torch` in the environment. Generation runs in process.
  off        no model; every path is deterministic (the default).

Network rules for the API providers: https is required unless the host is
the loopback interface; when an egress allowlist is configured the model's
host must be on it; responses are capped at 4 MB and calls time out.
Keys come from the environment only and are never written anywhere. If no
provider is configured, or a call fails, every entry point falls back to
the deterministic path, so the pipeline always completes and no generated
text can alter a computed number.
"""

import json
import os
import re
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.anthropic.com"
MODEL = os.environ.get("HSL_MODEL", "claude-sonnet-4-6")
MAX_QUESTION_CHARS = 600
RESPONSE_CAP = 4 * 1024 * 1024
LOOPBACK = ("127.0.0.1", "localhost", "::1")


def _host(url):
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _check_endpoint(url, allowlist=None):
    """https unless loopback; host on the allowlist when one is configured."""
    host = _host(url)
    if not host:
        raise RuntimeError("model endpoint has no host")
    if host not in LOOPBACK and not url.startswith("https://"):
        raise RuntimeError("the model endpoint must be https unless it is on the loopback interface")
    allow = [a.lower() for a in (allowlist or []) if a]
    if allow and host not in LOOPBACK and host not in allow:
        raise RuntimeError(f"model host {host} is not on the egress allowlist")


def _post_json(url, body, headers, timeout, allowlist=None):
    _check_endpoint(url, allowlist)
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers=dict({"Content-Type": "application/json"}, **headers))
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - scheme and host checked above
        raw = r.read(RESPONSE_CAP + 1)
    if len(raw) > RESPONSE_CAP:
        raise RuntimeError("model response exceeds the size cap")
    return json.loads(raw)


class ModelClient:
    provider = "off"
    model = None
    available = False

    def complete(self, prompt, system=None, max_tokens=1200, timeout=45):
        raise RuntimeError("no model configured")

    def describe(self):
        d = {"provider": self.provider, "model": self.model, "available": bool(self.available)}
        if getattr(self, "_error", None):
            d["note"] = self._error
        return d


class AnthropicClient(ModelClient):
    provider = "anthropic"

    def __init__(self, api_key=None, base=None, model=None, enabled=None, allowlist=None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.base = (base or os.environ.get("HSL_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.model = model or MODEL
        mode = (os.environ.get("HSL_LLM", "auto") if enabled is None else enabled).lower()
        self.enabled = mode not in ("off", "0", "false", "no")
        self.allowlist = allowlist

    @property
    def available(self):
        return bool(self.api_key) and self.enabled

    def complete(self, prompt, system=None, max_tokens=1200, timeout=45):
        body = {"model": self.model, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        data = _post_json(f"{self.base}/v1/messages", body,
                          {"anthropic-version": "2023-06-01", "x-api-key": self.api_key or ""},
                          timeout, self.allowlist)
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


ClaudeClient = AnthropicClient      # name kept for existing call sites


class OpenAICompatibleClient(ModelClient):
    """Chat completions against any OpenAI compatible endpoint: institutional
    gateways and local servers alike."""
    provider = "openai"

    def __init__(self, base=None, model=None, api_key=None, enabled=True, allowlist=None):
        self.base = (base or os.environ.get("HSL_LLM_BASE", "")).rstrip("/")
        self.model = model or os.environ.get("HSL_LLM_MODEL", "")
        self.api_key = api_key if api_key is not None else os.environ.get("HSL_LLM_KEY", "").strip()
        self.enabled = enabled
        self.allowlist = allowlist

    @property
    def available(self):
        return bool(self.base and self.model) and self.enabled

    def complete(self, prompt, system=None, max_tokens=1200, timeout=60):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = _post_json(f"{self.base}/chat/completions", body, headers, timeout, self.allowlist)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("model returned no choices")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content or ""


class LocalTransformersClient(ModelClient):
    """A model the authority installed itself, loaded from disk with the
    transformers library. Nothing is downloaded: the path must already hold
    the model files. Loaded lazily on first use and kept in process."""
    provider = "local"

    def __init__(self, path=None, max_input_tokens=4096, enabled=True):
        self.path = path or os.environ.get("HSL_LLM_PATH", "")
        self.model = os.path.basename(self.path.rstrip("/")) if self.path else None
        self.enabled = enabled
        self.max_input_tokens = max_input_tokens
        self._pipe = None
        self._error = None

    @property
    def available(self):
        if not (self.enabled and self.path and os.path.isdir(self.path)):
            return False
        try:
            import transformers  # noqa: F401
            return True
        except ImportError:
            self._error = "transformers is not installed; pip install transformers torch"
            return False

    def _load(self):
        if self._pipe is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            tok = AutoTokenizer.from_pretrained(self.path, local_files_only=True)
            mdl = AutoModelForCausalLM.from_pretrained(self.path, local_files_only=True)
            self._pipe = pipeline("text-generation", model=mdl, tokenizer=tok)
        return self._pipe

    def complete(self, prompt, system=None, max_tokens=1200, timeout=None):
        pipe = self._load()
        tok = pipe.tokenizer
        text = prompt
        if getattr(tok, "chat_template", None):
            msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        elif system:
            text = system + "\n\n" + prompt
        out = pipe(text, max_new_tokens=max_tokens, do_sample=False, return_full_text=False,
                   truncation=True, max_length=self.max_input_tokens)
        return (out[0].get("generated_text") or "") if out else ""


class AzureOpenAIClient(ModelClient):
    """Azure OpenAI Service, the platform behind Microsoft Copilot for
    enterprises: a deployment on the authority's own Azure resource.
    HSL_LLM_BASE is the resource endpoint (https://<resource>.openai.azure.com),
    HSL_LLM_MODEL the deployment name, HSL_LLM_KEY the key (or a bearer
    token with HSL_LLM_AUTH=bearer), HSL_LLM_API_VERSION the API version."""
    provider = "azure"

    def __init__(self, base=None, model=None, api_key=None, api_version=None, auth=None, enabled=True,
                 allowlist=None):
        self.base = (base or os.environ.get("HSL_LLM_BASE", "")).rstrip("/")
        self.model = model or os.environ.get("HSL_LLM_MODEL", "")
        self.api_key = api_key if api_key is not None else os.environ.get("HSL_LLM_KEY", "").strip()
        self.api_version = api_version or os.environ.get("HSL_LLM_API_VERSION", "2024-10-21")
        self.auth = (auth or os.environ.get("HSL_LLM_AUTH", "key")).lower()
        self.enabled = enabled
        self.allowlist = allowlist

    @property
    def available(self):
        return bool(self.base and self.model and self.api_key) and self.enabled

    def complete(self, prompt, system=None, max_tokens=1200, timeout=60):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {"messages": msgs, "max_tokens": max_tokens, "temperature": 0}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.auth == "bearer" else {"api-key": self.api_key}
        url = f"{self.base}/openai/deployments/{urllib.parse.quote(self.model)}/chat/completions?api-version={self.api_version}"
        data = _post_json(url, body, headers, timeout, self.allowlist)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("model returned no choices")
        content = (choices[0].get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content or ""


class GeminiClient(ModelClient):
    """Google Gemini API (generateContent). HSL_LLM_MODEL is the model name,
    HSL_LLM_KEY the API key; HSL_LLM_BASE may point at a gateway."""
    provider = "gemini"
    DEFAULT = "https://generativelanguage.googleapis.com"

    def __init__(self, base=None, model=None, api_key=None, enabled=True, allowlist=None):
        self.base = (base or os.environ.get("HSL_LLM_BASE") or self.DEFAULT).rstrip("/")
        self.model = model or os.environ.get("HSL_LLM_MODEL", "")
        self.api_key = api_key if api_key is not None else os.environ.get("HSL_LLM_KEY", "").strip()
        self.enabled = enabled
        self.allowlist = allowlist

    @property
    def available(self):
        return bool(self.model and self.api_key) and self.enabled

    def complete(self, prompt, system=None, max_tokens=1200, timeout=60):
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{self.base}/v1beta/models/{urllib.parse.quote(self.model)}:generateContent"
        data = _post_json(url, body, {"x-goog-api-key": self.api_key}, timeout, self.allowlist)
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError("model returned no candidates")
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def _dig(data, path):
    """Walk a dotted path with integer indices: choices.0.message.content."""
    cur = data
    for key in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(key)]
        else:
            cur = cur[key]
    return cur


class CustomTemplateClient(ModelClient):
    """Any JSON API the authority runs, described without code: a request
    body template with {prompt}, {system}, {model} and {max_tokens}
    placeholders (HSL_LLM_TEMPLATE), a JSON object of headers where
    ${HSL_LLM_KEY} is substituted (HSL_LLM_HEADERS), the full endpoint URL
    (HSL_LLM_BASE) and the dotted path of the reply text in the response
    (HSL_LLM_RESPONSE_PATH, for example choices.0.message.content)."""
    provider = "custom"

    def __init__(self, base=None, model=None, template=None, headers=None, response_path=None, api_key=None,
                 enabled=True, allowlist=None):
        self.base = (base or os.environ.get("HSL_LLM_BASE", "")).strip()
        self.model = model or os.environ.get("HSL_LLM_MODEL", "custom")
        self.template = template or os.environ.get("HSL_LLM_TEMPLATE", "")
        self.headers_json = headers or os.environ.get("HSL_LLM_HEADERS", "{}")
        self.response_path = response_path or os.environ.get("HSL_LLM_RESPONSE_PATH", "")
        self.api_key = api_key if api_key is not None else os.environ.get("HSL_LLM_KEY", "").strip()
        self.enabled = enabled
        self.allowlist = allowlist

    @property
    def available(self):
        return bool(self.base and self.template and self.response_path) and self.enabled

    def complete(self, prompt, system=None, max_tokens=1200, timeout=60):
        def esc(s):
            return json.dumps(str(s))[1:-1]
        text = (self.template.replace("{prompt}", esc(prompt)).replace("{system}", esc(system or ""))
                .replace("{model}", esc(self.model)).replace("{max_tokens}", str(int(max_tokens))))
        body = json.loads(text)
        headers = {k: str(v).replace("${HSL_LLM_KEY}", self.api_key) for k, v in json.loads(self.headers_json).items()}
        data = _post_json(self.base, body, headers, timeout, self.allowlist)
        out = _dig(data, self.response_path)
        return out if isinstance(out, str) else json.dumps(out)


PROVIDERS = {
    "off": "no model; every path deterministic",
    "anthropic": "Anthropic Messages API or a gateway that proxies it",
    "openai": "any OpenAI compatible chat completions endpoint: institutional gateways, Mistral, Groq, Together, "
              "Bedrock's OpenAI compatible endpoint, Azure AI Foundry inference, vLLM, llama.cpp, Ollama, LM Studio",
    "azure": "Azure OpenAI Service, the platform behind Microsoft Copilot for enterprises",
    "gemini": "Google Gemini API",
    "custom": "any JSON API described by a request template and a response path",
    "local": "a model installed by the authority, loaded from disk with transformers",
}


def make_client(cfg=None):
    """The configured client. `cfg` is the Config (or None to read the
    environment); provider off returns a client that is never available."""
    env = os.environ
    provider = (getattr(cfg, "llm_provider", None) or env.get("HSL_LLM_PROVIDER") or "").strip().lower()
    allow = getattr(cfg, "egress_allowlist", None) or None
    if not provider:
        # backwards compatible default: anthropic when a key is present, else off
        provider = "anthropic" if env.get("ANTHROPIC_API_KEY", "").strip() else "off"
    if provider == "anthropic":
        return AnthropicClient(api_key=getattr(cfg, "api_key", None), model=getattr(cfg, "model", None),
                               enabled=getattr(cfg, "llm_mode", None), allowlist=allow)
    if provider == "openai":
        return OpenAICompatibleClient(base=getattr(cfg, "llm_base", None), model=getattr(cfg, "llm_model", None),
                                      allowlist=allow)
    if provider == "azure":
        return AzureOpenAIClient(base=getattr(cfg, "llm_base", None), model=getattr(cfg, "llm_model", None),
                                 allowlist=allow)
    if provider == "gemini":
        return GeminiClient(base=getattr(cfg, "llm_base", None) or None, model=getattr(cfg, "llm_model", None),
                            allowlist=allow)
    if provider == "custom":
        return CustomTemplateClient(base=getattr(cfg, "llm_base", None), model=getattr(cfg, "llm_model", None),
                                    allowlist=allow)
    if provider == "local":
        return LocalTransformersClient(path=getattr(cfg, "llm_path", None))
    return ModelClient()


# ---------- LLM battery planning ----------

PLAN_SYSTEM = (
    "You translate a financial stability policy question into simulation "
    "battery parameters for an agent based market sandbox. Respond ONLY "
    "with JSON, no preamble and no markdown fences.")

PLAN_PROMPT = """Policy question: {q}

Design the herding families of a scenario battery for this question. Respond with ONE JSON object:
{{"families": [ {{family document}}, ... 2 to 5 entries ], "rationale": one sentence}}

A family document has these keys (all optional except name):
  name (lower case, letters, digits, underscores), note (one line), seeds (1 to 5),
  generator ("shared_signal", "imitation", "voter" or "sqrt_impact"),
  vendor_shares (list, each 0 to 0.45, sum at most 0.70), vendor_rhos (list, same length, 0 to 0.95),
  shock_size (0 to 0.10), shock_time (50 to 900), n_agents (40 to 200), t_steps (200 to 1000),
  frac_fundamental (0.05 to 0.40), evader_cohorts (0 to 8), manipulator_share (0 to 0.15),
  persona ("momentum_follower", "trend_vol_capped" or "contrarian") with persona_share (0 to 0.45),
  vendor_fault_time (a step; the dominant vendor's model misfires from then for vendor_fault_len steps),
  liquidity_withdrawal_time (a step; liquidity providers cut provision to liquidity_withdrawal_scale),
  false_shock_len (0 to 80; the shock is misinformation retracted after this many steps).
Use a mechanism only when the question calls for it. Leave at least 5% of agents for noise traders."""


def plan_battery_llm(question, client, log, seeds_per=3):
    """Ask the configured model to design the herding families as family
    documents; validate each against the family bounds (clamps reported);
    keep every fixed guardrail and report driven family so nothing can be
    planned away. The question family is added by the caller."""
    from .simulator import fixed_battery as scenario_battery
    from .families import validate_family, expand_family
    if not client.available:
        log("llm_plan_skipped", reason="no model configured; using fixed battery")
        return scenario_battery(), False
    try:
        raw = client.complete(PLAN_PROMPT.format(q=question[:MAX_QUESTION_CHARS]),
                              system=PLAN_SYSTEM, max_tokens=1200)
        plan = json.loads(re.sub(r"```(json)?", "", raw).strip())
        docs = plan.get("families") or plan.get("herding") or []
        specs, accepted, rejected = [], [], []
        for j, doc in enumerate(docs[:5]):
            if not isinstance(doc, dict):
                continue
            doc = dict(doc)
            doc["name"] = re.sub(r"[^a-z0-9_]+", "_", str(doc.get("name", f"planned_{j}")).lower())[:32].strip("_") \
                or f"planned_{j}"
            if not re.match(r"^[a-z]", doc["name"]):
                doc["name"] = "planned_" + doc["name"]
            doc["seeds"] = int(min(seeds_per, max(1, int(doc.get("seeds", seeds_per) or seeds_per))))
            ok, fam, errors, notes = validate_family(doc)
            if not ok:
                rejected.append({"name": doc["name"], "errors": errors[:3]})
                continue
            specs.extend(expand_family(fam))
            accepted.append({"name": fam["name"], "clamped": notes})
        if not accepted:
            raise ValueError("no planned family passed validation: " + "; ".join(
                f"{r['name']}: {', '.join(r['errors'])}" for r in rejected)[:300])
        fixed = scenario_battery()
        keep = ("rl_emergent", "evader", "ignition", "persona_llm", "vendor_fault", "liquidity_withdrawal",
                "misinformation", "quiet", "holdout_herd", "holdout_quiet")
        planned_names = {s.family for s in specs}
        specs += [sp for sp in fixed if sp.family in keep and sp.family not in planned_names]
        log("llm_plan_used", provider=client.provider, model=client.model, rationale=str(plan.get("rationale"))[:300],
            accepted=accepted, rejected=rejected, n_scenarios=len(specs))
        return specs, True
    except Exception as e:  # noqa: BLE001 - any failure falls back to the fixed battery
        log("llm_plan_failed", error=str(e)[:200])
        return scenario_battery(), False


# ---------- LLM briefing drafting with critic number verification ----------

DRAFT_SYSTEM = (
    "You draft concise supervisory briefings for a financial authority. "
    "Use ONLY the numbers present in the artefacts JSON; never invent, "
    "round differently, or extrapolate figures. British spelling. No em "
    "dashes. Advisory tone; outputs are comparative rankings on synthetic "
    "scenarios, never forecasts.")


def draft_briefing_llm(artefacts, client, deterministic_text, log):
    """Draft prose with Claude, then the critic's number vetting must pass.
    Returns (text, used_llm). Any failure returns the deterministic text."""
    from .critic import numbers_in, numbers_in_artefacts
    if not client.available:
        log("llm_draft_skipped", reason="no API key or LLM disabled; deterministic briefing")
        return deterministic_text, False
    try:
        slim = {k: v for k, v in artefacts.items() if k not in ("battery",)}
        prompt = ("Artefacts JSON:\n" + json.dumps(slim, indent=1, default=str)[:60000]
                  + "\n\nDraft a one page markdown supervisory briefing: headline finding on "
                    "the decision gap with its bootstrap probability of inversion, the two "
                    "rankings, a table of sentinel metrics with intervals and grades, held out "
                    "and adversarial results, a table of intervention outcomes, the autonomy "
                    "gate's leave one out figures, and a limitations line.")
        draft = client.complete(prompt, system=DRAFT_SYSTEM, max_tokens=1600)
        allowed = numbers_in_artefacts(artefacts)
        rogue = {n for n in numbers_in(draft) if n not in allowed}
        if rogue:
            log("llm_draft_rejected", rogue_numbers=sorted(rogue)[:10])
            return deterministic_text, False
        log("llm_draft_verified", model=client.model, n_numbers=len(numbers_in(draft)))
        return draft, True
    except Exception as e:  # noqa: BLE001
        log("llm_draft_failed", error=str(e)[:200])
        return deterministic_text, False


# ---------- ASK phrasing layer ----------

ASK_SYSTEM = (
    "You are the analyst inside the Herding Scenario Lab supervisory terminal. Answer ONLY "
    "from the context supplied; cite sources like [S1]. Be concise and quantitative. If the "
    "context lacks the answer, say so and suggest what to run or check. Never invent numbers. "
    "British spelling. No em dashes. Outputs are comparative rankings on synthetic scenarios, "
    "never forecasts, and the named supervisor decides.")


def ask_llm(question, sources, deterministic_text, client, log):
    """Phrase an answer from the retrieved sources and the deterministic
    answer. The client only ever supplied the question."""
    if not client.available:
        return None
    q = question[:MAX_QUESTION_CHARS]
    ctx = "\n".join(f"[S{i + 1}] {c['title']}: {c['text']}" for i, c in enumerate(sources))
    prompt = (f"CONTEXT:\n{ctx}\n\nDETERMINISTIC ANSWER (computed from the artefacts):\n"
              f"{deterministic_text}\n\nQUESTION: {q}")
    try:
        text = client.complete(prompt, system=ASK_SYSTEM, max_tokens=700)
        log("ask_llm", model=client.model, sources=[c["id"] for c in sources],
            n_chars=len(text))
        return text
    except Exception as e:  # noqa: BLE001
        log("ask_llm_failed", error=str(e)[:200])
        return None
