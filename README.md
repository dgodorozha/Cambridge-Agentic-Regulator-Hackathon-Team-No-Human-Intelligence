# Herding Scenario Lab (HSL) v3

**Herding versus noise, decided before certification.** HSL is a decision
first agentic sandbox in which a public authority stress tests candidate
surveillance sentinels and intervention rules against synthetic AI agent
markets, and measures the **decision gap**: the divergence between the
ranking of tools by conventional aggregate fidelity and the ranking by
decision accuracy. Version 2 made it a build an authority can run: a
signed, replayable ledger and an evidence pack for every run, an interval
and an evidence grade on every headline number, named gates that can refuse
as well as approve, an emergency stop one click away. Version 3 makes the
certification defensible: seven sentinels including three that separate a
herd from noise, a false alert guarantee with a finite sample proof, a
counterfactual ground truth, an audit of whether the ranking survives a
change of market generator, a cost frontier the supervisor owns, a rule
library across jurisdictions, LLM persona traders and a colluding
manipulator family, and a red team that attacks both the certified tool and
the pipeline. `REFERENCES.md` lists every work the build draws on.

Team **No Human Intelligence** · C:\>DIR Global 'Agentic Regulator'
Hackathon · problem space: *Market Manipulation, Agentic Herding and
Stability*. Built by researchers in regulatory data infrastructure and LLM
systems (LSE statistics; ETH Zürich secure LLM infrastructure; Swansea/SAIL
national record linkage; previously Bank of England).

The full manual, every feature and every quantity measured, is `docs/MANUAL.md`.

## Run it in sixty seconds

```
pip install -r requirements.txt
export HSL_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))")
python dash_app.py            # open http://127.0.0.1:8050
```

Pure Python, one process, no accounts, no external data; charts and fonts
are vendored so it runs offline. `export ANTHROPIC_API_KEY=…` if you want a
model to plan the herding families, draft the briefing prose and phrase ASK
answers; without a key every path runs deterministically from the artefacts.
To have a robot judge drive the whole workflow (boots the server, refuses a
gate, fires the emergency stop, runs the battery, releases, replays the
ledger): `pip install -r requirements-dev.txt && playwright install chromium
&& python test_terminal.py`. Unit tests: see below.

Unit tests: `python -m pytest -q tests` (97 tests, about two minutes).

Batch, without the terminal:

```
python -m hsl.orchestrator --approve-battery --approve-briefing \
    --preparer "D. Godorozha" --preparer-role "certified function" \
    --approver "R. Ahmed" --approver-role "SMF24" --outdir runs/cli
python figures.py runs/cli            # paper figures from the run
```

A full run takes about three and a half minutes (the assurance stages are
half of it). `HSL_ASSURANCE=light` and `HSL_SEEDS=2` give a shorter demonstration
run with the same structure. `HSL_ASSURANCE=demo` gives the three minute demonstration profile: twelve short scenarios, about twenty seconds a run, the heavy audits skipped and declared in the ledger, never a certification battery (`docs/demo/` has the storyboard and the recording driver).

## The challenge: herding versus noise

AI trading agents built on shared foundation models can herd: correlated
reactions that amplify a routine shock into a dislocation. The supervisory
problem is *discrimination*: telling destabilising correlated herding from
ordinary volatility, early enough to act, and knowing **which surveillance
tool to trust** for that call. HSL's claim is that this choice is currently
made with the wrong yardstick. On the demonstration battery of the run in
`sample_outputs/` (34 scenarios, 7 sentinels, 6 rules):

- The volatility trigger scores aggregate fidelity **1.00** by construction
  (the conventional criterion is its own output) and decision F1 **0.29**,
  flagging the whole market when it fires.
- The structural sentinels score fidelity between **0.11** and **0.23** and
  decision F1 between **0.27** and **0.61**, localised to the destabilising
  cluster.
- The rankings invert: decision gap **0.76** (Kendall tau **−0.52** over
  seven tools) and, over 400 scenario resamples, a **probability of
  inversion of 0.83**. Under a multi moment fidelity construct that scores no
  tool against its own output the gap is 0.52.
