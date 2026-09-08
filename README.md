# Herding Scenario Lab (HSL)

**Team No Human Intelligence** · C:\>DIR Global 'Agentic Regulator' Hackathon · problem space *Market Manipulation, Agentic Herding and Stability* · version 3.9, September 2026

| | |
|---|---|
| **Live prototype** | https://hsl-terminal.onrender.com |
| **Source code (GitHub)** | https://github.com/dgodorozha/Cambridge-Agentic-Regulator-Hackathon-Team-No-Human-Intelligence |
| **Interface only (Vercel)** | https://cambridge-agentic-regulator-hackath.vercel.app (serverless: the pages load, but a run does not survive across function instances; use the Render address to run a battery) |
| **Full manual** | `docs/MANUAL.md` |
| **Long form project description** | `docs/OVERVIEW.md` |
| **Referenced works** | `REFERENCES.md` |

## Running a battery: use the demonstration identities

The live prototype at https://hsl-terminal.onrender.com, and any local copy started with `HSL_DEV_MODE=on`, accept two built in identities, so no account and no register entry is needed. On the RUN page enter exactly:

| Field | Value |
|---|---|
| Prepared by | `Developer1` |
| Preparer's function | `Developer1` |
| Approver at the gates | `Developer2` |
| Approver's function | `Developer2` |

Then click **Plan**, then **Gate 1: approve battery**, wait for the battery and the critic to finish (a few minutes on the demonstration profile; the phase line under the command bar shows progress), and click **Gate 2: release briefing**, or **Refuse** with a reason. The preparer and the approver must differ (four eyes). Any other names are checked against the register of regulated persons in `sample_data/register.csv`, which also accepts the four team members listed there with their recorded functions (for example approver `Rajib Ahmed`, function `SMF24`); names not on it are refused, by design.

## 1. What the prototype does

Regulators and central banks are starting to build surveillance tools and circuit breakers for markets in which AI trading agents on shared foundation models can herd. Today those tools are validated on **aggregate fidelity**: how closely a synthetic market reproduces volatility, spreads and correlation. The supervisory decision is different: which agents are destabilising, and when to act. Our research (under review at ICAIF 2026) shows the two criteria can fully invert, so a tool certified on aggregates alone can fail at the decision it exists to inform.

HSL is a **decision first agentic sandbox** in which a public authority stress tests candidate surveillance sentinels and intervention rules against synthetic AI agent markets whose ground truth is known, because the market was generated. In one run it:

- turns a policy question into a **battery of synthetic markets** (51 markets in 18 scenario families out of the box: parametric herds of three intensities, herding learned by reinforcement learning traders, an evader, colluding ignition, an LLM persona monoculture, a faulty vendor model, liquidity withdrawal, misinformation, quiet and held out families), hashed and signed off by a named human at **Gate 1**;
- streams **8 surveillance sentinels** over the tape and applies **8 intervention rules** (EU, UK and US style instruments, including LULD and MiFID II venue halts), each reading only the flags as they stood at that step;
- scores every sentinel twice, by fidelity and by **decision accuracy** against the generator's truth, and reports the **decision gap** with a bootstrap probability of inversion;
- **certifies** the most accurate tool whose false alert probability on a new quiet market is bounded by a split conformal guarantee, with winner stability and a walk forward test of the certification procedure itself;
- runs the assurance stages: Shapley attribution, truth dependence audit across four generators, concentration dose response, survival analysis, off policy evaluation, and a **red team** that searches for the evasion that blinds the certified tool;
- passes **31 critic checks** that recompute every figure from the raw rows and replay the ledger before a human can release anything at **Gate 2**;
- leaves an HMAC signed, hash chained **ledger**, an **evidence pack**, a briefing with evidence grades, a transparency record in the UK ATRS structure and an exchange record.

The four guardrails the organisers require are implemented and demonstrated: human in the loop (two named gates with four eyes, approver checked against a register of regulated persons, emergency stop), auditability and traceability (signed replayable ledger, hashed battery, critic), safety and governance controls (no generated figure reaches a supervisor, autonomy gate, injection suite, role based actions) and cyber risk management (a 17 control security framework checked live, data quarantine, egress allow list).

## 2. Setup and run

### Local (any machine with Python 3.12)

```bash
pip install -r requirements.txt
export HSL_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
export HSL_ASSURANCE=demo HSL_DEV_MODE=on HSL_SEEDS=2
python3 dash_app.py            # open http://127.0.0.1:8050
```

