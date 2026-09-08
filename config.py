"""Server configuration, read once from the environment.

Every setting has a safe default: the server binds to localhost, every
ledger is signed (with an ephemeral secret and a loud warning if none is
configured), approvals are open to any named person in demo mode and
restricted to an allow list behind single sign on in production mode.

  HSL_HOST          bind address (default 127.0.0.1; use 0.0.0.0 only behind a proxy)
  HSL_PORT          port (default 8050)
  HSL_RUNS_DIR      directory for run folders (default ./runs)
  HSL_SECRET        HMAC key for ledger signatures (set this in production)
  HSL_AUTH_MODE     open | header  (header: identity comes from a trusted proxy header)
  HSL_USER_HEADER   header carrying the SSO identity (default X-Remote-User)
  HSL_APPROVERS     comma separated identities allowed to approve gates (empty = any)
  HSL_FOUR_EYES     1/0: approver must differ from preparer (default 1)
  HSL_LLM_PROVIDER  off | anthropic | openai | azure | gemini | custom | local
                    (default: anthropic if ANTHROPIC_API_KEY is set, else off)
  HSL_LLM           auto | off: allow outbound model calls when a key is set (default auto)
  ANTHROPIC_API_KEY optional; enables model planned batteries, prose and ASK phrasing (anthropic)
  HSL_MODEL         Anthropic model name (default claude-sonnet-4-6)
  HSL_LLM_BASE      OpenAI compatible base URL ending in /v1 (an institutional gateway or a local server)
  HSL_LLM_MODEL     model name at that endpoint
  HSL_LLM_KEY       bearer token for that endpoint (optional for local servers)
  HSL_LLM_PATH      directory holding a model the authority installed itself (provider local)
  HSL_LLM_API_VERSION  Azure OpenAI API version (default 2024-10-21); HSL_LLM_AUTH=bearer for a token instead of a key
  HSL_LLM_TEMPLATE  custom provider: JSON request body with {prompt} {system} {model} {max_tokens} placeholders
  HSL_LLM_HEADERS   custom provider: JSON object of headers; ${HSL_LLM_KEY} is substituted
  HSL_LLM_RESPONSE_PATH  custom provider: dotted path of the reply text, for example choices.0.message.content
  HSL_TICK_PACE     seconds per simulated step on the tape (default 0.0008)
  HSL_ASK_RATE      ASK questions per identity per minute (default 20)
  HSL_ASSURANCE     full | light | demo: budgets of the assurance stages (default full; demo is a three minute
                    battery of twelve short scenarios with the heavy audits skipped and declared in the provenance)
  HSL_CONNECTORS    on | off: outbound data connectors (default off, the sandbox is air gapped)
  HSL_EGRESS_ALLOWLIST  comma separated hosts a connector may call (empty by default)
  HSL_DEV_MODE      on: the identities Developer1 and Developer2 are accepted as preparer and approver (and as
                    their functions) without a register entry; every gate records dev mode; never for production
  HSL_REGISTER      path to the register of regulated persons (CSV or JSON) approvers are checked against
  HSL_REGISTER_REQUIRED  on: an approver not on the register cannot approve (default: on when a register is set)
  HSL_UPLOAD_MAX_MB size limit for uploaded datasets (default 25)
  HSL_ROLE_HEADER   header carrying the caller's role in header auth mode (default X-HSL-Role)
  HSL_SEEDS         seeds per herding family in the planned battery (default 3; 2 for a short demo)
"""

import os
import secrets
import warnings