- The best tool by decision accuracy (the absorption ratio, F1 0.61) exceeds
  the declared false alert budget (0.38 against 0.25), so it is **not
  certifiable**; the best tool within budget is the lead lag ignition
  sentinel (F1 0.39), and the red team then shows that six rotating cohorts
  reduce its F1 to **0.00** while the market still dislocates. That is the
  finding a supervisor needs before certifying anything.

Everything above is reproduced live in the terminal on every run and
written to `artefacts.json` with intervals; the README quotes the run, not
the other way round. Exact figures move with the calibration of the newest
sentinels; the evidence pack of the run you are looking at is the source.

## Observed data, connectors and the security framework

The `DAT` panel (or `--data` on the CLI) brings observed data to the
sandbox through one quarantine: size and type limits, text only, a schema
check, a spreadsheet formula check, a personal identifier scan that refuses
rather than redacts, and a classification with a no write down rule
(`confidential` and `personal` are refused; `licensed` and `pseudonymised`
rows never enter an evidence pack). Accepted data anchors the battery's
quiet family, adds held out empirical scenarios built from the observed
shock and volatility, and, where per participant order flow is supplied,
runs the sentinels on it with counts reported only above a query set size.
Connectors for Bloomberg, LSEG, Alpha Vantage, FRED, the ECB Data Portal
and the Bank of England database share the quarantine and sit behind an
egress allowlist; they are off by default and only the replay fixture was
exercised in this build. Two synthetic fixtures are in `sample_data/`.

The `SEC` panel and `python -m hsl.security posture` check the deployment
against the controls of `docs/SECURITY_FRAMEWORK.md`, which organises the
platform's security argument by the chapters of Anderson's *Security
Engineering*; a failing control seals Gate 2. Roles (viewer, preparer,
approver, admin) are enforced from the proxy's role header in header auth
mode. After changing anything under `assets/`, run
`python -m hsl.security manifest`.

## The question, read without a model, and your own model

The policy question is read deterministically at planning: the numbers it
states, the mechanisms it names and the tools it asks about become a
`question` family that contains the case asked about, and the briefing
opens with a direct answer for those tools, stating what it could not
interpret. That works offline. A model, when you want one, is a
complement. `HSL_LLM_PROVIDER` selects it:

| Provider | Reaches | Settings |
|---|---|---|
| `anthropic` | the Anthropic API or a gateway proxying it | `ANTHROPIC_API_KEY`, `HSL_MODEL` |
| `openai` | any OpenAI compatible endpoint: an institutional gateway, Mistral, Groq, Together, Bedrock's compatible endpoint, Azure AI Foundry inference, or a local server (vLLM, llama.cpp, Ollama, LM Studio) on the loopback interface | `HSL_LLM_BASE`, `HSL_LLM_MODEL`, `HSL_LLM_KEY` |
| `azure` | Azure OpenAI Service, the platform behind Microsoft Copilot for enterprises | resource endpoint, deployment name, key or bearer token, API version |
| `gemini` | the Google Gemini API | `HSL_LLM_MODEL`, `HSL_LLM_KEY` |
| `custom` | any JSON API you run, described by a request template, headers and a response path, with no code | `HSL_LLM_BASE`, `HSL_LLM_TEMPLATE`, `HSL_LLM_HEADERS`, `HSL_LLM_RESPONSE_PATH` |
| `local` | a model you installed yourself, loaded from a directory with `transformers` | `HSL_LLM_PATH` |

HSL never downloads a model. Remote endpoints must be https and, when an egress
allowlist is configured, on it; the security posture fails release
otherwise. Whatever the provider, the model only plans families within
hard bounds, distils personas, and phrases text that the critic vets
number by number.

## Backtests

Every run backtests three things. Stress episodes are found in accepted
data (an event column, or rolling window drawdowns above a threshold), and
every sentinel is run over them with the observed flows: detected or not,
lead before the event, alerts per 100 quiet steps, and recall on labelled
positives where an enforcement finding or post event report supplies a
`label` column. Each episode is replayed as a hybrid market (observed news,
calibrated synthetic population) with every rule applied. And the
certification procedure itself is walked forward over folds of the
battery: the tool certified on earlier folds is scored on the next, and its
regret against the best tool there is reported. A real tape says when a
tool alerted and how often, never who the destabilising participants were,
so precision on observed data is not reported and the briefing says why.

