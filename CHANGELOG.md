# Changelog

## 3.9.9 (2026-09-08)

- Navigation from anywhere: the footer keys and the command box open a page from any
  other page, including from ASK, which now closes when a page is opened; letter
  shortcuts K, D, F, A, S and R for RSK, DAT, FAM, AGT, SEC and REG, alongside the digits;
  keys pressed inside the network and case file frames reach the terminal; the footer
  stays above every page; the command box releases focus after a code runs, so the next
  key press is a shortcut, not typing.
- New run: a button beside Plan and Stop that clears the terminal for a fresh run, stopping
  a run in progress first, keeping the quarantined datasets; the finished run stays in the
  registry on disk.
- Deployment: `api/index.py` and `vercel.json` expose the terminal to Vercel from a GitHub
  repository (interface and short demonstration runs; see DEPLOY.md for what serverless
  cannot promise a run); `render.yaml` for a durable Docker host; `.gitignore` and
  `.vercelignore`; the Dockerfile binds the port from `HSL_PORT`.

## 3.9.8 (2026-09-08)

- Functions are mandatory: the preparer's before a plan, the approver's at
  each gate, in the terminal and on the command line (`--preparer-role`,
  `--approver-role`).
- Dev mode (`HSL_DEV_MODE=on`): `Developer1` as preparer and `Developer2` as
  approver run a scenario without a register entry, with `Developer1` and
  `Developer2` accepted as their functions (the command line defaults them).
  Every gate entry, the approvals file, the briefing signature and the
  ledger carry the dev mode mark; the security posture warns while it is
  on; it is never for production.

## 3.9.7 (2026-09-08)

- Surfaces instead of outlines. The boxes are no longer drawn with a
  hairline around each one; they sit as tiles on the darker ground, each
  named by a solid amber number key and a header band, the way a trading
  terminal separates its windows. Tables use alternating row tones rather
  than rules, the feed too; the tiles of the decision gap have no rules
  between them; the top bar, the rail, the footer and the tape's mode row
  lost their rules; the drag handles between boxes show only under the
  pointer; a maximised page is marked by an amber edge on its header.
  Form controls, chips and seals keep their borders, as controls should.
- Reports coverage evidence rounds its figures and names tools in their
  regulator facing form.

## 3.9.6 (2026-09-08)

- Resizable grid: the eight boxes sit in three flex rows, and every line
  between two boxes is a drag handle. Dragging a vertical line trades width
  between neighbours, a horizontal line trades height between rows; the
  chart and the network redraw to the new box; double clicking a handle
  restores that split and `LAYOUT` resets the grid.
- Scrolling in every box, both directions, with visible scrollbars in the
  terminal's colours. Tables keep their natural width and scroll sideways
  instead of squeezing; long free text cells wrap within a bounded width;
  feed rows never wrap.

## 3.9.5 (2026-09-07)

The three minute demonstration.

- `HSL_ASSURANCE=demo`: a battery of twelve short scenarios (the strong
  herd, the evader, the colluding ignition, the faulty vendor model, the
  persona monoculture, three quiet markets, a held out pair, the question
  family and one scenario per data driven family) at 400 steps and 100
  agents; attribution, the truth audit, the dose response and the learned
  policy skipped and declared in the ledger; the red team budget three; no
  RL population to train; a cheap fallback battery for the planner and the
  injection suite. A full run with a dataset, the register and the policy
  question completes in about twenty seconds and passes 28 critic checks.
  Never a certification battery.
- `docs/demo/`: the recording driver (frames at four a second from the real
  terminal, every cue timed), the assembler (captions burned in, an optional
  synthetic narration, the SRT and the timed script) and the storyboard.
  `sample_data/refused_pii_example.csv` is the two line file the quarantine
  refuses on camera.

## 3.9.4 (2026-09-07)

Model touchpoints verified end to end, and the planner made whole.

- The model planner now designs full family documents (structure,
  mechanisms, seeds) validated by the same bounds as the scenario library:
  clamps reported, reserved names refused, every guardrail and report
  driven family kept, and the question family added by the deterministic
  parser regardless. `llm_plan_used` in the ledger records the provider,
  the model, the accepted families with their clamps and the rejected ones.
