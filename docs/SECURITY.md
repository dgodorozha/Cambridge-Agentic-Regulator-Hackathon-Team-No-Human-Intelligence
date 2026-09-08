# Security notes and threat model

## Assets

The supervisory record (ledgers, artefacts, briefings), the integrity of
the numbers a supervisor relies on, the identities recorded at the gates,
and the model API key if one is configured.

## Trust boundaries

- The reverse proxy is trusted to authenticate users and to set the
  identity header truthfully; HSL never accepts a typed identity in header
  mode. Requests that change state (`/_dash-update-component`, `/ask`)
  without the header are refused with 401.
- The browser is untrusted. It sends questions and button clicks only. The
  grounding prompt, retrieval and the deterministic answer are server side;
  the client cannot supply messages to the model.
- The file system under `runs/` is trusted for availability, not for
  integrity: every ledger is hash chained and HMAC signed, and every
  evidence pack carries a manifest of SHA-256 hashes.

## Controls

| Threat | Control |
|---|---|
| Tampering with the record | append only ledger; SHA-256 chain; HMAC signature under `HSL_SECRET`; `verify` tool; critic replays the chain before Gate 2 |
| Swapping the battery after sign off | Gate 1 approves a battery hash; the critic fails the run if the executed battery differs |
| A prose surface altering a number | briefings are drafted from `artefacts.json`; the critic vets every number in the text against the artefacts; ASK answers are computed first and only phrased by a model |
| Key misuse through the relay | no client supplied prompts; question length capped; per identity rate limit; every question chained into the ledger; `HSL_LLM=off` for air gapped deployments |
| Unauthorised approval | identity from SSO header only; optional approver allow list; four eyes; refusals with reasons recorded |
| Cross site abuse | same origin CSP with `frame-ancestors 'self'`; `X-Frame-Options`; `nosniff`; no cookies are used for state |
| Path traversal | run files are served from an allow list of names inside a validated run id directory |
| Resource exhaustion | 256 KB request limit; one active run per server; rate limited ASK |
| Supply chain | pinned dependencies; vendored front end libraries with their licences |

## Version 3 controls

- The injection suite (`hsl/redteam.py`) runs on every battery and the
  critic refuses Gate 2 unless every case is contained: planner bounds and
  guardrail families, persona table validation, briefing number vetting at
  printed precision, ASK acting only on artefacts, ledger tamper detection.
- Persona policy tables are hashed at planning, written to `battery.json`
  and bound into each spec; `simulate()` refuses a table whose hash differs
  from the one approved at Gate 1, and the critic checks the binding.
- Model calls remain single shot, server side, with fixed prompts; the
  persona elicitation adds one call per persona per battery.

## Residual risks

- The development server is fine for demonstrations; use gunicorn behind
  the proxy in production (see `docs/DEPLOYMENT.md`).
- Dash requires inline scripts, so the CSP allows `'unsafe-inline'` and
  `'unsafe-eval'` for scripts from the same origin. No third party origins
  are permitted.
- The HMAC secret must be managed by the authority; an attacker with the
  secret and write access to `runs/` could forge a ledger. A future version
  can anchor ledger heads in an external timestamping service.
- If a model is enabled, the artefacts of a run are sent to the model
  provider for phrasing. Everything in them is synthetic. Keep `HSL_LLM=off`
  where that is not acceptable.