## Your own data, as calibrated markets

Observed data cannot replace the synthetic markets, because decision
accuracy needs a ground truth a real order book does not carry. It can set
the parameters of the markets that do. Every dataset accepted by the data
desk calibrates the simulator (volatility, the drawdown tail as the shock,
price impact from flows, the momentum window, the fundamentalist fraction,
the vendor split observed from a vendor column when the data carries one, otherwise inferred from communities in the flow correlation matrix) and two
families join the plan: a calibrated synthetic market with the fitted
parameters and the generator's ground truth, and a hybrid market in which
the observed return path is the news and the synthetic agents respond. The
calibration shift then says whether the certification survives the move
from the demonstration structure to yours.

## Your own agents

Beyond the built in classes, `AGT` in the terminal (or `--agent file.json`)
takes an agent template in a small declarative language with no code: order
flow is a bounded combination of named signals (momentum, mispricing, the
crowd's last flow, a vendor's shared signal, own inventory, volatility, time
since the shock), gated, lagged, capped and noised, with an optional burst.
Probe shows what the agent does in a herd market before you store it; a
stored template is referenced by name in a family, hashed into the battery
at Gate 1, checked by the critic and named in the network panel. The auto
label uses an overshoot test, so an agent that trades toward fundamental is
liquidity provision and one that pushes beyond it is herding.
`sample_data/agent_example_liquidity_provider.json` and
`family_example_mm_withdrawal.json` show the pair.

## Your own scenario families

The demonstration battery encodes the families the reports name; an
authority's question is usually more specific. `FAM` in the terminal (or
`--family file.json` on the CLI) takes a small JSON document: name, note,
seeds, generator, vendor shares and correlations, shock, population, and
any of the mechanisms the battery already knows (a faulty vendor model,
liquidity withdrawal, misinformation, colluding ignition, an LLM persona,
evader cohorts, quiet or held out). It is validated against the same hard
bounds the model planner obeys, every clamped value is reported, and the
stored family joins the next plan, enters the battery hash approved at
Gate 1 and is written to the ledger with its author and its own hash.
`sample_data/family_template.json` is the starting point;
`python -m hsl.families validate my_family.json` checks one before use.

## What the reports ask for

The FSB, IOSCO, the Bank of England and the IMF converge on a short list of
needs: close the data gaps with indicators, monitor third party
concentration and substitutability, detect herding and collusion between AI
agents, test in a segregated environment under stress, evidence circuit
breaker and kill switch policies, plan for a third party model that fails,
measure liquidity withdrawal and disinformation shocks, supervise
proportionately with a stated level of human oversight, keep auditable
records, and align indicators across borders. `hsl/reports.py` holds that
register with its sources, computes the indicators a run can supply
(IOSCO 2026 Table 7 and the FSB 2025 third party indicators), lists the
five that need firm reporting, and writes a coverage map into every run:
which need is answered with a figure, which in part, which not on this
battery. Three scenario families exist for the risks the reports name
(`vendor_fault`, `liquidity_withdrawal`, `misinformation`), every rule
carries its human oversight class, and `exchange_record.json` in the
evidence pack carries the indicators in a fixed schema for another
authority to read.

## Accountability: names, functions and a transparency record

Both functions are mandatory: the preparer's before a plan, the approver's
at each gate. For development and demonstrations, `HSL_DEV_MODE=on` accepts
`Developer1` as preparer and `Developer2` as approver, with `Developer1` and
`Developer2` as their functions, without a register entry; every gate entry,
the briefing signature and the security posture then say dev mode, and it
is never for production.

Approvers can be tied to a register of regulated persons. `HSL_REGISTER`
names a CSV or JSON file the authority keeps (its HR or governance system,
the FCA Financial Services Register, the Directory of certified persons):
name, individual reference number, firm, function, status, validity dates
and source. At each gate the approver is looked up; the record must be
active and hold an approving function, or the approval is refused with the
reason, and the match is recorded on the gate entry, in the ledger, the
briefing signatures and the transparency record. `sample_data/register.csv`
is an example; an optional refresh from the FCA Register API by reference
number sits behind the connector switch and the allowlist.

