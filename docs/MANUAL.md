# Herding Scenario Lab: the manual

## Running a battery: use the demonstration identities

The live prototype at https://hsl-terminal.onrender.com, and any local copy started with `HSL_DEV_MODE=on`, accept two built in identities, so no account and no register entry is needed. On the RUN page enter exactly:

| Field | Value |
|---|---|
| Prepared by | `Developer1` |
| Preparer's function | `Developer1` |
| Approver at the gates | `Developer2` |
| Approver's function | `Developer2` |

Then click **Plan**, then **Gate 1: approve battery**, wait for the battery and the critic to finish (a few minutes on the demonstration profile; the phase line under the command bar shows progress), and click **Gate 2: release briefing**, or **Refuse** with a reason. The preparer and the approver must differ (four eyes). Any other names are checked against the register of regulated persons in `sample_data/register.csv`, which also accepts the four team members listed there with their recorded functions (for example approver `Rajib Ahmed`, function `SMF24`); names not on it are refused, by design.

Version 3.9. This manual goes through every feature of the terminal, what each control does, and every quantity the platform measures, with its definition and where it appears. It is written for the people who will use it: market oversight, financial stability and policy teams in a central bank or a securities regulator.

Contents

1. What HSL is and is not
2. Installing and running
3. The workflow: question, plan, gates, run, critic, release
4. The terminal: navigation and every page
5. Scenarios: generators, mechanisms, the demonstration battery, families of your own
6. Agents: every class, and agents of your own
7. Sentinels: the surveillance tools under test
8. Intervention rules
9. Everything the platform measures
10. Assurance stages
11. Observed data: the data desk, connectors, calibration, backtests
12. Governance: gates, roles, ledger, evidence pack, transparency and exchange records
13. Security posture
14. The model layer
15. ASK, the run oracle
16. Configuration reference
17. Command line reference
18. Files a run produces
19. Limitations

---

## 1. What HSL is and is not

HSL is a sandbox in which a public authority stress tests surveillance sentinels and intervention rules against synthetic markets populated by AI trading agents, and certifies them on the decision they exist to inform (which agents are destabilising, and can the dislocation be contained) rather than on how closely a synthetic market matches aggregate statistics. Its central finding, from the team's published research, is that the two rankings can invert: the tool that best reproduces aggregate statistics can be the worst at identifying destabilising agents. HSL measures that decision gap on every run.

It is not a trading system, a forecasting tool or a surveillance system. It never touches live markets, never recommends live intervention, and produces comparative rankings on a declared battery with intervals, evidence grades and a replayable trail, for a named supervisor to act on.

---

## 2. Installing and running

Requirements: Python 3.12, the packages in `requirements.txt` (numpy, scipy, networkx, dash, flask, matplotlib). Optional: `transformers` and `torch` for a local model, `blpapi` or `lseg-data` for those connectors, `playwright` for the browser test.

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HSL_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))")
python dash_app.py                 # http://127.0.0.1:8050
```

Profiles: `HSL_ASSURANCE=demo` runs twelve short scenarios in about twenty seconds for a live demonstration (the heavy audits skipped and declared in the ledger; never a certification battery); `HSL_ASSURANCE=light HSL_SEEDS=2` runs a reduced battery in under two minutes; the full profile runs 40 or more scenarios in about four to six minutes. `HSL_PORT` changes the port. A Dockerfile and `deploy/docker-compose.yml` with an nginx configuration run the service behind an authenticating proxy with gunicorn.

Command line, without the terminal:

```
python -m hsl.orchestrator --approve-battery --approve-briefing \
    --preparer "D. Godorozha" --preparer-role "certified function" \
    --approver "R. Ahmed" --approver-role "SMF24" --outdir runs/cli
