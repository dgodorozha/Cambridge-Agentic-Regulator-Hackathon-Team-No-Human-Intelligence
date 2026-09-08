# Algorithmic transparency record: Herding Scenario Lab

Structure: Algorithmic Transparency Recording Standard (UK), structure of the published template. Status: draft for the accountable owner's review; not a published record. Run 20260907-160809-0939, 2026-09-07, HSL 3.9.2.

## Tier 1

- **name**: Herding Scenario Lab (HSL)
- **description**: A decision first sandbox in which a public authority stress tests candidate surveillance sentinels and intervention rules against synthetic AI agent markets and certifies them on decision accuracy rather than aggregate fidelity. Outputs are comparative rankings on a declared scenario battery with intervals; the tool never trades, never touches live market data and never recommends live intervention.
- **website url**: to be completed
- **contact email**: to be completed

## Tier 2

### Owner and responsibility

- **organisation**: to be completed
- **team**: to be completed
- **senior responsible owner**: R. Ahmed
- **senior responsible owner role**: SMF24 Chief Operations
- **senior responsible owner register**: SMF24 Chief Operations, reference RXA01234, Authority HR register; FCA Financial Services Register checked 2026-09-01
- **record prepared by**: D. Godorozha
- **record prepared by role**: to be completed
- **external supplier involvement**: None. No external model is configured; every path runs deterministically from the artefacts.
- **data access processing or sharing**: No data leaves the authority's environment; the run is synthetic and self contained.

### Description and rationale

- **detailed description**: Version 3.9.2. Each run plans a battery of synthetic markets (51 scenarios in 18 families on this run), simulates them, scores 8 surveillance sentinels on aggregate fidelity and on decision accuracy (which agents are destabilising), scores 8 intervention rules on containment and false halts, and reports the decision gap between the two rankings with a bootstrap probability of inversion, a conformal false alert guarantee, counterfactual attribution, a truth dependence audit, a cost frontier, tail risk and survival measures, a red team and a regulatory options appraisal.
- **scope**: Certification of surveillance tools and calibration of intervention rules for agentic herding and market manipulation, in market monitoring, policy design and supervision. Out of scope: live surveillance, enforcement decisions about any firm or person, and any use with real personal or confidential supervisory data.
- **benefit**: Replaces certification on aggregate fidelity, which on this run ranks the tools close to the reverse of their decision accuracy (decision gap 0.68, probability of inversion 0.90), with certification on the decision the tool exists to inform, with intervals, a guarantee and a replayable trail.
- **previous process**: Back tests against historical episodes containing almost no agentic herding, and validation of synthetic environments on aggregate statistics.
- **alternatives considered**: Do nothing (the untreated herd is the baseline in every run); monitor and warn without intervention (the non regulatory option in the appraisal); a fixed battery instead of a model planned one (the fixed battery is the fallback whenever no model is configured or its plan fails validation).

### Decision making process

- **process integration**: The tool sits before certification. A policy officer poses a question; the battery is approved at Gate 1 by a named approver; the run executes; the critic verifies; the briefing is released at Gate 2 by a named approver. The briefing is advisory input to a supervisory decision taken by people.
- **provided information**: A ranked evidence graded briefing, the artefacts with intervals, the signed ledger and the evidence pack; on this run the tool certified within the false alert budget is Tail dependence (tail concordance).
- **frequency and scale of usage**: Per policy question; each run is a few minutes on one machine.
- **human decisions and review**: Two mandatory human gates with refusal and recorded reasons; four eyes between preparer and approver; an emergency stop that halts execution and seals the partial ledger; the autonomy gate reports how much execution the evidence would back and defaults to none.
- **required training**: Familiarity with the decision gap, the false alert budget, the evidence grades and the limitations section of the briefing; the ASK page answers questions from the artefacts only.
- **appeals and review**: Every figure is recomputed from per scenario rows by the critic and can be replayed from the evidence pack by a third party; gate refusals and reasons are in the ledger.

### Tool specification

- **system architecture**: Planner, scenario synthesiser (agent based market simulator with RL traders and distilled LLM personas), sentinels under test, intervention harness, evaluator, attribution, audits, red team, critic, drafter, signed ledger. Pure Python; runs offline.
- **phase**: Prototype (hackathon build); pilot with delayed pseudonymised venue data is the next phase.
- **maintenance**: Versioned code with a changelog; every run records the software and library versions.
- **models**: Tabular Q learning traders; distilled persona policy tables (hashed); eight sentinels (volatility, correlation, network, absorption ratio, imbalance, endogeneity, lead lag, tail dependence); a model based learned intervention policy (advisory).
- **software versions**: hsl_version 3.9.2, python 3.12.3, numpy 2.4.4, scipy 1.17.1, platform Linux-6.18.44-fc-v24-x86_64-with-glibc2.39

### Data

- **source data name**: Synthetic scenario battery generated by the HSL simulator, plus observed datasets brought through quarantine: labelled_flows.csv (public, sha256 bf47b2157e7df1fd)
- **data modality**: Simulated prices, returns and per agent order flows
- **data description**: 51 scenarios, seeds recorded, battery hash 4bf2b1c1e6282df0; generators hybrid, shared_signal.
- **data quantities**: 51 runs of up to 600 steps and up to 150 agents
- **sensitive attributes**: None. No personal data, no confidential supervisory information, no proprietary datasets.
- **data completeness and representativeness**: Synthetic by design; the battery is anchored to published ranges and includes held out families with a different population; the truth dependence audit reports whether rankings survive a change of generator.
- **source data url**: to be completed
- **data collection**: Generated at run time from recorded seeds.
- **data cleaning**: Not applicable.
- **data sharing agreements**: None required.
- **data access and storage**: Run directory under the authority's control; evidence pack with a manifest.

### Risks mitigations and impact assessments

| Risk | Mitigation |
|---|---|
| Sim to real gap | Synthetic only; comparative rankings with intervals, never forecasts; provenance and anchoring recorded. |
| Certification that only holds under one generator | Truth dependence audit under alternative generators; the briefing states whether rank one survives. |
| False alert budget that is only an estimate | Conformal threshold with a finite sample guarantee at 0.25 on 8 calibration scenarios. |
| A certified tool an adversary can evade | Budgeted adversarial search and the sentinel against evader game; robustness margin in the briefing. |
| Prompt injection through model facing surfaces | Injection suite on every run; 11 of 11 cases contained on this run; the critic requires every case contained. |
| Hallucinated figures in prose | Every number is computed, not generated; the critic vets every number in the briefing and in this record against the artefacts at printed precision. |
| Overreliance and false confidence | Evidence grades and limitations in every briefing; named human release; advisory only. |
| Interruption of legitimate participants by a rule | Burden by participant class, false halt rate, proportionality test in the options appraisal; the appraisal recommends tier 4 (market wide halt). |

| Impact assessment | Description | Date | Link |
|---|---|---|---|
| HSL critic report | Independent checks recomputed from the per scenario rows at release | 2026-09-07 | critic.json in the evidence pack |
| Ledger replay | Hash chained, HMAC signed record of every step and gate | 2026-09-07 | ledger.jsonl in the evidence pack |

Every figure above is read from the artefacts of the run and vetted by the critic; blank fields are for the adopting authority to complete.