There is no register of people who run systems like this. UK accountability
attaches to named individuals through the Senior Managers and Certification
Regime at authorised firms, the Algorithmic Transparency Recording Standard
registers a public body's algorithmic tools and their accountable senior
manager, and the EU AI Act registers high risk systems (deferred to December
2027). HSL fits that shape: a named preparer and a named approver hold the
gates, each may record their SMF or certified function, every gate entry in
the ledger carries it, and at release the run writes an ATRS style
transparency record (`atrs_record.md` in the evidence pack) from the
artefacts alone, vetted by the critic and marked as a draft for the
accountable owner to complete.

## Version 3.2: methods from the coursework, applied

Each module below takes a taught method and points it at the certification
problem; the references are in `REFERENCES.md`.

- **Tail risk, not mean risk** (quantitative risk management). Value at
  risk, expected shortfall and a generalised Pareto tail of the post shock
  drawdown; every rule's ES reduction with an interval; a tail dependence
  sentinel that finds the agents that sell together when selling is extreme.
- **Time to dislocation** (survival analysis). Kaplan Meier curves per arm,
  a Cox model with hazard ratios per rule against the untreated market, pre
  emption probability per sentinel. A rule that delays a dislocation is
  told apart from one that prevents it.
- **A learned policy and off policy evaluation** (reinforcement learning).
  A model based market wide policy under declared halt and throttle costs,
  scored as a rule; and the pilot's question answered in the sandbox: how
  far an offline estimate of a rule's value (importance sampling, doubly
  robust, model based) sits from the simulated truth.
- **The certification as a game** (AI in games). Sentinels against the red
  team's evasions as a matrix game: the maximin sentinel and what
  randomising the armed sentinel would guarantee.
- **Herding as consensus** (AI reasoning). A voter model generator joins
  the truth dependence audit.
- **Options appraisal and the enforcement ladder** (regulation, strategy
  and enforcement). Instrument type, proportionality, false halt budget,
  legal basis and a responsive regulation recommendation of the lowest
  tier that works.

## Version 3: what is new