- ASK: the direct answer to the policy question and the backtest chunk are
  reachable again ("what does the run say about my question", "what did
  the backtest show"); the answer's brain label names the configured
  provider and model.
- `tests/fake_model_server.py`: a loopback OpenAI compatible server that
  answers the planner, the persona elicitation, the briefing drafter and
  ASK. The suite drives planning, persona distillation, the draft
  (accepted, then rejected with a rogue number) and ASK through the real
  HTTP client against it; the same path was exercised through the terminal
  (plan, Gate 1, run, ASK, Gate 2) with the fake model attached. 97 tests.

## 3.9.3 (2026-09-07)

Audit pass (ruff, vulture, bandit, a profiled run, a read of every input
surface added since 3.3.1).

- Question interpreter: a bare percentage is read as a vendor share only
  when the question is about vendors, models, agents or traders; "a false
  alert budget of 25 per cent" no longer plants a 25% herd in the battery.
- Family names `question`, `backtest`, and the `calibrated_`, `hybrid_`
  and `backtest_` prefixes are reserved for the system's own families;
  the library refuses them. Family documents stored before 3.6 (no
  `custom_agents` key) load again.
- One flow matrix helper serves calibration and the backtests (the
  duplicate in `calibrate.py` removed); the dead `RULE_LABELS` constant
  removed.
- Fidelity: the realised volatility, absolute return and mean correlation
  series are computed once per scenario and shared across the eight
  sentinels and both constructs; values unchanged.
- Verified end to end: the question family and direct answer, custom
  agents and families, calibration and hybrid families, backtests and the
  register check all run through the terminal's planner and the command
  line alike; 95 tests.

## 3.9.2 (2026-09-07)

- Approvers tied to a register of regulated persons (`hsl/register.py`).
  `HSL_REGISTER` names a CSV or JSON register the authority keeps (from
  its own HR or governance system, the FCA Financial Services Register or
  the Directory): name, individual reference number, firm, function,
  status, validity dates, source. At each gate the approver is looked up
  by name or reference; the record must be active, within its dates and
  hold an approving function (SMF, certified function, PRA SMF); otherwise
  the approval is refused with the reason. The match (reference, function,
  firm, source, time of the check) is written onto the gate entry, into
  the ledger, the approvals file, the briefing signatures and the
  transparency record's senior responsible owner. A declared function that
  differs from the register's is noted and the register's is recorded.
  `--register` on the command line; `sample_data/register.csv`; an optional
  FCA Register API refresh by reference number behind the connector switch
  and the allowlist; a posture control that warns when approvers are self
  declared. `tests/test_register.py`; 95 tests in total.

## 3.9.1 (2026-09-07)

- Observed vendor split. A dataset may carry a `vendor` (or provider,
  model, platform) column per participant. When it does, the calibration
  takes the split from it: shares by actual provider and within provider
  correlations, marked "observed from the vendor column"; otherwise the
  split is inferred from flow communities and marked as such, with the
  caveat that a correlated group may be a shared model, a shared
  information source or a shared hedging need. The data desk, the
  briefing and the reports coverage (need N2) say which. The manual's
  limitation is restated: the sandbox estimates the structure present in
  supplied data and measures its consequence; market wide prevalence
  needs firm reporting.

## 3.9.0 (2026-09-07)

- `docs/MANUAL.md`: the user manual, every feature, control, family, agent
  class, sentinel, rule, metric, assurance stage, data facility,
  configuration option and file, with definitions and bounds.

Backtesting suite (`hsl/backtest.py`), honest about what a real tape can
and cannot say.

- Episodes: stress episodes found in accepted data, from an event column
  when present or from rolling window drawdowns above a threshold, with the
  event step at the largest drop; known destabilising participants attached
  from a label column (an enforcement finding or a post event report).
  Datasets may now carry `event` and `label` columns.
- Sentinel backtest: every sentinel over each episode with the observed
  flows (return based sentinels alone on a price only tape): detected or
  not, lead in steps before the event, peak stress, alerts per 100 quiet
  steps, and recall on the labelled positives where labels exist.
  Precision is not reported, because the tape does not say who the
  negatives were; the briefing says so.
- Rule backtest: each episode replayed as a hybrid market (observed news,
  calibrated synthetic population), every rule applied; containment per
  episode against the untreated hybrid run.
- Walk forward validation of the certification procedure over interleaved
  seed ordered folds of the calibration scenarios: the tool certified on
  the earlier folds scored on the next, its regret against the best tool
  there, and how often it was still the best. On the sample battery the
  mean regret is 0.13 and the certified tool is still the best on a third
  of test folds, the number that says how far one battery's answer repeats.
- Artefacts block `backtest`, a critic check on the regret identity and
  the rates, a briefing section, an assurance panel section and an ASK
  intent. `sample_data/labelled_flows.csv` shows the event and label
  columns; 92 tests in total.

## 3.8.1 (2026-09-07)

More model providers, without code changes for the authority.

- `azure`: Azure OpenAI Service, the platform behind Microsoft Copilot for
  enterprises. A deployment on the authority's own resource: endpoint,
  deployment name, key (or a bearer token with `HSL_LLM_AUTH=bearer`),
  API version.
- `gemini`: the Google Gemini API (generateContent) with a model name and a
  key; `HSL_LLM_BASE` may point at a gateway.
- `custom`: any JSON API the authority runs, described by a request body
  template with `{prompt}`, `{system}`, `{model}` and `{max_tokens}`
  placeholders, a JSON object of headers with `${HSL_LLM_KEY}` substituted,
  the endpoint URL and the dotted path of the reply text in the response.
- Mistral, Groq, Together, Bedrock's OpenAI compatible endpoint, Azure AI
  Foundry model inference and local servers are reached through the
  existing `openai` provider. The security posture checks the endpoint of
  every provider; `PROVIDERS` in `hsl/llm.py` lists them.
- `tests/test_question_models.py` (4 tests); 91 tests in total.

## 3.8.0 (2026-09-07)

Reading the question without a model, and bringing your own model.

- `hsl/question.py` (new): a deterministic interpreter of the policy
  question. It reads the numbers stated (a vendor share, a correlation, a
  shock size, a horizon in steps), the mechanisms named (a faulty vendor
  model, liquidity withdrawal, misinformation, collusion, evasion, a shared
  foundation model, imitation, voter dynamics) and the tools asked about
  (throttle, kill switch, circuit breakers, bands, venue halts, the ladder,
  the learned policy, any sentinel). From these it builds a `question`
  family that contains the case asked about, validated by the family
  bounds, and records what it matched and what it could not read. The
  briefing now opens with a direct answer for the tools named, with their
  figures across the battery and on the question's own family, and states
  the phrases it did not interpret. ASK answers "what about my question".
  The interpreter runs whether or not a model is configured; a model's plan
  complements it.
- `hsl/llm.py`: a model layer with three providers behind one interface.
  `anthropic` (the existing path), `openai` for any OpenAI compatible chat
  completions endpoint (an institutional gateway or a local server such as
  vLLM, llama.cpp, Ollama or LM Studio on the loopback interface), and
  `local` for a model the authority has installed itself and loads from a
  directory with the transformers library. HSL never downloads a model.
  Endpoint rules: https unless loopback, host on the egress allowlist when
  one is configured, responses capped, keys from the environment only.
  `HSL_LLM_PROVIDER`, `HSL_LLM_BASE`, `HSL_LLM_MODEL`, `HSL_LLM_KEY`,
  `HSL_LLM_PATH` in `config.py` and `.env.example`; provider and model in
  the provenance; a model provider control in the security posture that
  fails release on an insecure endpoint.
- `tests/test_question_models.py` (3 tests); 90 tests in total.

## 3.7.0 (2026-09-07)

Synthetic markets calibrated from the authority's own data.

- `hsl/calibrate.py` (new): every accepted dataset now calibrates the
  simulator. Volatility from the observed returns; the shock from the 90th
  percentile of rolling window drawdowns rather than the single largest
  drop; price impact from the regression of returns on aggregate flow when
  participant flows are present; the momentum window as the past window
  that best predicts the next return; the fundamentalist fraction from the
  observed speed of reversion toward a slow reference; the vendor split
  from Louvain communities of the flow correlation matrix (shares and
  within group correlations). Every fitted value is clamped to the
  planner's bounds with the clamp reported, and the fit, its diagnostics
  and its hash are written to the ledger.
- Two families per dataset join the plan. `calibrated_<sha>`: a synthetic
  market with the fitted parameters and the generator's ground truth, so
  decision accuracy is measured as usual. `hybrid_<sha>`: the observed
  return path is the market's news, the fundamentalists anchor to it, and
  the synthetic agents with the fitted structure respond; the shock time is
  the largest observed drop. Observed series are carried in the battery
  file for replay.
- Calibration shift: the rank correlation between the sentinel ranking on
  the demonstration herds and on the calibrated families, and whether rank
  one survives; stated as absent when the calibrated structure sits below
  the destabilising thresholds.
- Data desk shows the fitted parameters per dataset and the shift; the
  briefing carries both in the observed data section.

## 3.6.2 (2026-09-06)

- Certification is adjudicated by the conformal guarantee, not by the point
  estimate of the quiet alert rate. The certified sentinel is the highest
  decision F1 among those whose guarantee is achievable and whose conformal
  power is at least 0.50; the briefing and the decision gap panel say
  "conformally certified at level 0.25 given 8 exchangeable calibration
  scenarios". The empirical rate is the fallback only when no guarantee
  holds, and is named as such (`certification_basis` in the artefacts).
- Winner stability from the scenario bootstrap already run for the
  probability of inversion: P(tool is top by decision F1) and P(tool is the
  within budget pick) per sentinel, and the stability of the leader,
  reported on the decision gap panel and in the briefing.
- Cox hazard ratios and intervals computed with a clamped exponent; no
  runtime warning on a degenerate fit.
- Terminal: the light dropdowns are gone; classification, connector and the
  stored family and template pickers are segmented controls in the
  terminal's own style. The data desk, scenario library and agent workshop
  open with an instructional header (what the page does, the steps in
  order, what happens next). Upload well restyled.

## 3.6.1 (2026-09-05)

Regulator facing polish, from screenshots.

- Footer function keys could not be clicked: the scrolling tape was
  painted over them as it moved left. The tape now lives in its own clipped
  box, ignores the pointer, and the keys sit above it.
- Identifiers are shown in their regulator facing form everywhere a person
  reads them: underscores become spaces, sentence case, known acronyms
  upper case (`Liquidity withdrawal 0`, `RL emergent 2`, `Vendor A`,
  `LULD style band`). Applied to tables, alerts, the phase line, the tape
  selector and read outs, the pivot columns, the briefing and ASK. Codes,
  hashes and JSON keys are untouched.
- Proper capitalisation of chips, labels, table headers and first column
  cells, notes, seals and verdicts.
- Panels with many blocks (assurance, intervention monitor, decision gap,
  sentinel telemetry) now open with a row of section buttons; the reader
  chooses what the box shows and the choice survives the live re renders.
  The assurance page leads with what the reports ask for and no longer
  repeats the tail risk block.
- Perspective pivot: the theme was registered twice (a stylesheet and a
  custom property), so the picker listed Pro Dark twice and part of the
  settings panel stayed white; one registration remains and columns carry
  their regulator facing names.

## 3.6.0 (2026-09-05)

The authority's own agents.

- `hsl/agents.py` (new): an agent template is a JSON document in a small
  declarative language with no code execution. Order flow at each step is
  a bounded linear combination of named market signals (momentum,
  mispricing against fundamental, last return, volatility ratio, the
  crowd's previous flow, the agent's own inventory, the shared signal of a
  vendor cluster, time since the shock), gated by a threshold, an active
  window or a volatility withdrawal level, lagged, capped, noised, with an
  optional burst. Every coefficient and parameter is bounded and clamps
  are reported. `destabilising` may be true, false or auto; auto labels the
  class when it is large, its members act together and it pushes the price
  away from fundamental after the shock (the overshoot test, which
  separates liquidity provision from herding). A registry
  (`<runs_dir>/agents.json`) with author, timestamp and sha256; hashes are
  bound into every referencing scenario at planning so Gate 1 covers the
  definitions, the simulator refuses a changed definition and the critic
  checks the binding. `probe` runs one herd market with the agent at 20%
  and reports its signature before it is stored. `python -m hsl.agents
  validate | probe | template`.
- Simulator: `custom_agents` and `custom_agent_hashes` on the spec; custom
  classes take codes from -10 down and appear by name in the network panel
  and the attribution; custom agents draw their normals after the built in
  block, so earlier dynamics are unchanged bit for bit. The fundamental
  path is now carried on the result for the overshoot test.
- Families accept `custom_agents: [{"agent": name, "share": x}]`, validated
  against the registry and the population budget.
- Terminal: `AGT` agent workshop (editor, signals and bounds, probe,
  validate and store, remove, registry with provenance). CLI: `--agent
  file.json` (repeatable); stored agents load from the families store
  directory. Battery files carry the agent definitions for replay.
- `sample_data/agent_template.json`, `agent_example_liquidity_provider.json`,
  `family_example_mm_withdrawal.json`; `tests/test_agents.py` (5 tests);
  86 tests in total.

## 3.5.0 (2026-09-05)

The authority's own scenario families.

- `hsl/families.py` (new): a family is a JSON document (name, note, seeds,
  generator, vendor shares and correlations, shock, population, and any of
  the mechanisms of the battery: faulty vendor model, liquidity withdrawal,
  misinformation, colluding ignition, LLM persona, evader cohorts, RL
  share, quiet or held out). Validation against the same hard bounds the
  model planner obeys, with every clamped value reported and reserved
  names, unknown keys, impossible timings and over full populations
  refused. Expansion into seeded scenarios whose seeds derive from the
  definition's hash, so a family always reproduces and two families with
  the same parameters and different names differ. A store
  (`<runs_dir>/families.json`) with author, timestamp, sha256 and an
  enabled flag; enabled families join every later plan, enter the battery
  hash approved at Gate 1 and are written to the ledger with their hash.
  `python -m hsl.families template | validate | expand`.
- Terminal: `FAM` scenario library page with the JSON editor, the bounds,
  validate and store (preparer or admin role), enable, disable and remove,
  and the stored list with provenance. CLI: `--family file.json`
  (repeatable) and `--families-store <dir>`.
- Battery notes carry the family's own note marked as defined by the
  authority; the briefing, the ATRS record and the exchange record inherit
  it through the battery block.
- `sample_data/family_template.json`; `tests/test_families.py` (5 tests);
  81 tests in total. Dash callback validation relaxed so that controls
  rendered inside a panel body (the posture re check) register cleanly.

## 3.4.0 (2026-09-05)

What the reports ask for. The FSB (2024, 2025, 2026 consultation), IOSCO
(2025 report and the May 2026 Supervisory Toolkit), the Bank of England
(2025 Financial Stability in Focus; Breeden 2026) and the IMF (2024 GFSR
chapter 3) converge on a short list of needs. Each is now either answered
by a run with a figure, answered in part, or stated as needing firm
reporting the sandbox cannot supply.

- `hsl/reports.py` (new): the needs register (fifteen needs with sources),
  the supervisory indicators of IOSCO 2026 Table 7 and the FSB 2025 third
  party indicators computed from a run (adoption share, vendor Herfindahl
  index, top vendor share, substitutability proxy, dislocation threshold
  share, herd against quiet correlation channel, persona input to output
  sensitivity, incident frequency and severity, model performance and held
  out drift), a data gaps register of the five indicators that need firm
  reporting, the coverage map, the human oversight level of every rule
  (IOSCO 2026 Box 2 classes) and an exchange record in a fixed schema for
  cross border comparison (`exchange_record.json` in the evidence pack).
- Three scenario families for risks the reports name: `vendor_fault` (a
  faulty third party model sends every agent on the dominant vendor the
  same erroneous signal for 25 steps; the kill switch case of Breeden 2026
  and the contingency planning of IOSCO 2026), `liquidity_withdrawal`
  (liquidity providers cut provision to 30% after the shock; IMF 2024), and
  `misinformation` (the shock is disinformation retracted after 20 steps;
  FSB 2024, IOSCO 2025). Earlier dynamics unchanged bit for bit. Rules now
  report containment by family, so the faulty model episode has its own
  containment figure.
- Briefing section, assurance panel section, ASK intents (reports,
  indicators, oversight; the game, learned policy, appraisal and risk
  chunks restored) and the coverage map in the artefacts.

## 3.3.1 (2026-09-05)

Audit pass: static analysis (ruff, vulture, bandit), a manual read of every
input surface, profiling, and a search for anything documented but not
implemented. Fixes, all covered by the 75 tests.

Bugs and unimplemented behaviour
- Uploads above about 190 KB were rejected with 413: the server's request
  body limit was 256 KB while the desk advertised 25 MB. The limit now
  follows `HSL_UPLOAD_MAX_MB` (base64 inflated, plus headroom).
- "In evidence pack: yes" was a claim without an implementation: dataset
  rows were never written to the run directory or the pack. Accepted
  datasets are now persisted under `data/` as sanitised CSV with an index;
  the evidence pack takes the index and the rows of packable
  classifications only (public, synthetic); licensed and pseudonymised
  rows stay in the run directory. `export_csv` is now used for this.
- The replay connector accepted any path, a local file read primitive
  through the data desk; it now takes a fixture name in `sample_data` only.
- Bloomberg connector: the session is closed in a `finally`, timeout events
  no longer loop forever, response and security errors are surfaced. LSEG
  connector: session closed in a `finally`, empty results refused.
- Datasets held for the next plan are bounded (twenty, most recent kept).
- The survival block now reports a log rank test of each arm against the
  untreated market (the function existed but was never called).
- The transparency record no longer reads a placeholder artefact key.
- An unreadable `--data` file is logged rather than silently skipped.

Security
- The ASK rate limit was keyed by a name in the request body and could be
  reset per request; it is keyed by the proxy identity in header mode and
  the client address otherwise, and the table is bounded over long uptimes.
- The evidence pack was rebuilt on every download (a CPU cost per request
  and a race with a release in progress); it is rebuilt only when absent
  or older than the artefacts it packs.
- The model endpoint must be https and its response is capped at 4 MB.
- Role strings are bounded server side, not only by the input's maxLength.

Performance
- The simulator's per agent Python loop is vectorised per step with bit
  identical output (one standard normal per agent in index order, then per
  class scaling), verified against 44 recorded runs including every
  generator, the evader and the rules: about 40% faster per scenario.
- The network sentinel builds its graph from the upper triangle edge list
  instead of a dense conversion (identical partitions, about a third faster).

Dead code removed
- `evaluate_battery` (superseded by `pipeline.run_battery`), `_vol_bucket`,
  `_policy_probs`, unused colour constants and panel code list, unused
  imports and locals flagged by ruff. The browser test counts the DAT and
  SEC panels.

## 3.3.0 (2026-09-05)

Observed data, connectors and a security framework, after Anderson,
*Security Engineering* (3rd edition).

- The replay connector takes a fixture name inside `sample_data`, never a
  path; separators and parent references are refused so the data desk
  cannot be used to read files on the host. Dash dropdowns styled to the
  terminal tokens; posture statuses colour coded.

- `hsl/ingest.py` (new): one quarantine for every dataset (size and type
  limits, text only, schema check, spreadsheet formula check with signed
  numbers allowed, personal identifier scan that refuses rather than
  redacts, classification with a no write down rule, sha256 provenance);
  anchoring of observed returns against the battery's quiet family;
  held out empirical scenarios from the observed shock and volatility; an
  observed window that runs the sentinels on per participant order flow
  and reports counts only above the query set size of five.
- `hsl/connectors.py` (new): Bloomberg (Desktop API or B-PIPE via blpapi,
  licensed), LSEG Data Library (licensed), Alpha Vantage, FRED, ECB Data
  Portal, Bank of England database, and a replay fixture; all produce the
  same CSV shape and pass the same quarantine; HTTPS only, egress
  allowlist, no cross host redirects, timeout and size cap; credentials
  from `HSL_KEY_<SOURCE>` only. Connectors are off by default
  (`HSL_CONNECTORS`, `HSL_EGRESS_ALLOWLIST`). Only the replay path was
  exercised here.
- `hsl/security.py` (new): deployment posture self check with the chapter
  each control applies (`python -m hsl.security posture`), sha256 manifest
  of the vendored assets (`manifest`, `verify`), roles and least privilege
  (viewer, preparer, approver, admin; enforced from the proxy's role header
  in header auth mode), data classification, identifier scan, formula
  sanitiser, egress policy. `docs/SECURITY_FRAMEWORK.md` (new) is the
  written argument by chapter, packed with every evidence pack.
- Terminal: `DAT` data desk (upload with classification, connector form,
  quarantine verdicts, anchoring and observed window tables) and `SEC`
  security posture panel with re-check; roles refuse plan, gate, stop,
  upload and fetch they do not hold.
- Pipeline: `data` and `security` artefact blocks; the critic checks dataset
  hashes and classifications, the query set size, and that no posture
  control fails (30 checks in a full run); briefing sections and ASK
  intents for data and security; the ATRS data section names the datasets.
- CLI: `--data <file>` (repeatable) and `--data-class`.
- `sample_data/` (new): two synthetic fixtures (an index series and per
  participant flows) for demos and tests. `tests/test_data_security.py`
  (8 tests); 72 tests in total.
- Rebuild the asset manifest after any change to `assets/`:
  `python -m hsl.security manifest`; a stale manifest fails the posture
  check and seals Gate 2, which is the control working.

## 3.2.1 (2026-09-05)

Accountability fields and a transparency record, after the question of
whether people who run such systems are registered anywhere. In the UK
they are not registered as such: SM&CR attaches accountability to named
individuals at authorised firms, the Algorithmic Transparency Recording
Standard registers the system and its accountable senior manager for
public bodies, and the EU AI Act registers high-risk systems (deferred to
December 2027 by the Digital Omnibus). HSL now speaks both languages.

- `hsl/atrs.py` (new): an algorithmic transparency record in the structure
  of the UK ATRS template (tier 1 summary; tier 2 owner and responsibility,
  description and rationale, decision making process, tool specification,
  data, risks and mitigations, impact assessments), generated at release
  from the artefacts and the approvals and nothing else. Written as
  `atrs_record.md` and `atrs_record.json`, served from the run, linked in
  the RUN panel and included in the evidence pack. Marked as a draft for
  the accountable owner; blank fields are for the adopting authority.
- The critic vets every number in the record against the artefacts as it
  does for the briefing (28 checks in a full run); version and platform
  tokens are treated as identifiers, not figures.
- Role fields: the approver's SMF or certified function and the preparer's
  function, optional, entered in the RUN panel (`--approver-role`,
  `--preparer-role` on the CLI), recorded on every gate entry in the
  ledger, in `approvals.json` and `meta.json`, shown in the gate seals and
  the briefing signatures, and carried into the record as the senior
  responsible owner's role.
- `tests/test_atrs.py` (2 tests); 64 tests in total.

## 3.2.0 (2026-09-05)

Course grounded upgrades. Each addition takes a method from a taught
module and applies it to the certification problem; nothing in the version
1 to 3.1 dynamics changed and the earlier batteries still reproduce.

### Quantitative risk management (`hsl/risk.py`, `hsl/evaluate.py`, `hsl/herding.py`)

- Value at risk and expected shortfall of the untreated post shock drawdown
  over the herding scenarios, per rule ES reduction with a bootstrap
  interval, and a generalised Pareto peaks over threshold fit of the tail
  with the number of excesses reported beside it (`risk_report`).
- Expected shortfall containment (`tail_containment`) per rule in the
  intervention monitor, checked by the critic to be at least the mean.
- `TailDependenceSentinel`: the largest cluster of agents whose order flows
  are jointly extreme (empirical lower tail dependence from ranks in a
  rolling window). Eight sentinels are now ranked.

### Survival analysis (`hsl/survival.py`)

- Time to dislocation with censoring: Kaplan Meier per arm (untreated and
  each rule), median and survival at 20 and 60 steps, Weibull baseline, a
  ridge stabilised Cox proportional hazards model with the untreated market
  as reference (hazard ratio per rule; share and correlation per standard
  deviation), a log rank test, and per sentinel pre emption probability and
  median alert step.

### Reinforcement learning (`hsl/rl_supervisor.py`, `hsl/redteam.py`)

- A learned market wide intervention policy: transitions logged under an
  epsilon soft behaviour policy, a tabular model fitted by counts, value
  iteration under declared halt and throttle costs; scored as a rule like
  any other and advisory only.
- Off policy evaluation of every rule from the logged data: per decision
  importance sampling, a doubly robust estimator with clipped weights and
  the fitted model's value, each compared with the simulated on policy
  value; mean absolute errors reported.
- The adversarial evasion search is a UCB1 bandit over evasion arms and
  scores every sentinel on every trial.

### Game theory (`hsl/games.py`)

- The sentinel against evader matrix game over the dislocating red team
  trials: maximin sentinel, the adversary's best counter, the mixed
  strategy value by linear programme and the value of unpredictability.

### AI reasoning (`hsl/simulator.py`, `hsl/audit.py`)

- Voter model generator: herding as opinion consensus by local copying on a
  ring inside each vendor cluster; a fourth generator in the truth
  dependence audit.

### Regulation, strategy and enforcement (`hsl/appraisal.py`, `hsl/rules.py`)

- Regulatory options appraisal: instrument type per rule, an enforcement
  ladder from monitor and warn to market wide halt, tests of containment,
  false halt budget and proportionality (burden on agents that were not
  destabilising), the do nothing baseline and the non regulatory option,
  an illustrative legal basis per rule, and a responsive regulation
  recommendation of the lowest eligible tier.
- `ResponsiveLadder` rule: escalation from a targeted throttle to a halt.

### Integration

- Pipeline stages, artefact blocks (`risk`, `survival`, `learned_policy`,
  `game`, `appraisal`), four new critic checks (27 in a full run), briefing
  sections, ASK intents and chunks, assurance panel sections.
- `tests/test_v32.py` (14 tests); 62 tests in total. `REFERENCES.md`
  extended with the course readings behind each method.

## 3.2.0 (2026-09-05)

Methods drawn from course material supplied by the team (LSE ST411
Survival Analysis; LSE ST455 Reinforcement Learning; LSE Quantitative Risk
Management; KCL 6CCS3AIN Artificial Intelligence, consensus mechanisms;
QMUL ECS7002P AI in Games; LSE Regulation, Strategy and Enforcement).
`REFERENCES.md` lists the underlying published sources.

- `hsl/survival.py` (new): time to dislocation as a survival problem. The
  event is the first step after the shock at which the drawdown from the pre
  shock level exceeds the dislocation threshold, censored at the horizon.
  Kaplan Meier curves per arm (untreated market and each rule) with Greenwood
  errors, medians and survival at 20 and 60 steps; a Cox proportional hazards
  model (Breslow ties, ridge penalised partial likelihood with step halving)
  with one indicator per rule and the dominant vendor's share and correlation
  as covariates; time to first alert per sentinel, censored at the shock,
  whose survival at the shock is the pre emption probability. Artefacts block
  `survival`; briefing section; RSK panel table; ASK intent; critic check.
- Expected shortfall (level 0.75) of post shock drawdown, untreated and
  treated, and tail containment for every rule (QRM chapter 3: ES is
  coherent, VaR is not). Critic requires ES at least the mean.
- `TailDependenceSentinel` (eighth sentinel): pairwise tail concordance of
  order flows (probability that two flows sit in the same tail of their own
  distributions, q under independence and one under perfect dependence),
  largest component above a threshold, mass as stress index (QRM chapter 7:
  linear correlation misses tail dependence). On the demonstration families
  it detects the low intensity herd that most sentinels miss.
- `ResponsiveLadder` (seventh rule): an enforcement pyramid as an
  intervention rule, escalating from a targeted throttle to kill
  functionality to a market wide halt only when the lower rung fails and
  stepping down on recovery (Ayres and Braithwaite; Baldwin and Black).
- `generator="voter"`: herding by local copying on a ring within a vendor
  cluster (the voter model of 6CCS3AIN week 9); the truth dependence audit
  now compares four generators.
- Red team: the adversarial search is a UCB1 bandit over nine evasion arms
  (reward: damage to the certified sentinel when the market dislocates),
  the bandit form of adaptive stress testing (ST455 lecture 9 and AI in
  Games lab 3 on Monte Carlo planning with UCT); `method="random"` keeps
  the version 3 baseline. Artefacts record pulls and mean damage per arm;
  the critic checks that pulls sum to the trials.
- Briefing: an impact assessment summary in the structure of the UK Better
  Regulation Framework (rationale, options, costs and benefits, monitoring
  and evaluation) and an enforcement ladder section.
- Tests: `tests/test_v32.py` (8 tests); 56 tests in total.

## 3.1.0 (2026-09-05)

Terminal redesign. No change to the pipeline, the artefacts or the tests of
the core library.

- `assets/hsl.css` rewritten around a token system: ground `#05070b`, wells
  `#020306`, surfaces `#0b0f16` and `#10161f`, hairlines at 14% and 30%;
  amber `#f6b52a` only for function codes, the command line, the gates and
  the active state; blue `#6cb5ff` for every data series; green `#47d6a3`
  and red `#ff5f5f` for state. IBM Plex Sans for words and JetBrains Mono for
  numbers, vendored under `assets/fonts/` with their licences. No rounded
  corners, no shadows, one pixel rules; numeric table columns right aligned
  with tabular figures; inputs recessed; empty states without dashed boxes.
- Workflow rail under the command bar (plan, Gate 1, battery, rules,
  assurance, critic, Gate 2, released) lit as the run advances; green on
  release, red on refusal, stop or error. Function key row in the footer.
  Front page reworked as a boot card with a two column key index.
- Case file panel renders natively (decision F1 by sentinel and family,
  held out and quiet columns, per scenario rows when maximised); the
  Perspective pivot opens from the panel header. The sentinel table shows
  a compact column set in the grid and the full set when maximised.
- Semantics fixed in the data views: price line and treated series in blue,
  the herd path in red, dose response bars red only where dislocation is
  the likelier outcome; network palette categorical and distinct from the
  state colours, force layout spread so flagged borders read.
- Copy: middle dot separator strings replaced by punctuation in phase
  lines, alerts and status text; formatted intervals and lists in ASK
  sources and the RL emergence note.
- Network panel made legible: click a node to open an inspector (class,
  verdict against the ground truth, edges, mean correlation, market
  correlation, share of gross flow, strongest correlations with links to
  neighbours); a frame readout with destabilising, flagged, correct,
  missed and false flags plus precision and recall; a red ring marks a
  destabilising agent the sentinel missed; labels toggle; ring by class
  layout that shows the herd as a chord bundle; edge width by strength.
  `net.json` nodes now carry degree, mean correlation, market correlation
  and flow share.
- Dash 4 input wrappers sized and their default focus ring removed.
- `test_terminal.py` updated for the native case file and the extra panel.

## 3.0.0 (2026-09-05)

Every change from version 2, itemised. Nothing in the market dynamics of
version 1 and 2 scenarios changed: the new agent classes and generators draw
random numbers only when a scenario enables them, and
`tests/test_core.py::test_v1_dynamics_preserved` still pins the version 1
drawdowns. `REFERENCES.md` (new) lists every work the build draws on and
states that no third party code was copied.

### Simulator and battery (`hsl/simulator.py`, `hsl/personas.py`)

- `ScenarioSpec` gains `generator` (shared_signal, imitation, sqrt_impact),
  `evader_period`, `manipulator_share`, `ignition_time`, `ignition_len`,
  `ignition_size`, `persona`, `persona_share`, `persona_noise` and
  `persona_hash`. Defaults reproduce version 2 exactly.
- Two new agent classes: `manipulator` (-4), a colluding cluster that stays
  quiet, sells in a coordinated burst across the shock and then buys back;
  `llm_persona` (-5), agents trading from one distilled policy table.
  Manipulators are always ground truth positives; a persona group is a
  positive when it is large and follows momentum (slope of its own table).
- Imitation generator: vendor members are chartists or fundamentalists and
  recruit one another within their cluster at rate rho, with a fundamentalist
  recruiting less the stronger the trend (Lux and Marchesi); trends tip a
  cluster into a chartist herd. Square root generator: concave price impact
  normalised to match the linear rule at a mean flow of 0.5.
- `personas.py` (new): `PersonaPolicy` (3 volatility regimes by 5 momentum
  buckets, actions from the RL action set, sha256 of the table), three
  documented offline surrogates, `elicit_persona()` (one model call, JSON
  validated, fallback recorded), a registry and `bind_persona_hashes()` which
  writes each table's hash into the specs at planning so Gate 1 covers the
  tables and `simulate()` refuses a table that has changed.
- Battery: ignition family (3), persona family (3), eight quiet scenarios
  (so the conformal guarantee at the 0.25 budget is achievable), `seeds_per`
  parameter; 34 scenarios in the default battery.

### Sentinels (`hsl/herding.py`, `hsl/sentinels.py`, `hsl/_common.py`)

- `herding.py` (new): `ImbalanceSentinel` (Lakonishok, Shleifer and Vishny
  buy sell imbalance herding measure on order flow), `EndogeneitySentinel`
  (Hawkes branching ratio by profiled maximum likelihood on large move
  events, after Filimonov and Sornette; localisation by correlation with the
  endogenous intensity), `LeadLagSentinel` (lag one lead and follow scores;
  flags leaders at a robust z score and the strongest followers). All expose
  `flags_online`. Thresholds set on the demonstration quiet family.
- `sentinels.py`: `ALL_SENTINELS` is the four core sentinels plus the three
  herding sentinels (seven tools); `CORE_SENTINELS` kept. The network
  sentinel uses Louvain communities with a fixed seed instead of greedy
  modularity (same construct, two to three times faster; flags and first
  alerts identical on every scenario compared). Shared helpers moved to
  `_common.py`.

### Evaluation and assurance (new modules)

- `conformal.py`: conformal p values and thresholds on the quiet calibration
  scenarios at the declared budget; per sentinel guaranteed bound,
  achievability, conformal power on calibration and held out herds, held out
  quiet alert rate as the exchangeability check; `certifiable()`.
- `attribution.py`: Shapley values of post shock drawdown over agent groups
  by counterfactual silencing under common random numbers; efficiency
  residual; impact ordering; per sentinel share of flags on the top group and
  rank correlation of flag rates with impact.
- `audit.py`: `truth_dependence()` (reduced battery under each generator,
  rankings, Kendall tau, rank shifts, rank one preserved) and
  `concentration_sweep()` (share sweep at fixed correlation, amplification,
  dislocation probability, quadratic curvature, threshold share).
- `rules.py`: `LULDStyleBand`, `MarketWideBreaker`, `VenueVolatilityHalt`
  with `jurisdiction` and `basis`; `RULE_LIBRARY`; `evaluate.ALL_RULES` now
  six rules (`CORE_RULES` kept).
- `frontier.py`: sentinel and rule loss as a function of the declared weight
  c; optimal intervals, crossovers, loss at the declared c.
- `redteam.py`: budgeted adversarial search over cohorts, rotation period,
  correlation and share for the worst case of the certified sentinel subject
  to dislocation, with every sentinel's F1 on it and the robustness margin;
  eleven case injection suite against the planner, persona elicitation,
  drafter, ASK and ledger.
- `pipeline.py`: assurance stages after the rules with streamed progress;
  `ASSURANCE` budgets and an `assurance` argument; artefacts gain
  `conformal`, `conformally_certifiable`, `certified`, `frontier`,
  `attribution`, `truth_audit`, `concentration`, `redteam`, `personas`,
  `rule_library`; provenance records the sentinel and rule sets.
- `critic.py`: number vetting keeps the printed precision (up to four
  decimals) so dense artefacts no longer let any figure in [0, 1] pass; seven
  new checks: conformal arithmetic, Shapley efficiency recomputed, frontier
  endpoints, injection suite, truth audit range, adversarial search bounds,
  persona hash binding (twenty one checks in a full run).
- `briefing.py`: sections for the guarantee, the cost frontier, attribution,
  truth dependence, the dose response, the red team, personas and the rule
  library; herding versus noise paragraph.
- `ask.py`: intents and deterministic answers for red team, conformal,
  attribution, frontier, truth, concentration and persona questions;
  retrieval chunks for every new block; glossary entries.
- `orchestrator.py`: persona hashes bound at planning; persona tables written
  to `battery.json` and restored on replay; assurance budget from `HSL_ASSURANCE`;
  seeds from `HSL_SEEDS`.

### Terminal, configuration, figures, tests, documentation

- `dash_app.py`: `RSK` assurance panel (hidden until maximised, like `AUT`
  and `REG`), assurance progress events with alerts, ASK snapshot carries the
  artefacts; `assets/terminal.js` codes `RSK`, `RISK`, `ASSURANCE`, `RED`;
  `assets/hsl.css` panel rule.
- `config.py`: `HSL_ASSURANCE` (full or light) and `HSL_SEEDS`; exposed on
  `/version`.
- `figures.py`: dose response, cost frontier and attribution figures.
- `tests/test_v3.py` (new, 22 tests): 48 tests in total.
- `README.md`, `docs/VALIDATION.md` and `REFERENCES.md` updated or added.

## 2.0.0 (2026-09-01)

Every change from the hackathon build, itemised. File paths are relative to
the repository root. Nothing in the market dynamics, the RL agents or the
original three sentinels and two rules changed; `tests/test_core.py::
test_v1_dynamics_preserved` pins the v1 numbers.

### Core library (`hsl/`)

- `__init__.py` (new): package version, `code_fingerprint()` over the
  package source and `provenance()` (versions, platform) for artefacts.
- `ledger.py` (new; replaces `RationaleLog` in `orchestrator.py`):
  append only file that continues an existing chain instead of truncating;
  full SHA-256 over canonical JSON; HMAC-SHA256 signature under a secret;
  sequence numbers, run id, actor and UTC timestamp on every record;
  numpy safe encoder; `verify()` with a command line entry point
  (`python -m hsl.ledger verify`); fsync on every write.
- `simulator.py`: `family`, `holdout` and `evader_cohorts` fields on
  `ScenarioSpec`; `describe()` now returns every field; `battery_hash()`;
  `SimulationStopped` and a cooperative `stop` event checked every 50
  steps; `post_shock_drawdown()`, `shock_trough()`, `pre_shock_vol()` and
  `class_members()` on `SimResult`; `class_label()`; the evader mechanism
  (cluster 0 rotates cohorts every 5 steps with flow scaled by the number
  of cohorts, preserving aggregate impact); `scenario_battery()` adds three
  evader scenarios, three held out herding and two held out quiet
  scenarios (150 agents, three vendors, shock at 400, kappa 0.018); family
  notes for the UI and the briefing. Dynamics for all v1 specs unchanged.
- `sentinels.py`: every sentinel now returns `flags_online` (T×N), the
  flags issued by each step, built from the same events that set the final
  flags; `stride` and `alert_level` parameters; sentinel `label`s; new
  `AbsorptionRatio` sentinel (share of flow variance on the leading
  eigenvector, localisation by loading, threshold 0.31 calibrated on the
  demonstration quiet family).
- `evaluate.py`: two declared fidelity constructs (`FIDELITY_CONSTRUCTS`);
  `score_row()` carries family, held out flag, both fidelities, peak
  stress, pre shock volatility, post shock drawdown and confusion counts;
  `bootstrap_ci()` and `evidence_grade()`; `summarise()` returns
  calibration and held out summaries with intervals, grades, by family
  results, `share_alerting`, a false alert budget (0.25) and a
  `within_budget` flag; `best_certifiable()`; `decision_gap()` reports the
  number of tools and the construct; `gap_bootstrap()` gives P(inversion),
  P(full inversion) and a gap interval; `DynamicThrottle.make()` takes
  `flags_online` and records whether lookahead was used; new `KillSwitch`
  rule (factor 0, dwell 120); `evaluate_rules()` reuses cached untreated
  runs, measures post shock and trough containment with bootstrap
  intervals, dislocation probability before and after (threshold 0.10),
  false halts, pre shock engagement, and burden by class and by ground
  truth over the 150 steps after the shock; held out scenarios are excluded
  from rule calibration.
- `autonomy.py` (new; moved out of `dash_app.py`): the same score
  triggered gates, plus leave one out validation reporting backed share,
  claims and claim rate; `autonomy_public()` strips per scenario lists.
- `critic.py` (new): fourteen checks: summary recomputed from rows,
  ranking heads, gap recomputed, gap range, bootstrap range, intervals
  contain estimates, rule arithmetic and no lookahead, autonomy
  bookkeeping and withdrawal rule, battery hash bound to Gate 1, held out
  families present, ledger replay, briefing numbers vetted, provenance
  present. Number vetting ignores identifiers (hashes, run ids, dates,
  clock times, semantic versions) and tolerates formatting rounding.
- `pipeline.py` (new): one `run_battery()` used by both the CLI and the
  terminal with optional streaming hooks, so batch and streamed numbers are
  identical; computes network frames from the first herding scenario; the
  treated three worlds stream carries its own name.
- `briefing.py` (new; replaces `draft_briefing` in `orchestrator.py`):
  evidence graded briefing with run id, preparer and both approvals; both
  fidelity constructs; intervals and grades; held out, adversarial and
  emergent families; interventions with containment intervals, dislocation
  probability, false halts, pre shock engagement and burden; automatic
  paragraphs for the false alert budget, the targeting cost to
  fundamentalists and pre shock engagement; autonomy in sample and leave
  one out; scope, grades and provenance; `to_html()` for a printable copy.
- `evidence.py` (new): evidence pack zip with SHA-256 manifest and a
  `VERIFY.md`.
- `ask.py` (new): server side retrieval and deterministic intent answers
  (certify, gap, rules, autonomy, false alerts, lead time, generalisation,
  ledger, status, scenario lookup) with sources; glossary extended.
- `llm.py`: `HSL_LLM=off` disables all outbound calls; model planned
  batteries keep the fixed guardrail families; ASK phrasing with a fixed
  system prompt and question only input; drafting uses the critic's number
  vetting; question length capped.
- `orchestrator.py`: run id, per run directory with all files, signed
  ledger, four eyes option, `--battery` replay from an evidence pack,
  provenance in `run_started`, evidence pack built on release.

### Server (`dash_app.py`, `config.py`, `runstore.py`, `assets/`)

- `config.py` (new): all settings from the environment with safe defaults;
  localhost bind; ephemeral secret with a warning if none is set.
- `runstore.py` (new): per run directories, metadata index, atomic JSON
  writes, evidence packs, servable file allow list.
- `dash_app.py`: rewritten. Identity from a trusted proxy header in
  `header` mode; typed preparer and approver fields in `open` mode;
  approver allow list; four eyes; Gate 1 and Gate 2 approve or refuse with
  a required reason; emergency stop; per run state reset; live NET and
  per scenario tape; `REG` registry panel; ledger replay status; evidence
  links; `/healthz`, `/version`, `/runs.json`, `/run/<id>/<file>` (allow
  listed), `/ask` (question only, rate limited); security headers; request
  size limit; identity required for state changing requests in header mode.
- `assets/terminal.js`: per scenario tapes indexed by step with a
  selector and live following; markers for the shock and first alerts;
  three worlds chart fitted on display; server side ASK client; controlled
  input clearing; registry code.
- `assets/hsl.css`: 12 px body, 11 px tables, 10 px captions; sentence
  case; new controls (stop, refuse, identity chip, interval bands, chips).
- `assets/network.html`: reads the live run's `net.json`; class colours,
  ground truth squares, flagged borders, window and mean correlation in the
  title.
- `assets/casefile.html`: reads the live run's `rows.json` with a pivot
  by sentinel and family.
- Removed: `assets/network_data.json` (canned), `dash_app_v1_backup.py.txt`,
  the Streamlit `app.py` and `demo.py` (superseded by the CLI orchestrator
  and `figures.py`).

### Tests, tooling and documentation

- `tests/test_core.py` (new, 20 tests) and `tests/test_server.py` (new, 6
  tests); `test_terminal.py` rewritten for v2 (21 browser checks).
- `figures.py` (new): paper figures from a run directory.
- `requirements.txt` pinned; `requirements-dev.txt`; `Dockerfile`;
  `deploy/docker-compose.yml`; `deploy/nginx.conf`; `.env.example`.
- `README.md` rewritten; `REVIEW.md`, `CHANGELOG.md`, `docs/DEPLOYMENT.md`,
  `docs/SECURITY.md`, `docs/VALIDATION.md` added.