def _bool(v, default):
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.host = env.get("HSL_HOST", "127.0.0.1")
        self.port = int(env.get("HSL_PORT", "8050"))
        self.runs_dir = env.get("HSL_RUNS_DIR", "runs")
        self.secret = env.get("HSL_SECRET") or None
        self.ephemeral_secret = self.secret is None
        if self.ephemeral_secret:
            self.secret = secrets.token_hex(32)
            warnings.warn("HSL_SECRET is not set: ledgers are signed with an ephemeral key "
                          "that will not survive a restart. Set HSL_SECRET in production.")
        self.auth_mode = env.get("HSL_AUTH_MODE", "open").strip().lower()
        if self.auth_mode not in ("open", "header"):
            raise ValueError("HSL_AUTH_MODE must be 'open' or 'header'")
        self.user_header = env.get("HSL_USER_HEADER", "X-Remote-User")
        self.approvers = {x.strip().lower() for x in env.get("HSL_APPROVERS", "").split(",")
                          if x.strip()}
        self.four_eyes = _bool(env.get("HSL_FOUR_EYES"), True)
        self.llm_mode = env.get("HSL_LLM", "auto").strip().lower()
        self.api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        self.model = env.get("HSL_MODEL", "claude-sonnet-4-6")
        self.llm_provider = env.get("HSL_LLM_PROVIDER", "").strip().lower() or ("anthropic" if self.api_key else "off")
        if self.llm_provider not in ("off", "anthropic", "openai", "azure", "gemini", "custom", "local"):
            raise ValueError("HSL_LLM_PROVIDER must be off, anthropic, openai, azure, gemini, custom or local")
        self.llm_base = env.get("HSL_LLM_BASE", "").strip()
        self.llm_model = env.get("HSL_LLM_MODEL", "").strip()
        self.llm_path = env.get("HSL_LLM_PATH", "").strip()
        self.tick_pace = float(env.get("HSL_TICK_PACE", "0.0008"))
        self.ask_rate = int(env.get("HSL_ASK_RATE", "20"))
        self.assurance = env.get("HSL_ASSURANCE", "full").strip().lower()
        if self.assurance not in ("full", "light", "demo"):
            raise ValueError("HSL_ASSURANCE must be 'full' or 'light'")
        self.seeds = int(env.get("HSL_SEEDS", "3"))
        self.connectors = env.get("HSL_CONNECTORS", "off").strip().lower() in ("on", "1", "true", "yes")
        self.egress_allowlist = [h.strip() for h in env.get("HSL_EGRESS_ALLOWLIST", "").split(",") if h.strip()]
        self.upload_max_mb = int(env.get("HSL_UPLOAD_MAX_MB", "25"))
        self.role_header = env.get("HSL_ROLE_HEADER", "X-HSL-Role")
        self.register_path = env.get("HSL_REGISTER", "").strip()
        self.dev_mode = env.get("HSL_DEV_MODE", "").strip().lower() in ("on", "1", "true", "yes")
        self.register_required = env.get("HSL_REGISTER_REQUIRED", "").strip().lower() in ("on", "1", "true", "yes")
        if self.connectors and not self.egress_allowlist:
            warnings.warn("HSL_CONNECTORS is on with an empty HSL_EGRESS_ALLOWLIST: every outbound call will be "
                          "refused until hosts are named.")

    @property
    def assurance_budget(self):
        """Budgets passed to run_battery for the version 3 stages."""
        if self.assurance == "light":
            return {"truth_families": ["herd_high", "herd_mid", "evader"], "truth_n_quiet": 3,
                    "redteam_budget": 6, "dose_seeds": (0,)}
        if self.assurance == "demo":
            return {"redteam_budget": 3, "skip_attribution": True, "skip_truth": True, "skip_dose": True,
                    "skip_learned": True}
        return None

    @property
    def llm_enabled(self):
        if self.llm_mode in ("off", "0", "false", "no"):
            return False
        if self.llm_provider == "anthropic":
            return bool(self.api_key)
        if self.llm_provider == "openai":
            return bool(self.llm_base and self.llm_model)
        if self.llm_provider == "azure":
            return bool(self.llm_base and self.llm_model and os.environ.get("HSL_LLM_KEY"))
        if self.llm_provider == "gemini":
            return bool(self.llm_model and os.environ.get("HSL_LLM_KEY"))
        if self.llm_provider == "custom":
            return bool(self.llm_base and os.environ.get("HSL_LLM_TEMPLATE") and os.environ.get("HSL_LLM_RESPONSE_PATH"))
        if self.llm_provider == "local":
            return bool(self.llm_path)
        return False

    def public(self):
        """Non secret view for /version and the front page."""
        return {"host": self.host, "port": self.port, "runs_dir": self.runs_dir,
                "auth_mode": self.auth_mode, "user_header": self.user_header,
                "approvers_restricted": bool(self.approvers), "four_eyes": self.four_eyes,
                "llm_enabled": self.llm_enabled, "llm_provider": self.llm_provider if self.llm_enabled else "off",
                "model": ({"anthropic": self.model, "openai": self.llm_model, "azure": self.llm_model,
                           "gemini": self.llm_model, "custom": self.llm_model or "custom", "local": self.llm_path}
                          .get(self.llm_provider) if self.llm_enabled else None),
                "assurance": self.assurance, "seeds_per_family": self.seeds,
                "connectors": self.connectors, "egress_allowlist": self.egress_allowlist,
                "ledger_secret": "configured" if not self.ephemeral_secret else "ephemeral"}