```

Tests: `python -m pytest -q tests` (92 tests). Browser test: `python test_terminal.py`.

---

## 3. The workflow

Every run follows the same sequence, and the rail under the command bar shows where a run is.

| Step | What happens | Who acts |
|---|---|---|
| Question | A policy question is typed on `RUN`. It is read deterministically (numbers, mechanisms, tools) and, with a model configured, also used to plan families. | Preparer |
| Plan | The battery is built: demonstration families, the question family, families and agents the authority defined, families calibrated from accepted data. The battery is hashed. | System |
| Gate 1 | The approver, who must differ from the preparer, approves that battery by hash or refuses with a recorded reason. Nothing simulates before it. | Approver |
| Battery | Every scenario is simulated and streamed; every sentinel is scored on it. | System |
| Rules | Every intervention rule is applied to every herding scenario and to the quiet scenarios. | System |
| Assurance | Conformal certification, cost frontier, attribution, truth audit, dose response, learned policy and off policy evaluation, risk, survival, red team, game, appraisal, calibration shift, backtests, reports coverage. | System |
| Critic | Thirty one checks recompute every headline number from the per scenario rows, replay the ledger, vet the briefing and the transparency record, check the security posture. Gate 2 does not arm unless all pass. | System |
| Gate 2 | The approver releases the briefing and the evidence pack, or refuses. | Approver |

An **emergency stop** halts execution at the next check and seals the partial ledger. Both gates accept a **refusal** with a reason that goes into the ledger.

---

## 4. The terminal

### Navigation

Type a code in the command line and press Enter (or click **GO**), press a digit, or click a key in the footer row. `Esc` restores the grid. `FRONT` reopens the front page. `HELP` lists the codes. Double clicking a panel header maximises it. A page opens from anywhere: the footer keys, the digits 0 to 9, the letters K D F A S R, or a code in the command box; Esc returns to the grid; the New run button beside Plan clears the terminal for a fresh run (stopping one in progress) and keeps the datasets. Dragging the line between two boxes resizes them (width between neighbours in a row, height between rows); double clicking a line restores that split; `LAYOUT` resets the grid. Every box scrolls in both directions when its content is larger than the box; tables keep their natural width and scroll sideways rather than squeezing. Panels with many blocks open with a row of section buttons; the choice survives the live re render.

| Key | Code | Page |
|---|---|---|
| 1 | `MKT` | Market tape |
| 2 | `NET` | Correlation network |
| 3 | `GAP` | Decision gap |
| 4 | `SEN` | Sentinel telemetry |
| 5 | `INT` | Intervention monitor |
| 6 | `CSF` | Case file |
| 7 | `LDG` | Rationale ledger |
| 8 | `RUN` | Run control, gates and briefing |
| 9 | `ASK` | Run oracle |
| 0 | `AUT` | Autonomy gate |
| K | `RSK` | Assurance |
| D | `DAT` | Data desk |
| F | `FAM` | Scenario library |
| A | `AGT` | Agent workshop |
| S | `SEC` | Security posture |
| R | `REG` | Run registry |

The top bar shows the phase line (what the run is doing), the run id, the stage lamp (idle, planning, planned, running, evaluated, released, refused, halted, error) and the clock. The footer carries the function keys and a tape of alerts.

### MKT, market tape

Every simulated price step of the current scenario, live, one tick per step. The shock is marked; each sentinel's first alert is marked on the tape. The selector chooses any completed scenario; **Live** follows the running one. **3 worlds** (after the run) shows the same shock in a quiet market, in the herd, and under the best rule, with post shock drawdowns in the read out.

### NET, correlation network

The first herding scenario's agent correlation network in three frames: before the shock, as it lands, in the cascade. Nodes are agents (colour by class); squares are agents destabilising in the ground truth; an amber ring is the sentinel's flag; a red ring is a destabilising agent the sentinel missed; edges are flow correlations above 0.5, width by strength. The readout gives the window, edges, mean correlation, destabilising count, flagged count, correct flags, missed, false flags, precision and recall for the frame, and the most connected agent. Click a node for its class, verdict, edges, mean correlation with all agents, correlation of its flow with the market return, share of gross flow, and its strongest correlations (clickable). **Ring by class** arranges agents by class on a circle so the herd shows as a chord bundle. **Labels** toggles agent ids on flagged and destabilising nodes.

### GAP, decision gap

Headline tiles: decision gap, Kendall tau, probability of inversion, and the same under the multi moment construct. Per sentinel, fidelity and decision F1 bars with bootstrap intervals. The two rankings. The certification line (conformal or empirical basis) and the winner stability line. Sections: Headline, Sentinels.

### SEN, sentinel telemetry

Per sentinel: fidelity (both constructs), decision F1 with 95% interval and evidence grade, precision, recall, lead time, false alert rate against the budget (a cross marks a breach), held out decision F1 and false alert rate. Compact columns in the grid, the full set when maximised. The alert feed lists every sentinel alert with its scenario and lead.

### INT, intervention monitor

One section per rule: drawdown untreated and treated, containment with interval and grade, dislocation probability before and after, false halt rate, engagement before the shock, burden by class (destabilising, others, fundamentalists), the throttle's withdrawal status, containment by family. Then the three worlds tiles and the RL emergence note.

### CSF, case file

Decision F1 by sentinel and family, with held out F1 and quiet false alert rate; the per scenario rows when maximised. **Open pivot** opens the same rows in an interactive Perspective pivot in a new tab.

### LDG, rationale ledger

Every entry of the hash chained, signed ledger as it is written: sequence, time, actor, event, payload keys, entry hash. Verification status at evaluation.

### RUN, run control

Policy question; preparer and approver names; the approver's SMF or certified function and the preparer's function (optional, recorded); reason (required to refuse). Buttons: Plan, Stop, Gate 1 approve and refuse, Gate 2 approve and refuse. Then the run status: identities, battery table (family, count, agents, shares, correlations, shock, note), gate seals, critic verdict, links (artefacts, ledger, evidence pack, printable briefing, transparency record, exchange record), and the released briefing rendered on paper.

### ASK, run oracle

A question box; answers are computed on the server from the artefacts of the current run and the sources are listed beside them. See section 15.

### AUT, autonomy gate

How much execution the evidence would back: the pre emption score axis with the zero claim gates, in sample and leave one out backing rates, the claim rate, separability, and the throttle availability. Defaults to none.

### RSK, assurance

Twelve sections: Reports, Guarantee, Cost frontier, Attribution, Survival, Truth audit, Dose response, Game, Learned policy, Tail risk, Appraisal, Red team, plus Backtests. Each is described in section 10.

### DAT, data desk

Upload or fetch observed data through the quarantine; classification and connector controls; the datasets waiting for the next plan with their calibration; anchoring and calibration shift after a run. Section 11.

### FAM, scenario library

Define, validate, store, enable, disable and remove families of your own. Section 5.

### AGT, agent workshop

Define, probe, validate, store and remove agent templates of your own. Section 6.

### SEC, security posture

The deployment checked against the framework's controls, each naming its chapter of Anderson's Security Engineering. Section 13.

### REG, run registry

Every past run: id, stage, question, preparer, approver, files. Runs live in `HSL_RUNS_DIR`.

---

## 5. Scenarios

A scenario is one simulated market: a population of agents trading for `t_steps` steps (600 by default) with a shock to the fundamental value at `shock_time` (300 by default). Prices move by the crowd's net order flow through a price impact function plus noise. A family is a set of scenarios that differ only by seed.

### Generators

| Generator | Mechanism |
|---|---|
| `shared_signal` | Agents on a vendor read a shared signal: momentum plus an AR(1) vendor factor, blended with idiosyncratic noise by the vendor's correlation. The default. |
| `imitation` | Lux and Marchesi style: agents switch between chartist and fundamentalist modes by recruitment that depends on the trend. |
| `voter` | Agents copy the stance of a neighbour on a small world ring inside each vendor cluster (Holley and Liggett; the voter model). Consensus is the herd. |
| `sqrt_impact` | The shared signal generator with Bouchaud's concave (square root) price impact. |
| `hybrid` | The observed return path is the market's news; fundamentalists anchor to it; synthetic agents respond. Used by the calibrated hybrid family and the rule backtest. |

### Mechanisms a scenario may add

| Field | Effect |
|---|---|
| `evader_cohorts`, `evader_period` | The dominant vendor rotates its agents through cohorts, defeating correlation based surveillance. |
| `manipulator_share`, `ignition_time`, `ignition_len`, `ignition_size` | A colluding cluster sells hard for a window then reverses, igniting momentum. |
| `persona`, `persona_share`, `persona_noise` | A group trades from one distilled LLM persona table. |
| `rl_share` | A share of independently trained reinforcement learning traders. |
| `vendor_fault_time`, `vendor_fault_len`, `vendor_fault_signal` | The dominant vendor's model misfires: every agent on it receives the same erroneous signal for a window. |
| `liquidity_withdrawal_time`, `liquidity_withdrawal_scale` | Fundamentalists cut their liquidity provision to a fraction after the time. |
| `false_shock_len` | The shock is misinformation retracted after this many steps. |
| `custom_agents` | Groups of agents from templates defined in the workshop, with shares. |
| `quiet` | No shock; used for false alert measurement. |
| `holdout` | Never used for calibration; scored separately. |

### The demonstration battery

Three seeds per family unless stated (`HSL_SEEDS`).

| Family | Population | What it tests |
|---|---|---|
| herd high | vendor A 40% at correlation 0.90, vendor B 15% at 0.30, shock 5% | a strong herd |
| herd mid | 30% at 0.75, 15% at 0.30, shock 5% | a moderate herd |
| herd low | 20% at 0.65, 15% at 0.30, shock 4% | a weak herd near the label threshold |
| mixed | two vendors of 25% each at 0.80 and 0.20 | two vendors, one destabilising |
| rl emergent | 48 independently trained RL traders, no vendor signal | herding that is learned, not imposed |
| evader | the strong herd rotating three cohorts | evasion of correlation based tools |
| ignition | 20% vendor at 0.65 plus an 8% colluding cluster igniting at step 295 | manipulation |
| persona llm | 35% of agents on one distilled LLM persona | the foundation model monoculture channel |
| vendor fault | 35% vendor at 0.60 with the model misfiring for 25 steps | a faulty third party model (the kill switch case) |
| liquidity withdrawal | the herd with liquidity providers cutting to 30% after the shock | the IMF channel |
| misinformation | the herd with a false shock retracted after 20 steps | disinformation |
| quiet (8) | 25% and 15% vendors at 0.45 and 0.25, no shock | false alerts and the conformal calibration |
| holdout herd (3) | 150 agents, three vendors (25, 20, 15% at 0.85, 0.70, 0.30), shock at step 400, higher impact | a different population, never calibrated on |
| holdout quiet (2) | 150 agents, three vendors, no shock | held out false alerts |
| question | the case the policy question names | the direct answer |
| empirical, calibrated, hybrid | from accepted data (section 11) | your market |

### Ground truth

An agent is destabilising when its vendor's correlation is at least `rho_crit` (0.60) and the vendor's share at least `share_crit` (0.10); manipulators always; the faulty vendor's agents during a fault episode; RL traders when their learned policies converged and amplified the shock; custom agents by their template's label (true, false, or auto, section 6). Counterfactual attribution (section 10) is the behavioural ground truth, checked against the structural one.

### Families of your own (`FAM`)

A family is a JSON document. Only `name` is required.

| Key | Meaning | Bounds |
|---|---|---|
| `name`, `note` | identifier (lower case, digits, underscores), description | 3 to 32 characters |
| `seeds` | scenarios in the family | 1 to 5 |
| `generator` | one of the generators above except hybrid | |
| `vendor_shares`, `vendor_rhos` | up to three vendors | each share 0 to 0.45, sum at most 0.70; correlation 0 to 0.95 |
| `shock_size`, `shock_time` | | 0 to 0.10; 50 to 900 |
| `n_agents`, `t_steps` | | 40 to 200; 200 to 1000 |
| `frac_fundamental` | | 0.05 to 0.40 |
| `kappa`, `sigma` | price impact, noise | 0.005 to 0.03; 0.005 to 0.02 |
| `evader_cohorts`, `evader_period` | | 0 to 8; 1 to 20 |
| `manipulator_share`, `ignition_time`, `ignition_len`, `ignition_size` | | 0 to 0.15; any step; 2 to 40; 1 to 12 |
| `persona`, `persona_share`, `persona_noise` | momentum follower, trend vol capped, contrarian | 0 to 0.45; 0.05 to 1 |
| `rl_share` | | 0 to 0.45 |
| `vendor_fault_time`, `vendor_fault_len`, `vendor_fault_signal` | | any step; 5 to 100; minus 6 to 6 |
| `liquidity_withdrawal_time`, `liquidity_withdrawal_scale` | | any step; 0 to 1 |
| `false_shock_len` | | 0 to 80 |
| `custom_agents` | `[{"agent": name, "share": x}]` | each 0.02 to 0.45 |
| `quiet`, `holdout` | | booleans |

Every population must leave at least 5% for noise traders. Values outside the bounds are clamped and each clamp is reported; reserved names, unknown keys and impossible timings are refused with the reason. Seeds derive from the definition's hash, so a family always reproduces. Stored families carry author, time and sha256; enabled ones join every plan, enter the Gate 1 hash and are written to the ledger. `python -m hsl.families validate | expand | template`; `--family file.json` on the command line.

---

## 6. Agents

| Class | Behaviour |
|---|---|
| Noise traders | Independent standard normal flow each step. |
| Fundamentalists | Trade toward the fundamental value, flow proportional to the mispricing; the liquidity providers. |
| Vendor clusters | Read the vendor's shared signal (momentum plus the vendor factor), blended with idiosyncratic noise by the vendor's correlation. |
| RL traders | 48 agents trained once on quiet markets with double Q learning, SARSA(λ) and advantage actor critic; act on a discretised state of momentum and volatility; policy convergence and momentum slope are measured after the run. |
| LLM personas | A policy table over fifteen market states (three volatility regimes by five momentum buckets), distilled once from a model at planning or from a documented offline surrogate, hashed and bound at Gate 1. |
| Manipulators | Sell `ignition_size` for `ignition_len` steps from `ignition_time`, then buy back half. |
| Custom templates | Defined in the workshop, below. |

### Agent templates of your own (`AGT`)

A template is a declarative document with no code. Order flow at each step is `clip(sum of coefficient times signal, minus cap, cap) + noise times z`, gated, with an optional burst.

| Signal | Meaning |
|---|---|
| `momentum` | recent mean return over its standard deviation, clipped to plus or minus three |
| `mispricing` | (log price minus fundamental) / 0.02, positive above fundamental |
| `last_return` | the previous step's return over sigma |
| `vol` | recent volatility over normal volatility |
| `crowd` | mean order flow of every agent at the previous step |
| `inventory` | the agent's own decayed cumulative flow |
| `vendor_signal_0`, `_1`, `_2` | a vendor cluster's shared signal (subscribing is the monoculture channel) |
| `time` | steps since the shock |

| Key | Bounds |
|---|---|
| each coefficient | minus 5 to 5 |
| `noise` | 0 to 2 |
| `cap` | 0.5 to 8 |
| `threshold` (act only above it) | 0 to 3 |
| `lag` (momentum and last return read this many steps late) | 0 to 10 |
| `withdraw_if_vol_above` | 1 to 6 |
| `active_from`, `active_until` | step range |
| `burst` (`start`, `len`, `size`) | len 0 to 60; size minus 8 to 8 |
| `destabilising` | true, false or auto |

**Probe** runs one herd market with the template at 20% and reports its signature: mean absolute flow, correlation with momentum, mean pairwise correlation among its members, amplification after the shock, the overshoot push, the drawdown with and without it, the share of steps it was active, and whether auto labelling would mark it destabilising. **Auto** labels the class destabilising when it is large (share at or above `share_crit`), its members act together (mean pairwise correlation at least 0.5) and its flow pushes the price away from fundamental after the shock (the overshoot test), which keeps liquidity provision distinct from herding. Stored templates carry author, time and sha256; a family references one by name; the hash is bound into the battery at Gate 1, the simulator refuses a changed definition and the critic checks the binding. `python -m hsl.agents validate | probe | template`; `--agent file.json`.

---

## 7. Sentinels

Every sentinel produces a stress index over time, a first alert step (the first step the index crosses its alert level), flags per agent at the end, and the flags as they stood at every step (used by targeted rules, so no lookahead).

| Sentinel | Construct | Key parameters |
|---|---|---|
| Volatility trigger (`naive_threshold`) | Rolling volatility over its normal level; flags the most active agents. Scores 1.00 on the conventional fidelity construct by construction. | k 1.8 |
| Correlation clustering (`corr_clustering`) | Mean pairwise flow correlation in a window; flags the largest cluster above a correlation threshold. | window 80, threshold 0.45, min size 8, stress k 1.5 |
| Network community sentinel (`network_sentinel`) | Louvain communities on the thresholded correlation graph; stress is the mass of the densest community; flags its members. | window 80, edge 0.5, min community 8, stride 10 |
| Absorption ratio (`absorption_ratio`) | Share of flow variance absorbed by the first principal component (Kritzman et al.); flags agents with the largest loadings. | window 80, threshold 0.31, loading fraction 0.5 |
| Buy sell imbalance (`imbalance`) | Lakonishok, Shleifer and Vishny herding measure: share of agents on the majority side minus the independent expectation. | window 100, threshold 0.16, agreement 0.85 |
| Endogeneity (`endogeneity`) | Hawkes branching ratio of large move events by profiled maximum likelihood (Filimonov and Sornette); localisation by correlation with the endogenous intensity. | window 150, event multiple 2.0, threshold 0.75 |
| Lead lag ignition sentinel (`lead_lag`) | Lag one lead and follow scores; flags leaders by robust z score and the strongest followers. | window 100, z 3.0, follow fraction 0.5 |
| Tail dependence (`tail_dependence`) | Empirical lower tail dependence between agents' flows (joint extremes); flags the largest cluster of jointly extreme agents. | window 100, quantile 0.15, edge 0.5, alert 0.125, min component 8 |

---

## 8. Intervention rules

Rules act on the market each step through halts (no trading) or throttles (a scale on each agent's flow). Targeted rules read the sentinel's flags as they stood at that step.

| Rule | Mechanism | Jurisdiction basis | Human oversight class |
|---|---|---|---|
| Market wide circuit breaker (`static_circuit_breaker`) | halts everyone for 20 steps when the 15 step return exceeds 3.5% | generic | on the loop |
| Sentinel informed dynamic throttle (`dynamic_throttle`) | scales flagged agents to 10% for 80 steps when the 10 step return exceeds 2.8%; withdrawn if it fires on quiet markets | RTS 6 Art 12 by analogy | in the loop |
| Sentinel informed kill switch (`kill_switch`) | flagged agents cancelled for 120 steps on the same trigger | RTS 6 Art 12 | in the loop |
| LULD style price band (`luld_style_band`) | 5% band around a 25 step reference; limit state for 3 steps then a 20 step pause | LULD plan (US) | out of the loop |
| Market wide circuit breaker (US) (`market_wide_breaker`) | halts at declines of 7, 13 and 20% for 15 steps | Reg NMS Rule 80B style | on the loop |
| Venue volatility interruption (EU) (`venue_volatility_halt`) | halt for 10 steps on a 2% dynamic or 6% static move from a 50 step reference | MiFID II Art 48(5), ESMA guidelines | on the loop |
| Responsive enforcement ladder (`responsive_ladder`) | throttle flagged agents to 40%, escalate to a 15 step halt if the 10 step return still exceeds 3% | responsive regulation | on the loop |
| Learned policy (`learned_policy`) | market wide throttle or halt chosen by a model based reinforcement learning policy under declared costs | advisory | in control |

---

## 9. Everything the platform measures

### Per scenario, per sentinel (the rows behind everything)

| Quantity | Definition |
|---|---|
| Fidelity (vol) | correlation of the stress index with realised rolling volatility; the conventional validation criterion |
| Fidelity (moments) | mean correlation of the stress index with rolling volatility, rolling absolute return and rolling mean pairwise flow correlation |
| Precision, recall, decision F1 | of the end of run flags against the ground truth destabilising set |
| Lead time | shock step minus first alert step (positive is early) |
| False alert | on a quiet scenario, whether the sentinel alerted |
| Peak stress | maximum of the stress index |
| Flagged | number of agents flagged |
| Post shock drawdown | largest drop from the pre shock price after the shock |

### Per sentinel over the battery

Means of the above over herding scenarios (calibration and held out separately), with 95% bootstrap intervals over scenarios (400 resamples), an **evidence grade** (A: at least 12 scenarios and interval half width under 0.10; B: at least 6 and under 0.20; C otherwise), the **false alert rate** over quiet scenarios against the **budget** of 0.25, and **within budget**.

### The decision gap

| Quantity | Definition |
|---|---|
| Fidelity ranking, decision ranking | sentinels ordered by mean fidelity and by mean decision F1 |
| Kendall tau | rank correlation between the two |
| Decision gap | (1 minus tau) / 2, in [0, 1]; 1 is full inversion |
| P(inversion), P(full inversion) | over 400 scenario resamples, the share with tau below zero, and at minus one |
| Gap interval | 2.5th and 97.5th percentiles of the gap over resamples |
| Winner stability | share of resamples in which the leading tool tops decision F1; P(top) and P(within budget pick) per sentinel |
| Multi moment construct | the same under the moments fidelity, where no tool is scored on its own output |

### Certification

The certified sentinel is the highest decision F1 among those whose **conformal guarantee** holds (below) and whose conformal power is at least 0.50. Fallbacks: the best within the empirical false alert budget; then the top of the decision ranking. The basis is recorded.

### Per rule

| Quantity | Definition |
|---|---|
| Mean post shock drawdown untreated and treated | over herding scenarios |
| Containment | 1 minus treated over untreated drawdown, with interval and grade; also by family |
| Dislocation probability untreated and treated | share of scenarios with drawdown above 0.10 |
| False halt rate | share of quiet scenarios in which the rule halted |
| Engagement before the shock | share of scenarios in which the rule acted before the shock |
| Burden by class | mean throttle or halt burden on destabilising agents, others and fundamentalists over 150 steps after the shock |
| Tail containment | 1 minus treated over untreated expected shortfall of the drawdown |
| Withdrawn | the throttle is withdrawn if its quiet market halt rate exceeds the budget |

### Three worlds and RL emergence

The same shock in a quiet market, the herd and under the best rule: post shock drawdown, drawdown path and pre shock volatility ratio. RL emergence: policy convergence (mean pairwise similarity of learned policies) and momentum slope (response of RL flow to momentum), and each sentinel's F1 on the emergent herd.

### Assurance quantities (section 10 gives the methods)

Conformal alpha, calibration count, threshold, achievability, power on calibration and held out herds, held out quiet alert rate; frontier loss curves, optimal intervals, crossovers, loss at the declared weight; Shapley values by group, efficiency residual, flags on the top impact group, tau of flags against impact; truth audit rankings, tau and rank shifts per generator, rank one preservation; dose response drawdown, amplification and dislocation probability by share, curvature, threshold share; red team worst case F1, robustness margin, dislocating trials, bandit arms; injection cases contained; matrix game maximin, minimax, mixed value, mixture, value of mixing; learned policy action shares, coverage, off policy estimates and errors; VaR, ES, GPD shape, scale, tail probability, ES reduction with interval; Kaplan Meier medians and survival at 20 and 60 steps, hazard ratios, log rank p values, Weibull parameters, pre emption probabilities; appraisal tiers, tests, burden ratio, recommendation; report indicators and coverage; calibration parameters, diagnostics and shift; backtest detection rates, leads, quiet alerts, recall, episode containment, walk forward regret; autonomy gates, backing rates, claim rate.

---

## 10. Assurance stages

**Conformal certification.** For each sentinel, the alert threshold is set on the eight quiet calibration scenarios so that the false alert probability on a new exchangeable quiet scenario is at most alpha (0.25) by a finite sample bound; the guarantee is achievable when the calibration count allows it; power is the detection rate on herds at that threshold; the held out quiet rate is the empirical check of exchangeability.

**Supervisory cost frontier.** Loss = c times false alert (halt) rate plus (1 minus c) times miss (dislocation) rate, swept over c from 0 to 1; the optimal sentinel and rule on each interval, the crossovers, and the loss at the declared weight c = 0.5.

**Counterfactual attribution.** Shapley values of the post shock drawdown by agent group, from silencing coalitions under common random numbers; the efficiency residual; each sentinel graded on the share of its flags on the top impact group and the rank correlation of its flag rates with impact.

**Truth dependence audit.** The reduced battery re run under alternative generators (shared signal, imitation, voter, square root impact); rankings, tau against the reference, rank shifts, whether rank one survives.

**Concentration dose response.** Drawdown, amplification and dislocation probability as the dominant vendor's share rises at fixed correlation; quadratic curvature, R squared gain over linear, the share at which dislocations become the likelier outcome.

**Learned policy and off policy evaluation.** Trajectories logged under an epsilon soft behaviour policy; a tabular model fitted by counts; value iteration under declared halt and throttle costs; the policy scored as a rule. Every rule's value estimated from the logged data by per decision importance sampling, a clipped doubly robust estimator and the fitted model, each compared with the simulated on policy value; mean absolute errors and the closest estimator.

**Tail risk.** Value at risk and expected shortfall of the untreated drawdown at level 0.9; a generalised Pareto fit of the excesses over the 70th percentile with the count of excesses; each rule's ES reduction with a bootstrap interval.

**Survival.** Time to dislocation (first crossing of the 10% threshold after the shock) with censoring: Kaplan Meier per arm (untreated and each rule), median and survival at 20 and 60 steps, a Weibull baseline, a ridge stabilised Cox model with hazard ratios per rule against the untreated market (share and correlation per standard deviation), a log rank test per rule, and per sentinel pre emption probability and median alert step.

**Red team.** A UCB1 bandit over evasion arms (cohorts, period, correlation, share) searching for the lowest decision F1 of the certified sentinel while the market still dislocates; the robustness margin; every sentinel scored on every trial. An injection suite of eleven cases against the planner, persona distillation, the drafter, ASK and the ledger; every case must be contained.

**Matrix game.** Sentinels against the dislocating evasions: the maximin sentinel, the adversary's best counter, the mixed strategy value by linear programme and the value of mixing.

**Regulatory options appraisal.** Each rule as an instrument on an enforcement ladder (monitor and warn, targeted throttle, targeted kill, price band or venue halt, market wide halt), with its human oversight class and legal basis, tested for containment of at least 0.30, false halts within 0.25 and, for targeted rules, a burden on non destabilising agents of at most half the burden on destabilising ones; the lowest tier passing all three is recommended.

**Reports coverage.** Fifteen needs flagged by the FSB, IOSCO, the Bank of England and the IMF, each answered with a figure, answered in part, or stated as needing firm reporting; the indicators of IOSCO 2026 Table 7 and the FSB 2025 third party indicators computed from the run (adoption share, vendor Herfindahl index and top share, substitutability proxy, dislocation threshold share, herd against quiet channel, persona input to output sensitivity, incident frequency and severity, sentinel performance and held out drift); a data gaps register of five indicators the sandbox cannot supply.

**Calibration shift and backtests.** Section 11.

---

## 11. Observed data

### The data desk

Accepts CSV or JSON up to 25 MB and 250,000 rows, by upload or connector. The schema needs a timestamp (or step) column and a price (or return) column; optional participant and flow columns; optional `event` (a stress episode in progress), `label` (a known destabilising participant) and `vendor` (the model provider each participant trades on) columns. The quarantine checks size and type, text only, the schema, spreadsheet formula characters (refused), personal identifiers (refused, not redacted), and records a sha256. Classifications: public and synthetic rows may enter an evidence pack; licensed and pseudonymised rows stay in the run directory and only hashes and aggregates leave. Up to twenty datasets wait for the next plan; rows are persisted under `data/` in the run directory with an index.

### Connectors

Bloomberg (Desktop API or B-PIPE through `blpapi`, licensed), LSEG Data Library (licensed), Alpha Vantage, FRED, ECB Data Portal, Bank of England database, and a replay fixture from `sample_data`. All return one price series per fetch and pass the same quarantine. Off unless `HSL_CONNECTORS=on`; remote hosts must be https and on `HSL_EGRESS_ALLOWLIST`; no cross host redirects; 20 second timeout; 20 MB cap; keys from `HSL_KEY_<SOURCE>` only.

### What accepted data does

1. **Anchoring**: observed volatility, kurtosis, volatility clustering and drawdown against the battery's quiet family, as ratios with a band of 0.5 to 2.
2. **Empirical family**: two held out scenarios with the largest observed drop as the shock and the observed volatility.
3. **Calibration**: volatility; the shock from the 90th percentile of rolling 80 step drawdowns; price impact from the regression of returns on aggregate flow; the momentum window from the past window that best predicts the next return; the fundamentalist fraction from the speed of reversion toward a 50 step reference; the vendor split observed from the `vendor` column where the data carries one (shares by actual provider and within provider correlations), otherwise inferred from Louvain communities of the flow correlation matrix. Clamped to the planner's bounds, every clamp reported, the fit hashed into the ledger. Two families follow: **calibrated** (fitted parameters, generator ground truth) and **hybrid** (the observed path as the news). The **calibration shift** is the rank correlation between the decision ranking on the demonstration herds and on the calibrated families, and whether rank one survives.
4. **Observed window**: with participant flows, the sentinels run on the real flows and report counts and shares only, above a query set size of five.
5. **Backtests**: episodes from an event column or from window drawdowns above 5%; per sentinel, detected or not, lead in steps, peak stress, alerts per 100 quiet steps, recall on labelled positives (never precision, because the tape does not give the negatives); per rule, containment on each episode replayed as a hybrid market; and **walk forward** validation of the certification over interleaved seed ordered folds (the tool certified on earlier folds scored on the next, its regret against the best tool there, and how often it was still the best).

---

## 12. Governance

**Gates and roles.** A preparer and an approver, who must differ (`HSL_FOUR_EYES`), each with a mandatory function (the preparer's before a plan, the approver's at each gate). `HSL_DEV_MODE=on` accepts `Developer1` and `Developer2` as the two identities and as their functions without a register entry, marks every gate entry and signature as dev mode, and is never for production. With `HSL_REGISTER` set, the approver is checked against a register of regulated persons (name or individual reference number; active; within validity dates; holding an SMF, PRA SMF or certified function) and the match is recorded on the gate entry, in the ledger, the briefing signatures and the transparency record; an approver not on the register cannot approve. Behind a proxy (`HSL_AUTH_MODE=header`) identities come from the identity header and roles from the role header; `HSL_APPROVERS` restricts who may approve. Each person may record an SMF or certified function; it goes onto every gate entry, into the approvals file, the briefing signatures and the transparency record.

**Ledger.** Every event, gate, refusal and release is an HMAC signed, hash chained entry (`HSL_SECRET`); `python -m hsl.ledger verify ledger.jsonl` replays it. An ephemeral key is generated with a warning when none is set.

**Critic.** Thirty one checks before Gate 2 arms: the summary recomputed from the rows; ranking heads; the gap recomputed; ranges; intervals containing point estimates; rule arithmetic and no lookahead; autonomy bookkeeping; the battery hash against the Gate 1 approval; held out families scored separately; the ledger replaying; every number in the briefing and in the transparency record present in the artefacts at printed precision; provenance; conformal thresholds recomputed; Shapley efficiency; frontier endpoints; injection containment; truth audit ranges; adversarial search bounds; survival monotonicity and Cox convergence; ES at least the mean; persona and agent hash bindings; risk coherence; matrix game bounds; learned policy ranges; the lowest eligible tier recommended; dataset hashes and classifications; the security posture; backtest bookkeeping.

**Evidence pack.** A zip with a manifest: artefacts, rows, autonomy, network, battery, ledger, briefing (markdown and html), approvals, meta, critic report, transparency record, exchange record, security framework document, and the rows of packable datasets.

**Transparency record.** In the structure of the UK Algorithmic Transparency Recording Standard: tier 1 summary; tier 2 owner and responsibility (the approver as senior responsible owner, with function), description and rationale, decision making process, tool specification, data, risks and mitigations, impact assessments. Generated from the artefacts and vetted by the critic; a draft for the accountable owner.

**Exchange record.** A fixed schema (`hsl.exchange/1`) carrying the indicators, the certified sentinel, the decision gap, the recommendation, oversight classes and needs coverage for another authority to read.

---

## 13. Security posture

`SEC` and `python -m hsl.security posture` check eighteen controls, each naming its chapter of Anderson's Security Engineering, 3rd edition; a failing control blocks release.

Ledger signing key configured; identities from an authenticating proxy; development mode off; approvers tied to a register of regulated persons; separation of duty at the gates; service bound to the loopback or behind a proxy; debug off; outbound connectors disabled or limited to an allowlist; model provider endpoint secure; credentials in the environment only; vendored front end assets matching their sha256 manifest (`python -m hsl.security manifest` after any front end change); upload size and type limits; ASK rate limit; security headers on every response; no confidential or personal data in the sandbox; licensed or pseudonymised rows never leaving the run directory; per participant results only above the query set size; every step in the signed ledger. `docs/SECURITY_FRAMEWORK.md` gives the argument.

---

## 14. The model layer

Off by default; every path is deterministic without a model. With one, it is called single shot, server side, with fixed prompts, in four places: planning families from the question within hard bounds, distilling personas, rephrasing the briefing (every number vetted; a draft with a figure absent from the artefacts is discarded) and phrasing ASK answers. The model never computes a metric or chooses a gate.

| `HSL_LLM_PROVIDER` | Reaches | Settings |
|---|---|---|
| `anthropic` | the Anthropic API or a gateway proxying it | `ANTHROPIC_API_KEY`, `HSL_MODEL`, `HSL_API_BASE` |
| `openai` | any OpenAI compatible endpoint: institutional gateways, Mistral, Groq, Together, Bedrock's compatible endpoint, Azure AI Foundry inference, local servers (vLLM, llama.cpp, Ollama, LM Studio) | `HSL_LLM_BASE`, `HSL_LLM_MODEL`, `HSL_LLM_KEY` |
| `azure` | Azure OpenAI Service (the platform behind Microsoft Copilot for enterprises) | endpoint, deployment, key or bearer token, `HSL_LLM_API_VERSION` |
| `gemini` | the Google Gemini API | `HSL_LLM_MODEL`, `HSL_LLM_KEY` |
| `custom` | any JSON API, by request template, headers and response path | `HSL_LLM_BASE`, `HSL_LLM_TEMPLATE`, `HSL_LLM_HEADERS`, `HSL_LLM_RESPONSE_PATH` |
| `local` | a model installed by the authority, loaded from a directory with transformers | `HSL_LLM_PATH` |

Remote endpoints must be https and, when an allowlist is configured, on it; loopback may use http; responses are capped at 4 MB; HSL never downloads a model.

---

## 15. ASK, the run oracle

Questions are matched to intents and answered from the artefacts of the current run; sources are listed beside the answer; a model, when configured, phrases only. Intents: certify (which sentinel should be certified), a sentinel by name, the decision gap, a scenario, a rule, the autonomy gate, the ledger, red team, conformal, attribution, frontier, truth audit, concentration, personas, survival, tail risk, reports and indicators, game, learned policy, appraisal, the direct answer to the policy question, backtests. Rate limited per identity (`HSL_ASK_RATE` per minute).

---

## 16. Configuration reference

| Variable | Default | Meaning |
|---|---|---|
| `HSL_HOST`, `HSL_PORT` | 127.0.0.1, 8050 | bind address |
| `HSL_RUNS_DIR` | runs | run directories, the family library, the agent registry |
| `HSL_SECRET` | ephemeral | ledger signing key |
| `HSL_AUTH_MODE` | open | `header` behind a proxy |
| `HSL_USER_HEADER`, `HSL_ROLE_HEADER` | X-Remote-User, X-HSL-Role | identity and role headers |
| `HSL_APPROVERS` | any | comma list of approver identities |
| `HSL_REGISTER`, `HSL_REGISTER_REQUIRED` | none | register of regulated persons approvers are checked against; required when set |
| `HSL_DEV_MODE` | off | accept Developer1 and Developer2 at the gates for development and demonstrations |
| `HSL_FOUR_EYES` | on | preparer and approver must differ |
| `HSL_ASSURANCE` | full | `light` for a short run, `demo` for the three minute demonstration |
| `HSL_SEEDS` | 3 | seeds per demonstration family |
| `HSL_TICK_PACE` | 0.0008 | seconds per streamed step |
| `HSL_ASK_RATE` | 20 | ASK questions per identity per minute |
| `HSL_CONNECTORS` | off | outbound connectors |
| `HSL_EGRESS_ALLOWLIST` | empty | hosts connectors and models may reach |
| `HSL_KEY_<SOURCE>` | | connector credentials |
| `HSL_UPLOAD_MAX_MB` | 25 | upload cap |
| `HSL_LLM`, `HSL_LLM_PROVIDER` and the provider variables | auto, off | section 14 |

---

## 17. Command line reference

`python -m hsl.orchestrator` with `--question`, `--outdir`, `--battery` (replay a battery.json), `--approve-battery`, `--approve-briefing`, `--preparer`, `--approver`, `--preparer-role`, `--approver-role`, `--family` (repeatable), `--families-store`, `--agent` (repeatable), `--data` (repeatable), `--data-class`, `--four-eyes`, `--llm`.

`python -m hsl.families validate | expand | template [--agent file] [--store dir]`; `python -m hsl.agents validate | probe | template`; `python -m hsl.security posture | manifest | verify`; `python -m hsl.ledger verify <ledger.jsonl>`; `python figures.py <run dir> <out dir>` for the figures.

---

## 18. Files a run produces

`artefacts.json` (every measured quantity), `rows.json` (per scenario per sentinel rows), `aut.json`, `net.json`, `tapes.json`, `three.json`, `battery.json` (the specs, persona tables, agent definitions and observed series for replay), `ledger.jsonl`, `approvals.json`, `meta.json`, `critic.json`, `briefing.md` and `briefing.html`, `atrs_record.md` and `.json`, `exchange_record.json`, `security_framework.md`, `data/` (persisted datasets with an index), `evidence_pack.zip`, and the figures.

---

## 19. Limitations

Everything is a comparative ranking on a declared synthetic battery. The sandbox measures the consequence of a structure; from supplied data it estimates the structure present in that data (observed by provider when a vendor column is supplied, otherwise inferred from correlated flows, which cannot distinguish a shared model from a shared information source or a shared hedging need); it cannot measure how prevalent that structure is across the market, which is what firm reporting supplies. Real data calibrates and backtests timing and workload but cannot supply the ground truth a certification needs, so precision on observed data is never reported. The RL population is trained once and shared across scenarios. The Bloomberg and LSEG connectors are written against their published APIs and exercised only through the replay path. The learned policy is advisory. A model, where used, plans and phrases; it never decides.