**Herding versus noise sentinels** (`hsl/herding.py`). Three candidates from
the empirical literature ask whether activity is coordinated and self
reinforcing rather than merely loud: the buy sell imbalance herding measure
of Lakonishok, Shleifer and Vishny (share of agents on the majority side in
excess of independent decisions), the Hawkes branching ratio of Filimonov
and Sornette (share of large moves generated by earlier moves rather than by
news) and a lead lag ignition sentinel (a small cluster whose orders lead
the crowd's next orders, and the crowd that follows). Seven tools are ranked,
so Kendall tau takes many more values than it could with four.

**Colluding ignition and LLM persona families** (`hsl/simulator.py`,
`hsl/personas.py`). A colluding cluster stays quiet, fires a coordinated sell
burst across the shock to ignite the herd and then reverses (momentum
ignition, MAR Annex II); the lead lag sentinel isolates the ignitors. An LLM
persona is distilled once into a policy table over fifteen market states,
hashed and bound into the battery at Gate 1; every agent that shares it
trades from the same table plus its own execution noise, so correlation
follows from a shared model. A model builds the table when a key is set;
otherwise a documented offline surrogate is used and recorded as such.

**Alternative generators and the truth dependence audit** (`hsl/audit.py`).
Herding by imitation within a vendor cluster (after Kirman and Lux and
Marchesi) and square root price impact (after Bouchaud and others) are
alternative truths. The audit re runs a reduced battery under each and
reports whether the decision ranking survives: in the sample run the
absorption ratio holds rank one under every generator (tau 0.90 under
imitation, 0.62 under square root impact).

**Certification with a false alert guarantee** (`hsl/conformal.py`). The
quiet calibration scenarios become a conformal threshold: if a new quiet
scenario is exchangeable with them, the false alert probability is at most
the declared budget, whatever the sentinel. The battery carries eight quiet
scenarios so that the 0.25 budget is achievable exactly; held out quiet
scenarios are the empirical check of exchangeability and are reported as
such, not as a guaranteed quantity.

**Counterfactual attribution** (`hsl/attribution.py`). Shapley values of
post shock drawdown over agent groups, by silencing coalitions under common
random numbers: the "fail each bank in turn" criterion of our ICAIF paper
transported to agent groups, with the efficiency identity checked by the
critic. Each sentinel is graded on the share of its flags that land on the
highest impact group.

**Concentration dose response** (`hsl/audit.py`). The dominant vendor's
share is swept at fixed correlation; in the sample run the response is
convex (curvature 0.63) and dislocations become the more likely outcome
from a share of 0.30. This tests, inside the sandbox, the convexity
prediction of Meng and Chen (2026), the paper the problem statement cites.

**Rule library and cost frontier** (`hsl/rules.py`, `hsl/frontier.py`). Rules
stylised after the US Limit Up-Limit Down plan, the US market wide circuit
breaker and MiFID II Article 48 venue volatility interruptions join the
three version 2 rules, each with its jurisdiction and the public rule it is
modelled on. The frontier sweeps the declared weight on false alerts (or
false halts) relative to misses and reports on which interval of that weight
each tool is optimal; a choice that switches depends on a cost the
supervisor has to own.

**Red team** (`hsl/redteam.py`). A budgeted adversarial search over evasion
and market parameters finds the worst case for the certified sentinel while
the market still dislocates (adaptive stress testing in its black box form),
and an injection suite in the spirit of AgentDojo attacks the battery
planner, the persona elicitation, the briefing drafter, ASK and the ledger:
eleven cases, all contained, checked by the critic before Gate 2 arms.

**Survival analysis, tail risk, tail dependence, an enforcement ladder,
a voter model generator and a bandit adversary** (version 3.2, from the
team's course material; see `CHANGELOG.md` and `REFERENCES.md`). Time to
dislocation is analysed as a survival problem with Kaplan Meier curves per
rule and a Cox proportional hazards model; every rule reports expected
shortfall and tail containment beside mean containment; an eighth sentinel
reads tail concordance of order flows; a seventh rule escalates through an
enforcement pyramid; the truth audit compares four generators; the red team
allocates its budget by UCB1.

**Assurance panel** (`RSK` in the terminal) and seven new critic checks,
briefing sections and ASK intents surface all of the above.

## What a run produces

`runs/<run_id>/` holds, for every run, planned or not:

| File | What it is |
|---|---|
| `ledger.jsonl` | append only, hash chained, HMAC signed record of every step, gate decision, refusal, stop and release |
| `battery.json` | the exact battery with its hash, the object Gate 1 approves |
| `artefacts.json` | every computed metric with bootstrap intervals and evidence grades, plus the conformal certification, cost frontier, attribution, truth audit, dose response, red team, persona tables and rule library blocks; the single source of truth for the briefing |
| `rows.json` | per scenario, per sentinel evaluation rows (the case file) |
| `aut.json`, `net.json`, `tapes.json`, `three.json` | autonomy detail, network frames, price paths |
| `critic.json` | the checks that passed before Gate 2 armed (28 in a full run) |
| `approvals.json` | who prepared, who approved or refused what, when and why |
| `briefing.md`, `briefing.html` | the released briefing, drafted only from `artefacts.json` |
| `atrs_record.md` | algorithmic transparency record in the UK ATRS structure, generated from the run |
| `evidence_pack.zip` | all of the above with a manifest of SHA-256 hashes and a `VERIFY.md` |

Any reviewer can replay the chain (`python -m hsl.ledger verify
runs/<id>/ledger.jsonl`) and recompute the numbers from `battery.json`
(`python -m hsl.orchestrator --battery runs/<id>/battery.json …`).

## Where this sits in supervision

**Workflows:** market monitoring and horizon scanning, and authorisation,
supervision and enforcement. HSL is the acceptance test a surveillance model
passes *before* it is certified for monitoring or its alerts are allowed to
trigger enforcement steps; the evidence pack is a portable battery a college
of supervisors can re run.

**Who uses it:** a surveillance or suptech analyst prepares the battery and
reads the panels; a **named senior supervisor** holds Gates 1 and 2. Under
four eyes the approver must differ from the preparer. In production the
identity comes from the authority's single sign on through a trusted proxy
header, never from a typed name.

**What it changes:** validation on aggregate fidelity and backtests is
replaced by a decision accuracy acceptance test with uncertainty, held out
and adversarial families, the cost side (false alerts, false halts, burden on
stabilising agents) beside the benefit, and a signed rationale ledger that
supports the duty to give reasons.

## The terminal

The visual layer follows the conventions of professional trading terminals
rather than of consumer dashboards: a deep cold black ground with true black
wells, panels one step up, one pixel rules and no rounded corners or
shadows; amber reserved for function codes, the command line, the gates and
the active state; one blue for every data series; green and red for state
and nothing else. Words are set in IBM Plex Sans and numbers in JetBrains
Mono with tabular figures, both vendored offline under `assets/fonts/` (SIL
Open Font Licence). A workflow rail under the command bar lights each step
(plan, Gate 1, battery, rules, assurance, critic, Gate 2, released) as the
run advances, and a function key row in the footer opens every page.
Screenshots of a released run are in `docs/screenshots/`.


One dark screen at terminal density: eight panels on a CSS grid, nothing
scrolls, everything streams. A command line drives the screen (`MKT<GO>`
maximises, `Esc` restores, digits jump, `REG` opens the registry).

| # | Code | Panel |
|---|------|-------|
| 1 | `MKT` | market tape: every simulated step of the live scenario, indexed by step, with shock and first alert markers; selector for any completed scenario; three worlds view |
| 2 | `NET` | correlation network of the live run before the shock, as it lands and in the cascade; squares are ground truth destabilising agents, amber rings the sentinel's flags, red rings the misses; click a node for its verdict, correlations and neighbours; ring by class layout; frame readout with precision and recall |
| 3 | `GAP` | decision gap with bootstrap intervals, P(inversion) under both fidelity constructs, best tool within the false alert budget |
| 4 | `SEN` | sentinel telemetry with intervals, grades, held out F1 and the alert feed |
| 5 | `INT` | seven rules (circuit breaker, targeted throttle, kill switch, LULD style band, market wide breaker, venue volatility interruption, responsive enforcement ladder): post shock containment with intervals, dislocation probability, false halts, pre shock engagement, burden by class |
| 6 | `CSF` | case file: decision F1 by sentinel and family with held out and quiet columns, the per scenario rows when maximised; the interactive Perspective pivot opens from the header |
| 7 | `LDG` | rationale ledger: sequence, actor, event and hash of every entry; chain replay status |
| 8 | `RUN` | run control: identities, plan, emergency stop, Gate 1 and Gate 2 with refusal and reasons, battery table, critic verdict, released briefing, evidence links |
| 9 | `ASK` | run oracle: answers computed server side from the artefacts, with sources; a model only phrases them |
| 0 | `AUT` | autonomy gate: backed execution in sample and leave one out |
| K | `RSK` | assurance: conformal guarantee, cost frontier, Shapley attribution, truth audit, dose response, red team |
| D | `DAT` | data desk: upload or fetch observed data through quarantine; anchoring and observed window |
| F | `FAM` | scenario library: families the authority defines, validated and stored with provenance, in the next plan |
| A | `AGT` | agent workshop: agent templates in a declarative language, probed, stored with provenance, referenced by families |
| S | `SEC` | security posture: the deployment checked against the framework's controls |
| R | `REG` | run registry: every past run, its stage, approver, gap and files |

## Architecture: where the agentic AI is

A supervised multi agent system with a human in command at both irreversible
points:

- **Planner** (`hsl/orchestrator.py`, `hsl/pipeline.py`) turns the policy
  question into a scenario battery, hashes it, and chains every step into the
  signed ledger. With a model configured the herding families are model
  planned within hard bounds; the quiet, adversarial, emergent and held out
  families are fixed so guardrail scenarios cannot be planned away.
- **RL trader population** (`hsl/rl_agents.py`): Double Q learning, SARSA(λ)
  with linear function approximation and advantage actor critic, trained
  independently on a shared objective. Herding is emergent, not scripted.
- **LLM persona traders** (`hsl/personas.py`): a persona's policy table is
  distilled from a model once at planning time, hashed and bound into the
  battery; agents sharing it are correlated because they share a model.
- **Sentinels under test** (`hsl/sentinels.py`, `hsl/herding.py`), observing
  only prices and flows, each exposing the flags it had issued at every step
  so that no rule can act on hindsight.
- **Evaluator** (`hsl/evaluate.py`, `hsl/autonomy.py`): decision accuracy,
  two fidelity constructs, bootstrap intervals, the gap and its resampling
  distribution, containment on post shock drawdown, dislocation probability,
  burden by class, autonomy gates with leave one out validation.
- **Assurance** (`hsl/conformal.py`, `hsl/frontier.py`, `hsl/attribution.py`,
  `hsl/audit.py`, `hsl/redteam.py`): the false alert guarantee, the cost
  frontier, Shapley attribution, the truth dependence audit, the dose
  response and the red team, run after the rules and streamed to `RSK`.
- **Critic** (`hsl/critic.py`): twenty one independent checks, including
  recomputation from rows, the battery hash approved at Gate 1, ledger
  replay, the Shapley efficiency identity, the conformal arithmetic, the
  injection suite and vetting of every number in the briefing at its
  printed precision.
- **Briefing drafter** (`hsl/briefing.py`) may only read `artefacts.json`;
  a model may rephrase, and the critic re verifies its numbers.
- **ASK** (`hsl/ask.py`): deterministic answers from the artefacts; a model,
  when configured, phrases them under a fixed server side prompt.
- **Human gates and stop** (`dash_app.py`): named identities, four eyes,
  approval or refusal with reasons, emergency stop, all chained.

## Risks and guardrails

| Risk | Guardrail in this build |
|---|---|
| Goodharted validation | the decision gap is the headline; two fidelity constructs; bootstrap P(inversion); held out and adversarial families |
| Automation bias | two named human gates with refusal; four eyes; nothing simulates before Gate 1, nothing releases before Gate 2; emergency stop |
| Over delegation of execution | autonomy gate with withdrawal when localisation fails the bar; leave one out claim rates quoted, not in sample breadth |
| Unaccountable reasoning | signed, append only ledger with replay tool; critic before release; evidence pack with manifest |
| Interventions that hurt healthy markets | false halt rate on quiet markets, pre shock engagement and burden on stabilising agents reported beside containment |
| Model hallucination | prose and ASK are computed first; a model only phrases; every number vetted against the artefacts; no client supplied prompts |
| Sim to real overreach | synthetic only; comparative rankings with intervals, never forecasts; provenance recorded |
| Certification that only holds under one generator | truth dependence audit under imitation herding and square root impact; the briefing says whether rank one survives |
| A false alert budget that is only an estimate | conformal threshold with a finite sample guarantee at the budget; held out quiet scenarios reported as the exchangeability check |
| A certified tool an adversary can evade | budgeted adversarial search for the worst case that still dislocates; robustness margin in the briefing |
| Prompt injection through the model facing surfaces | eleven case injection suite against planner, persona elicitation, drafter, ASK and ledger; the critic requires every case contained |
| A generative ground truth nobody trusts | Shapley attribution by counterfactual silencing as the behavioural ground truth; sentinels graded on it |
| A ranking that hides a cost judgement | cost frontier over the declared weight on false alerts and false halts |

## Honest limitations

Synthetic markets stylise real microstructure, and the jurisdiction rules
are stylised after public mechanisms with durations in simulation steps, not
calibrated to any venue. The conformal guarantee covers exchangeable quiet
scenarios, not a different population. Offline persona tables are documented
synthetic surrogates, not claims about any real model. All outputs are
comparative rankings of tools and rules on the battery run. Sentinel and rule thresholds
are calibrated on the demonstration families; the held out and adversarial
rows show where that calibration does not carry, and the briefing says so.
The targeted rules use flags observed on the untreated path (no lookahead in
time, but the sentinel does not re observe the treated market). A single
active run per server is by design; viewers are unlimited.

See `REVIEW.md` for the audit of the hackathon build, `CHANGELOG.md` for
every change, and `docs/` for deployment, security and validation notes.