Pure Python, one process, no accounts and no external data: charts and fonts are vendored so it runs offline. In the terminal: name a preparer (`Developer1`, function `Developer1`) and an approver (`Developer2`, function `Developer2`), which `HSL_DEV_MODE=on` accepts without a register entry; click **Plan**, approve **Gate 1**, watch the battery, and release or refuse at **Gate 2**. The demo profile runs twelve short scenarios in a few minutes with the heavy audits skipped and declared in the ledger. Leave `HSL_ASSURANCE` unset for the full certification battery (about three and a half minutes on a laptop). Every environment variable is documented at the top of `config.py`; `.env.example` lists them.

An optional language model plans the herding families, drafts briefing prose and phrases ASK answers (`ANTHROPIC_API_KEY`, or any OpenAI compatible, Azure, Gemini or local endpoint, see `config.py`). Without one every path is deterministic from the artefacts; every reported number is computed, never generated, in either case.

### Batch, without the terminal

```bash
python3 -m hsl.orchestrator --approve-battery --approve-briefing \
    --preparer "D. Godorozha" --preparer-role "certified function" \
    --approver "R. Ahmed" --approver-role "SMF24" --outdir runs/cli
python3 figures.py runs/cli    # figures from the run
```

### Docker and hosted deployments

- `Dockerfile` runs the terminal under gunicorn as one long lived process, which a run needs (the battery is a background computation polled by the page). `deploy/docker-compose.yml` adds nginx.
- `render.yaml` is a one click Render blueprint: connect the repository, and Render builds the image, generates `HSL_SECRET` and redeploys on every push. This is how the live prototype above is hosted (Standard instance).
- `vercel.json` with `api/index.py` deploys the same Flask server to Vercel serverless. The interface works there, but a run lives in one function instance and is lost on a cold start, so Vercel is for showing the pages, not for certifying a tool.

`DEPLOY.md` and `docs/DEPLOYMENT.md` cover each option.

### Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q tests     # 98 tests, about two minutes
```

`test_terminal.py` drives the whole workflow through a headless browser (boots the server, refuses a gate, fires the emergency stop, runs the battery, releases, replays the ledger). `docs/VALIDATION.md` records what has been verified.

## 3. Architecture overview

A supervised multi agent system, hierarchical planner and workers with an independent critic, and a human in command at both irreversible points. Agents communicate through a shared typed state and append every step to the ledger.

| Component | Where | What it does |
|---|---|---|
| Planner | `hsl/orchestrator.py`, `hsl/pipeline.py` | Turns the policy question into a scenario battery, hashes it and chains every step into the signed ledger; with a model configured the herding families are model planned within hard bounds, while quiet, adversarial, emergent and held out families are fixed so guardrail scenarios cannot be planned away |
| Market simulator and agents | `hsl/simulator.py`, `hsl/agents.py`, `hsl/families.py` | Synthetic order flow, prices and exposure networks from noise traders, fundamentalists, vendor clusters, manipulators and authority defined templates under five generators; the truth is a property of how the market was made |
| RL trader population | `hsl/rl_agents.py` | Double Q learning, SARSA(λ) and advantage actor critic traders trained independently; herding is learned, not scripted |
| LLM persona traders | `hsl/personas.py` | A persona's policy table distilled from a model once at planning time, hashed and bound into the battery |
| Sentinels under test | `hsl/sentinels.py`, `hsl/herding.py` | Volatility trigger, buy sell imbalance, Hawkes endogeneity, absorption ratio, correlation clustering, network community, lead lag ignition and tail dependence, each exposing only the flags it had issued at every step |
| Intervention rules | `hsl/rules.py` | Market wide breaker, LULD band, dynamic throttle, venue halt, responsive ladder, kill switch, MWCB levels and a learned policy (advisory only), scored on containment, false halts, hazard ratio and expected shortfall |
| Evaluator | `hsl/evaluate.py`, `hsl/autonomy.py` | Decision accuracy against the generator's truth, fidelity, bootstrap intervals, the decision gap and its resampling distribution, autonomy gates |
| Assurance | `hsl/conformal.py`, `hsl/frontier.py`, `hsl/attribution.py`, `hsl/audit.py`, `hsl/redteam.py`, `hsl/games.py`, `hsl/survival.py`, `hsl/rl_supervisor.py` | Conformal false alert guarantee, cost frontier, Shapley attribution, truth dependence audit, dose response, red team, matrix game, survival analysis, model based RL with off policy evaluation |
| Critic | `hsl/critic.py` | 31 independent checks: recomputation from rows, the battery hash approved at Gate 1, ledger replay, conformal arithmetic, the injection suite, and every number in the briefing at its printed precision |
| Briefing drafter and ASK | `hsl/briefing.py`, `hsl/ask.py`, `hsl/atrs.py`, `hsl/reports.py` | Reads only the artefacts; a model may rephrase and the critic re verifies; transparency record in the ATRS structure, exchange record |
| Ledger and evidence | `hsl/ledger.py`, `hsl/evidence.py`, `runstore.py` | HMAC signed, hash chained ledger with a replay CLI; evidence pack with manifest |
| Data, calibration, security | `hsl/ingest.py`, `hsl/connectors.py`, `hsl/calibrate.py`, `hsl/backtest.py`, `hsl/security.py`, `hsl/register.py` | Observed data through a quarantine, connectors behind an egress allow list, calibration of the simulator to the authority's data, backtests, the 17 control security framework, the register of regulated persons |
| Terminal and gates | `dash_app.py`, `assets/` | Multi panel terminal (Dash and Flask), named identities, four eyes, approval or refusal with reasons, emergency stop, live tape, network and casefile views |

Repository layout: `hsl/` (the package), `dash_app.py` (the terminal), `assets/` (front end, vendored libraries and fonts, with a SHA-256 manifest), `sample_data/` (synthetic flows, templates, a synthetic register), `sample_outputs/` (a complete run: artefacts, ledger, briefing, transparency record, figures), `tests/`, `docs/`, `deploy/`.

## 4. Third party components and licences

All third party code is either installed from PyPI at build time or vendored under `assets/` with its licence file beside it (`assets/MANIFEST.sha256` records the hash of every vendored asset and is checked at start up). Nothing is fetched at run time.

| Component | Version | Use | Licence |
|---|---|---|---|
| NumPy | 2.4.4 | numerical core | BSD-3-Clause |
| SciPy | 1.17.1 | statistics, optimisation, linear algebra | BSD-3-Clause |
| NetworkX | 3.6.1 | exposure and correlation networks, community detection | BSD-3-Clause |
| Dash | 4.4.1 | terminal application framework | MIT |
| Flask | 3.1.3 | HTTP server underneath Dash | BSD-3-Clause |
| Matplotlib | 3.10.8 | figures in the evidence pack | Matplotlib licence (PSF based, BSD compatible) |
| gunicorn | 23.0.0 | production process manager (container only) | MIT |
| pytest, Playwright | dev only | unit and end to end tests | MIT, Apache-2.0 |
| Apache ECharts | 5.6.0 | correlation network view (`assets/echarts.min.js`) | Apache-2.0 |
| TradingView Lightweight Charts | 5.2.1 | live market tape (`assets/vendor/`) | Apache-2.0 (`assets/vendor/lightweight-charts.LICENSE`) |
| FINOS Perspective | viewer, datagrid and d3fc plugins with WebAssembly engine | casefile pivot (`assets/psp/`, `assets/wasm/`) | Apache-2.0 |
| IBM Plex Sans | | interface typeface (`assets/fonts/`) | SIL Open Font License 1.1 (`assets/fonts/IBMPlexSans.LICENSE`) |
| JetBrains Mono | | monospace typeface (`assets/fonts/`) | SIL Open Font License 1.1 (`assets/fonts/JetBrainsMono.LICENSE`) |
| Bedstead | | terminal display typeface (`assets/fonts/`) | CC0-1.0 (`assets/fonts/bedstead.LICENSE`) |

Optional model providers (Anthropic, OpenAI compatible endpoints, Azure OpenAI, Gemini, or a locally installed model) are not bundled, are off by default, and are used under their own terms only when the operator supplies a key. Regulatory texts referenced for grounding are cited in `REFERENCES.md`. All data shipped with the repository is synthetic; the register in `sample_data/register.csv` contains no real persons.

## 5. Team

Daria Godorozha (LSE, team lead), Prithika Narayanan (LSE, Impact Advantage), Sara Gabrielli Salis (LSE), Rajib Ahmed (Department for Business, Innovation, Science and Trade; Cardiff University; LSE).

## 6. Licence

The HSL code (everything in this repository other than the third party components listed in section 4) is made available under an **Evaluation Licence**, all rights reserved: the organisers, judges and voters of the C:\>DIR hackathon may view, run and test it to evaluate the submission, and no other right is granted. Copying, redistribution, modification and commercial use require the written consent of the copyright holders. The full text is in `LICENSE`. The third party components remain under their own licences as listed in section 4. Copyright 2026 Team No Human Intelligence.
