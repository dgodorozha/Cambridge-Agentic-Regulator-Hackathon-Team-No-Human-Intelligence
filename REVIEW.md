# Review of the hackathon build (HSL_terminal (5).zip)

Method: every source file was read; the three PDFs (problem statement,
concept note, ICAIF submission) were read for the promises the build has to
keep; the batch pipeline was run and its numbers reproduced; the ledger was
verified with an independent script; the terminal was driven end to end in
headless Chromium and screenshotted at every stage. Each finding names the
fix in version 2 (see `CHANGELOG.md` for the diff level detail).

## What worked

The pipeline ran, reproduced every README number (gap 1.00, tau −1.00,
containment 0.17 and 0.11, RL convergence 0.74) and the hash chain verified.
The UI booted, streamed, gated and released without console errors. The
core simulator is sound and its dynamics are preserved unchanged in v2 (the
regression test `test_v1_dynamics_preserved` pins the v1 drawdowns).

## Findings

### A. Scientific credibility

| # | Finding | Severity | Fix |
|---|---|---|---|
| A1 | Aggregate fidelity was defined as correlation with rolling volatility, which is exactly the naive threshold's own stress index. Its 1.00 and part of the inversion were baked in by construction. | High | Both constructs are now declared and reported: the conventional one (kept, and labelled as identical to the trigger's output) and a multi moment construct that scores no tool against its own output. The gap is computed under each. |
| A2 | Kendall tau on three tools can take four values; "tau −1.00" was one outcome in four presented as a striking result. No uncertainty on any metric (3 seeds per family, 4 quiet scenarios, means only). | High | A fourth sentinel; bootstrap intervals over scenarios on every headline mean; a bootstrap distribution of the gap giving P(inversion) and P(full inversion); evidence grades A, B, C on each figure. |
| A3 | Autonomy gate thresholds were fitted on the same battery that scored them; "zero claims" held by construction. | High | Leave one out validation: each scenario is classified by gates refitted without it; the out of sample claim rate is reported and the briefing says it is the figure to quote. |
| A4 | The dynamic throttle used sentinel flags computed on the full path, including post shock data (lookahead). | High | Sentinels expose the flags they had issued at every step (`flags_online`); rules consume that matrix; the critic fails any targeted rule that used lookahead. |
| A5 | Containment used whole path drawdown; the herd market swings about 12% before the shock, so drawdown conflated endogenous instability with shock amplification. | Medium | Post shock drawdown and trough depth are the containment bases; pre shock volatility and pre shock engagement are reported; the three worlds view states which part of the herd's instability is endogenous. |
| A6 | "Lead time 240 steps" was presented as early warning; it is detection of a cluster present from t=0. | Medium | Relabelled and explained in the briefing and ASK as structural detection latency, not a forecast. |
| A7 | Concept note promises not delivered: uncertainty, held out families, adversarial evaders, false halts by participant class, crash probability reduction, emergency stop. | Medium | All delivered: held out family with a different population, shock time and impact; evader family with rotating cohorts; burden by class and by ground truth; dislocation probability before and after; emergency stop with ledger entry. |
| A8 | The decision F1 does not penalise a tool that fires on every quiet market; a tool could top the decision ranking while being useless in practice. | Medium | Declared false alert budget (0.25); each sentinel carries a within budget flag; the headline and the certification answer are conditional on it. |

### B. Security and production readiness

| # | Finding | Severity | Fix |
|---|---|---|---|
| B1 | `/ask_llm` relayed arbitrary client supplied `messages` to Anthropic with the server's key; the grounding prompt lived in browser JavaScript, so the "never invent numbers" guarantee was bypassable with curl. | High | The client sends a question only; retrieval, the deterministic answer and the fixed prompt are server side; the endpoint is rate limited, requires the identity header in production and logs every question to the ledger. |
| B2 | No authentication; the approver was a free text field; one person planned and approved both gates. | High | Header mode takes identity from a trusted proxy header (SSO) and ignores typed names; optional approver allow list; four eyes on by default; refusals with reasons recorded. |
| B3 | Single global mutable state with no run isolation; bound to 0.0.0.0 on the development server. | High | Per run directories and registry; localhost by default; single active run by design with unlimited viewers; deployment notes describe the proxy and process manager. |
| B4 | `RationaleLog.__init__` truncated the ledger file, so an "append only" trail was wiped on every restart; 64 bit truncated hashes; no signature. | High | Append only ledger that continues an existing chain; full SHA-256; HMAC signature under `HSL_SECRET`; `python -m hsl.ledger verify` replay tool; per run files. |
| B5 | No security headers, no request size limit, unpinned dependencies, no health endpoint, no Dockerfile, no version or code hash recorded in outputs. | Medium | CSP and related headers; 256 KB request limit; pinned requirements; `/healthz` and `/version`; Dockerfile and compose with a proxy example; code fingerprint and library versions in every artefact. |

### C. Bugs

| # | Finding | Fix |
|---|---|---|
| C1 | Re planning after a run left the previous run's gate approvals, critic verdict and briefing on screen against the new battery. | State is reset per run; approvals belong to a run directory. |
| C2 | Gate callbacks recorded the approver captured at plan time, not the name in the field when the gate was clicked. | Identity is read at the moment of the action. |
| C3 | `_ask_context` read `n_rl` (attribute is `rl_n`), so RL scenarios always reported zero RL agents; it also crashed when `false_halt_rate` was None. | Rewritten server side ASK with typed snapshot. |
| C4 | The NET panel showed a canned `network_data.json`, never the live run. | Frames are computed from the first herding scenario of the live run and streamed. |
| C5 | The tape concatenated all scenarios into one pseudo market with fabricated calendar dates. | One scenario at a time, indexed by simulation step, with a selector for completed scenarios and markers for the shock and each sentinel's first alert. |
| C6 | Offline ASK returned glossary fragments for the headline question. | Deterministic intent answers computed from the artefacts. |
| C7 | The three worlds chart was created in a hidden container and did not fit. | Fitted on display. |
| C8 | Labels at 8.5 to 9 px failed accessibility minimums. | 12 px body, 11 px tables, 10 px captions; sentence case content. |
| C9 | `assets/wasm` looked unused but Perspective loads it by relative path. | Kept; documented. |

## What was not changed

The market dynamics, the RL agents, the three original sentinels and the two
original rules are unchanged, so the v1 battery reproduces its numbers. The
terminal identity (dark surface, amber accent, function codes, the Ceefax
front page) is kept because it is the product's voice; its type sizes and
labels were made legible.
