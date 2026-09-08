# HSL supervisory briefing

**Run.** 20260907-160809-0939

**Policy question.** Would a sentinel informed dynamic throttle have contained a flash dislocation with 40 per cent of agents on one foundation model vendor, and which surveillance candidate should be certified?

**Prepared by.** D. Godorozha
**Gate 1 (battery sign off).** R. Ahmed (SMF24 Chief Operations) at 2026-09-07T16:08:28+00:00; on the register as SMF24 Chief Operations at Demonstration Authority, reference RXA01234, checked 2026-09-07
**Gate 2 (release).** R. Ahmed (SMF24 Chief Operations) at 2026-09-07T16:12:14+00:00; on the register as SMF24 Chief Operations at Demonstration Authority, reference RXA01234, checked 2026-09-07
**Critic verification.** PASSED (31 independent checks against the run artefacts and the ledger).

## Direct answer to the question

The case the question names was added to the battery as its own family (vendor share 0.40; mechanisms persona) and every figure below for it is measured on that family.

Sentinel informed dynamic throttle: containment 0.21 across the herding scenarios and -0.64 on the question's own family; false halt rate 0.00; dislocation probability after treatment 0.36; human oversight as deployed: human in the loop.

The certified sentinel on this battery is Tail dependence (tail concordance) (conformal basis); the appraisal recommends tier 4 (market wide halt): Market wide circuit breaker.

## Headline

The tool that best reproduces aggregate market statistics (Volatility trigger, fidelity 1.00) is not the tool that best identifies destabilising clusters (Tail dependence (tail concordance), decision F1 0.68, 95% interval [0.54, 0.81], grade B). Certification on aggregate fidelity alone would select the wrong surveillance tool for the supervisory decision in this battery.

Certification. Tail dependence (tail concordance) is conformally certified at level 0.25 given 8 exchangeable calibration scenarios: its alert threshold is set by the conformal rule, so the false alert probability on a new quiet scenario like those is at most 0.25 by construction, and among the sentinels with that guarantee and conformal power of at least 0.50 it has the highest decision F1 (0.68). Its empirical quiet alert rate is 0.25; a point estimate near the budget is exactly where the finite sample bound, not the estimate, should adjudicate. 

Winner stability. Over the 400 scenario resamples, Tail dependence (tail concordance) is the top tool by decision F1 in 98% of them and Tail dependence (tail concordance) is the within budget pick in 57% of them. A winner that changes with the resample is a reason to certify the procedure, not the tool; the number says how often this battery's answer would repeat.

Decision gap 0.68 (Kendall tau -0.36) under the conventional fidelity construct; 0.50 (tau +0.00) under the multi moment construct. Across 400 scenario resamples the rankings invert with probability 0.90 (conventional) and 0.30 (multi moment). With 8 tools tau takes few values, so the resampled probability is the number to quote.

## Surveillance candidates: aggregate fidelity versus decision accuracy

| Sentinel | Fidelity (vol) | Fidelity (moments) | Decision F1 | 95% interval | Grade | Precision | Recall | Alert lead vs shock | False alert rate |
|---|---|---|---|---|---|---|---|---|---|
| Volatility trigger | 1.00 | 0.70 | 0.25 | [0.17, 0.33] | A | 0.17 | 0.50 | 13 | 0.00 |
| Correlation clustering | 0.21 | 0.45 | 0.34 | [0.20, 0.47] | B | 0.30 | 0.39 | 70 | 0.00 |
| Network community sentinel | 0.15 | 0.36 | 0.41 | [0.27, 0.53] | B | 0.32 | 0.56 | 223 | 0.12 |
| Absorption ratio | 0.22 | 0.48 | 0.57 | [0.48, 0.63] | A | 0.44 | 0.80 | 192 | 0.38 |
| Buy sell imbalance (LSV herding measure) | 0.20 | 0.37 | 0.42 | [0.28, 0.58] | B | 0.42 | 0.43 | 200 | 0.00 |
| Endogeneity (Hawkes branching ratio) | 0.21 | 0.24 | 0.30 | [0.17, 0.42] | B | 0.27 | 0.35 | 46 | 0.12 |
| Lead lag ignition sentinel | 0.10 | 0.21 | 0.41 | [0.30, 0.53] | B | 0.39 | 0.47 | 27 | 0.00 |
| Tail dependence (tail concordance) | 0.19 | 0.39 | 0.68 | [0.54, 0.81] | B | 0.65 | 0.72 | 227 | 0.25 |

Ranking by aggregate fidelity: Volatility trigger > Absorption ratio > Endogeneity (Hawkes branching ratio) > Correlation clustering > Buy sell imbalance (LSV herding measure) > Tail dependence (tail concordance) > Network community sentinel > Lead lag ignition sentinel.

Ranking by decision accuracy: Tail dependence (tail concordance) > Absorption ratio > Buy sell imbalance (LSV herding measure) > Lead lag ignition sentinel > Network community sentinel > Correlation clustering > Endogeneity (Hawkes branching ratio) > Volatility trigger.

Fidelity constructs. Conventional: correlation of the stress index with realised rolling volatility (the conventional validation criterion; identical to the volatility trigger's own output, so that tool scores 1.00 by construction). Multi moment: mean correlation of the stress index with three realised moments: rolling volatility, rolling absolute return and rolling mean pairwise flow correlation (no candidate is scored against its own output).

Herding versus noise. Three candidates ask whether activity is coordinated and self reinforcing rather than merely loud: the buy sell imbalance herding measure (share of agents on the majority side in excess of independent decisions), the Hawkes branching ratio (share of large moves generated by earlier moves rather than news) and the lead lag ignition sentinel (a small cluster whose orders lead the crowd's next orders, and the crowd that follows).

Lead time is measured from the sentinel's first alert to the shock. A positive lead means the structural vulnerability was flagged before the shock landed; it is a measure of when the cluster became visible, not a forecast of the shock.

## Generalisation: held out, adversarial and emergent families

| Sentinel | Decision F1 (calibration battery) | Decision F1 (held out) | False alert rate (held out) |
|---|---|---|---|
| Volatility trigger | 0.25 | 0.37 | 0.00 |
| Correlation clustering | 0.34 | 0.52 | 0.00 |
| Network community sentinel | 0.41 | 0.73 | 0.00 |
| Absorption ratio | 0.57 | 0.73 | 0.50 |
| Buy sell imbalance (LSV herding measure) | 0.42 | 0.56 | 0.00 |
| Endogeneity (Hawkes branching ratio) | 0.30 | 0.48 | 0.00 |
| Lead lag ignition sentinel | 0.41 | 0.81 | 0.00 |
| Tail dependence (tail concordance) | 0.68 | 0.92 | 0.50 |

On the held out family the decision ranking is Tail dependence (tail concordance) > Lead lag ignition sentinel > Absorption ratio > Network community sentinel > Buy sell imbalance (LSV herding measure) > Correlation clustering > Endogeneity (Hawkes branching ratio) > Volatility trigger and the decision gap is 0.82. Held out scenarios use a different population, shock time and impact coefficient and were never used to set any threshold.

| Sentinel | F1 calibrated bf47b2 | F1 evader | F1 herd high | F1 herd low | F1 herd mid | F1 hybrid bf47b2 | F1 ignition | F1 liquidity withdrawal | F1 misinformation | F1 mixed | F1 persona llm | F1 question | F1 rl emergent | F1 vendor fault |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Volatility trigger | 0.00 | 0.19 | 0.38 | 0.00 | 0.46 | 0.00 | 0.44 | 0.52 | 0.52 | 0.27 | 0.17 | 0.00 | 0.38 | 0.00 |
| Correlation clustering | 0.00 | 0.00 | 0.84 | 0.00 | 0.91 | 0.00 | 0.00 | 0.82 | 0.84 | 0.00 | 0.56 | 0.00 | 0.00 | 0.91 |
| Network community sentinel | 0.00 | 0.00 | 0.70 | 0.00 | 0.75 | 0.00 | 0.00 | 0.67 | 0.78 | 0.71 | 0.70 | 0.84 | 0.00 | 0.72 |
| Absorption ratio | 0.00 | 0.53 | 0.70 | 0.43 | 0.67 | 0.00 | 0.65 | 0.67 | 0.67 | 0.69 | 0.70 | 0.84 | 0.55 | 0.69 |
| Buy sell imbalance (LSV herding measure) | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.87 | 1.00 | 0.00 | 0.95 | 1.00 | 0.89 | 0.49 |
| Endogeneity (Hawkes branching ratio) | 0.00 | 0.17 | 0.55 | 0.21 | 0.22 | 0.00 | 0.12 | 0.74 | 0.88 | 0.24 | 0.66 | 0.00 | 0.00 | 0.49 |
| Lead lag ignition sentinel | 0.00 | 0.66 | 0.82 | 0.00 | 0.79 | 0.00 | 0.61 | 0.84 | 0.73 | 0.23 | 0.00 | 0.71 | 0.00 | 0.34 |
| Tail dependence (tail concordance) | 0.00 | 0.00 | 0.90 | 0.99 | 0.91 | 0.00 | 0.59 | 0.82 | 0.97 | 0.97 | 0.93 | 1.00 | 0.43 | 0.93 |

Adversarial evaders. The dominant vendor rotates three trading cohorts so pairwise flow correlation stays low while its aggregate impact is unchanged. The best decision F1 on that family is 0.66 (Lead lag ignition sentinel). A sentinel certified on the parametric herds alone would not have revealed this.

Emergent herding. Independently trained RL traders (Double Q learning, SARSA(lambda) with function approximation and advantage actor critic) converged to near identical momentum policies: policy convergence 0.74, momentum slope 0.21. No correlation was imposed. Per sentinel decision F1 on the emergent herd: Volatility trigger 0.38, Correlation clustering 0.00, Network community sentinel 0.00, Absorption ratio 0.55, Buy sell imbalance (LSV herding measure) 0.89, Endogeneity (Hawkes branching ratio) 0.00, Lead lag ignition sentinel 0.00, Tail dependence (tail concordance) 0.43.

## Intervention rules: containment on the same battery

| Rule | Post shock drawdown untreated | Post shock drawdown treated | Containment | 95% interval | Grade | Trough containment | Dislocation probability before, after | False halt rate (quiet) | Engaged before the shock | Burden on non destabilising agents | Burden on destabilising agents |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Market wide circuit breaker | 0.128 | 0.087 | 0.32 | [0.16, 0.45] | B | 0.31 | 0.56, 0.22 | 0.00 | 86% | 0.41 | 0.34 |
| Sentinel informed dynamic throttle | 0.128 | 0.101 | 0.21 | [0.02, 0.37] | B | 0.19 | 0.56, 0.36 | 0.00 | 53% | 0.13 | 0.40 |
| Sentinel informed kill switch | 0.128 | 0.120 | 0.07 | [-0.19, 0.32] | C | 0.13 | 0.56, 0.44 | 0.00 | 53% | 0.17 | 0.51 |
| LULD style price band (US) | 0.128 | 0.100 | 0.22 | [0.11, 0.32] | B | 0.19 | 0.56, 0.42 | 0.00 | 39% | 0.13 | 0.12 |
| Market wide circuit breaker (US) | 0.128 | 0.123 | 0.04 | [-0.01, 0.10] | A | 0.10 | 0.56, 0.53 | 0.00 | 39% | 0.08 | 0.06 |
| Venue volatility interruption (EU) | 0.128 | 0.104 | 0.19 | [0.06, 0.31] | B | 0.16 | 0.56, 0.50 | 0.00 | 50% | 0.15 | 0.13 |
| Responsive enforcement ladder | 0.128 | 0.110 | 0.15 | [0.06, 0.22] | A | 0.16 | 0.56, 0.47 | 0.00 | 44% | 0.04 | 0.11 |
| Learned policy (model based RL) | 0.128 | 0.126 | 0.02 | [-0.00, 0.04] | A | 0.01 | 0.56, 0.56 | 0.00 | 22% | 0.03 | 0.03 |

Targeting cost. The targeted rules suppressed fundamentalists at 0.40, against 0.40 for the destabilising cluster. Fundamentalists trade on the same signal and are therefore as correlated with one another as the herd, so a correlation based flag cannot tell a stabilising correlated group from a destabilising one. Suppressing the mean reverting agents removes the force that would otherwise close the dislocation, which is why disconnecting flagged agents can deepen the drawdown rather than contain it.

Every rule that engaged before the shock did so on the herd's own pre shock swings, not on the shock. A rule tripped by endogenous herd volatility is intervening on the structure itself; whether that is desirable is a policy choice the briefing does not make.

Containment is one minus treated over untreated mean post shock drawdown. Trough containment uses the depth of the post shock trough relative to the pre shock price instead. A dislocation is a post shock drawdown above 0.10. Burden is the share of intended order flow suppressed over the 150 steps after the shock; a targeted rule should load it on destabilising agents and spare the rest. Targeted rules act only on flags the sentinel had issued by that step (no lookahead).

Same shock, three worlds: post shock drawdown 0.067 in the quiet market, 0.184 with a 40% single vendor herd and 0.116 with the sentinel informed throttle. The herd market's pre shock volatility is 2.9 times the exogenous noise scale, against 1.3 in the quiet market, so part of the herd's instability is endogenous and present before the shock.

## Autonomy gate: how much execution the evidence can back

| Sentinel | Backed in sample | Auto clear | Auto throttle | Localisation lift | Backed (leave one out) | Out of sample claims |
|---|---|---|---|---|---|---|
| Volatility trigger | 0% | 0% | withdrawn | 0.56 (bar 1.25) | 2% | 1 of 44 (2%) |
| Correlation clustering | 0% | 0% | withdrawn | 1.00 (bar 1.25) | 2% | 1 of 44 (2%) |
| Network community sentinel | 0% | 0% | withdrawn | 1.08 (bar 1.25) | 2% | 1 of 44 (2%) |
| Absorption ratio | 68% | 0% | 68% | 1.50 (bar 1.25) | 73% | 2 of 44 (5%) |
| Buy sell imbalance (LSV herding measure) | 68% | 2% | 66% | 1.42 (bar 1.25) | 73% | 2 of 44 (5%) |
| Endogeneity (Hawkes branching ratio) | 0% | 0% | withdrawn | 0.92 (bar 1.25) | 0% | 0 of 44 (0%) |
| Lead lag ignition sentinel | 41% | 0% | 41% | 1.31 (bar 1.25) | 45% | 2 of 44 (5%) |
| Tail dependence (tail concordance) | 77% | 0% | 77% | 2.21 (bar 1.25) | 82% | 2 of 44 (5%) |

Below the low gate the system stands behind no intervention; above the high gate it may trigger the targeted throttle; the band between escalates to the named supervisor. The throttle is withdrawn, not narrowed, when a tool's localisation cannot beat the flag everyone baseline by the declared margin. The in sample breadth is fitted on the scored scenarios and holds by construction. The leave one out columns refit the gates without each scenario and are the figures to quote.

## Certification with a false alert guarantee

| Sentinel | Calibration quiet scenarios | Guaranteed false alert bound | Conformal threshold | Power, calibration herds | Held out quiet alert rate | Power, held out herds |
|---|---|---|---|---|---|---|
| Volatility trigger | 8 | 0.25 | 1.39 | 0.64 | 0.50 | 0.60 |
| Correlation clustering | 8 | 0.25 | 0.59 | 0.97 | 0.50 | 1.00 |
| Network community sentinel | 8 | 0.25 | 0.62 | 0.97 | 0.50 | 1.00 |
| Absorption ratio | 8 | 0.25 | 0.91 | 0.92 | 0.50 | 1.00 |
| Buy sell imbalance (LSV herding measure) | 8 | 0.25 | 0.34 | 0.83 | 1.00 | 1.00 |
| Endogeneity (Hawkes branching ratio) | 8 | 0.25 | 0.91 | 0.31 | 0.00 | 0.60 |
| Lead lag ignition sentinel | 8 | 0.25 | 0.63 | 0.61 | 1.00 | 1.00 |
| Tail dependence (tail concordance) | 8 | 0.25 | 0.88 | 0.94 | 1.00 | 1.00 |

The conformal rule flags a scenario when its p value against the 8 calibration quiet scenarios is at most 0.25. If a new quiet scenario is exchangeable with the calibration set, the false alert probability is at most 0.25 whatever the sentinel and whatever its score distribution; the smallest achievable level with this calibration set is 0.11. The held out quiet column is the empirical check of exchangeability on a different population and is not covered by the guarantee. Sentinels with an achievable guarantee and conformal power of at least 0.50 on the calibration herds, in decision order: Tail dependence (tail concordance), Absorption ratio, Buy sell imbalance (LSV herding measure), Lead lag ignition sentinel, Network community sentinel, Correlation clustering, Volatility trigger.

## Supervisory cost frontier

Sentinel loss is c times false alert rate plus (1 - c) times (1 - recall); rule loss is c times false halt rate plus (1 - c) times dislocation probability after treatment. The weight c is the supervisor's declared cost of a false alert or false halt relative to a miss.

| Tool | Optimal for c from | to |
|---|---|---|
| Absorption ratio | 0.00 | 0.36 |
| Tail dependence (tail concordance) | 0.37 | 0.47 |
| Volatility trigger | 0.48 | 1.00 |
| Market wide circuit breaker | 0.00 | 1.00 |

At the declared weight c = 0.50 the sentinel with the lowest loss is Volatility trigger (loss 0.25) and the rule with the lowest loss is Market wide circuit breaker (loss 0.11). The sentinel choice switches 2 times across the range of c and the rule choice 0 times; a choice that switches depends on a cost the supervisor has to own.

## Counterfactual attribution: which group moved the market

| Scenario | Impact ordering (Shapley value of post shock drawdown) | Full market drawdown | All groups silenced |
|---|---|---|---|
| Herd high 0 | Vendor A 0.106, Vendor B 0.013 | 0.176 | 0.056 |
| Herd mid 0 | Vendor A 0.032, Vendor B -0.002 | 0.088 | 0.057 |
| Herd low 0 | Vendor B 0.002, Vendor A -0.002 | 0.044 | 0.043 |
| Mixed 0 | Vendor A 0.027, Vendor B 0.009 | 0.102 | 0.066 |
| RL emergent 0 | Vendor A 0.010, RL policy 0.006 | 0.079 | 0.063 |
| Evader 0 | Vendor A 0.090, Vendor B 0.017 | 0.161 | 0.054 |
| Ignition 0 | Vendor A 0.011, Vendor B 0.001, manipulator -0.003 | 0.057 | 0.048 |
| Persona LLM 0 | LLM persona 0.116, Vendor A 0.003 | 0.173 | 0.054 |
| Vendor fault 0 | Vendor A 0.036, Vendor B 0.008 | 0.074 | 0.029 |
| Liquidity withdrawal 0 | Vendor A 0.340, Vendor B 0.026 | 0.433 | 0.067 |
| Misinformation 0 | Vendor A 0.046, Vendor B 0.008 | 0.108 | 0.053 |
| Calibrated bf47b2 0 | Vendor A 0.028, Vendor B 0.002 | 0.187 | 0.157 |
| Hybrid bf47b2 0 | Vendor A 0.032, Vendor B 0.010 | 0.120 | 0.077 |
| Question 0 | Vendor A 0.015, Vendor B 0.000 | 0.120 | 0.104 |

| Sentinel | Share of flags on the highest impact group | Rank correlation of flag rates with impact |
|---|---|---|
| Volatility trigger | 0.30 | n/a |
| Correlation clustering | 0.80 | 1.00 |
| Network community sentinel | 0.59 | 1.00 |
| Absorption ratio | 0.47 | 0.44 |
| Buy sell imbalance (LSV herding measure) | 0.84 | 0.75 |
| Endogeneity (Hawkes branching ratio) | 0.39 | 0.20 |
| Lead lag ignition sentinel | 0.58 | 0.58 |
| Tail dependence (tail concordance) | 0.75 | 0.73 |

Each group's Shapley value is its average marginal contribution to the post shock drawdown over every order of silencing the other groups, under common random numbers; the values add up to the drawdown removed when every group is silenced, which the critic checks. This is the behavioural ground truth: it ranks groups by what removing them does, not by how they were generated. A sentinel whose flags land on the highest impact group is answering the supervisory question; 14 scenarios, one per family, were attributed.

## Truth dependence: does the ranking survive a change of generator

| Generator | Decision ranking | Rank correlation with shared signal | Largest rank shift | Rank one preserved |
|---|---|---|---|---|
| Shared signal | Tail dependence (tail concordance) > Absorption ratio > Lead lag ignition sentinel > Network community sentinel > Volatility trigger > Correlation clustering > Buy sell imbalance (LSV herding measure) > Endogeneity (Hawkes branching ratio) | reference | 0 | reference |
| imitation | Tail dependence (tail concordance) > Absorption ratio > Lead lag ignition sentinel > Network community sentinel > Correlation clustering > Volatility trigger > Buy sell imbalance (LSV herding measure) > Endogeneity (Hawkes branching ratio) | 0.93 | 1 | yes |
| voter | Tail dependence (tail concordance) > Absorption ratio > Correlation clustering > Volatility trigger > Lead lag ignition sentinel > Network community sentinel > Buy sell imbalance (LSV herding measure) > Endogeneity (Hawkes branching ratio) | 0.64 | 3 | yes |
| square root impact | Tail dependence (tail concordance) > Absorption ratio > Lead lag ignition sentinel > Network community sentinel > Buy sell imbalance (LSV herding measure) > Correlation clustering > Endogeneity (Hawkes branching ratio) > Volatility trigger | 0.71 | 3 | yes |

The reduced battery (9 scenarios) was re run with herding produced by imitation within a vendor cluster and with square root price impact, and the sentinels were re ranked by decision F1 under each. Tail dependence (tail concordance) holds rank one under every generator.

## Concentration dose response

| Dominant vendor share | Post shock drawdown | Amplification over the quiet baseline | Dislocation probability |
|---|---|---|---|
| 0.10 | 0.073 | 1.1 | 0.00 |
| 0.15 | 0.080 | 1.2 | 0.00 |
| 0.20 | 0.088 | 1.3 | 0.00 |
| 0.25 | 0.099 | 1.5 | 0.00 |
| 0.30 | 0.115 | 1.7 | 1.00 |
| 0.35 | 0.139 | 2.1 | 1.00 |
| 0.40 | 0.168 | 2.5 | 1.00 |
| 0.45 | 0.193 | 2.9 | 1.00 |
| 0.50 | 0.211 | 3.1 | 1.00 |

Vendor correlation is held at 0.85 and the share of the dominant vendor is swept. The fitted response is convex (quadratic coefficient 0.633; 71% of second differences positive). Dislocations become the more likely outcome from a share of 0.30. This tests, inside the sandbox, the prediction of Meng and Chen (2026): coupling convex in the adoption share.

## Red team: worst case evasion and injection containment

A budgeted search of 12 evasions over cohorts, rotation period, vendor correlation and share found 12 dislocating markets. The worst case for the certified sentinel (Tail dependence (tail concordance)) rotates 4 cohorts every 2 steps at correlation 0.85 and share 0.40: decision F1 0.00 against 0.68 on the battery, a robustness margin of 0.68. Every sentinel on that market: Volatility trigger 0.57, Correlation clustering 0.00, Network community sentinel 0.00, Absorption ratio 0.42, Buy sell imbalance (LSV herding measure) 0.00, Endogeneity (Hawkes branching ratio) 0.00, Lead lag ignition sentinel 0.70, Tail dependence (tail concordance) 0.00.

Injection containment: 11 of 11 adversarial cases against the battery planner, the persona elicitation, the briefing drafter, ASK and the ledger were contained (all).

## LLM personas in the battery

| Persona | Source | Momentum slope | Table hash |
|---|---|---|---|
| momentum_follower | offline surrogate | 0.83 | d45250610994e72a |

A persona is distilled once into a policy table over fifteen market states; every agent that shares it trades from the same table plus its own execution noise, so their correlation is a consequence of a shared model. The table hash was bound into the battery at Gate 1 and the simulator refuses a table that has changed. An offline surrogate is a documented synthetic table, not a claim about any real model.

## Time to dislocation: survival analysis of the battery

| Arm | Runs | Dislocations | Median steps to dislocation | Still contained after 20 steps | Still contained after 60 steps |
|---|---|---|---|---|---|
| untreated | 36 | 20 | 260 | 0.83 | 0.78 |
| Market wide circuit breaker | 36 | 8 | not reached | 1.00 | 0.94 |
| Sentinel informed dynamic throttle | 36 | 13 | not reached | 0.94 | 0.83 |
| Sentinel informed kill switch | 36 | 16 | not reached | 0.94 | 0.83 |
| LULD style price band (US) | 36 | 15 | not reached | 0.97 | 0.83 |
| Market wide circuit breaker (US) | 36 | 19 | 260 | 0.86 | 0.75 |
| Venue volatility interruption (EU) | 36 | 18 | 298 | 1.00 | 0.86 |
| Responsive enforcement ladder | 36 | 17 | not reached | 0.92 | 0.78 |
| Learned policy (model based RL) | 36 | 20 | 260 | 0.83 | 0.78 |

| Covariate | Hazard ratio | 95% interval |
|---|---|---|
| Market wide circuit breaker | 0.27 | 0.12 to 0.62 |
| Sentinel informed dynamic throttle | 0.50 | 0.25 to 1.02 |
| Sentinel informed kill switch | 0.63 | 0.33 to 1.21 |
| LULD style price band (US) | 0.61 | 0.31 to 1.20 |
| Market wide circuit breaker (US) | 0.96 | 0.51 to 1.81 |
| Venue volatility interruption (EU) | 0.80 | 0.43 to 1.52 |
| Responsive enforcement ladder | 0.72 | 0.38 to 1.37 |
| Learned policy (model based RL) | 1.00 | 0.54 to 1.85 |
| Dominant share | 3.06 | 2.40 to 3.91 |
| Dominant rho | 0.71 | 0.58 to 0.88 |

Each run is at risk from the shock; the event is the first step at which the drawdown from the pre shock level exceeds 0.10, and runs that never dislocate are censored at the horizon. The Kaplan Meier rows read the probability of no dislocation yet. The Cox model (324 runs, 146 events, converged) takes the untreated market as the reference: a hazard ratio below one means the rule delays or prevents dislocation, and the share and correlation rows give the hazard multiplier per standard deviation of each. Proportional hazards is an assumption here, not a finding.

| Sentinel | Alerts before the shock | Pre emption probability | Median alert step |
|---|---|---|---|
| Volatility trigger | 3 of 36 | 0.08 | 381 |
| Correlation clustering | 7 of 36 | 0.19 | not reached |
| Network community sentinel | 19 of 36 | 0.53 | 150 |
| Absorption ratio | 28 of 36 | 0.78 | 50 |
| Buy sell imbalance (LSV herding measure) | 18 of 36 | 0.50 | 220 |
| Endogeneity (Hawkes branching ratio) | 8 of 36 | 0.22 | not reached |
| Lead lag ignition sentinel | 10 of 36 | 0.28 | 370 |
| Tail dependence (tail concordance) | 33 of 36 | 0.92 | 40 |

## Tail risk of the treated market

| Rule | Expected shortfall of post shock drawdown, untreated | Treated | Tail containment |
|---|---|---|---|
| Market wide circuit breaker | 0.234 | 0.143 | 0.39 |
| Sentinel informed dynamic throttle | 0.234 | 0.165 | 0.29 |
| Sentinel informed kill switch | 0.234 | 0.224 | 0.04 |
| LULD style price band (US) | 0.234 | 0.156 | 0.33 |
| Market wide circuit breaker (US) | 0.234 | 0.216 | 0.07 |
| Venue volatility interruption (EU) | 0.234 | 0.155 | 0.34 |
| Responsive enforcement ladder | 0.234 | 0.179 | 0.24 |
| Learned policy (model based RL) | 0.234 | 0.225 | 0.04 |

Expected shortfall at level 0.75 is the mean drawdown of the worst 25% of herding scenarios. Unlike the mean, it reads the tail a supervisor is paid to worry about, and unlike value at risk it is coherent. A rule whose mean containment looks good but whose tail containment is poor is spending its halts on the easy scenarios.

## Enforcement ladder

The responsive enforcement ladder escalates from a targeted throttle to kill functionality to a market wide halt only when the lower rung fails, and steps down on recovery, after the enforcement pyramid of Ayres and Braithwaite. On this battery it contained 0.15 of the post shock drawdown with a false halt rate of 0.00 and engaged before the shock in 44% of herding scenarios. Because it is sentinel informed, its burden by class carries the sentinel's targeting error.

## Impact assessment summary

Set out in the structure of the UK Better Regulation Framework (rationale for intervention, options considered, costs and benefits, monitoring and evaluation), so the briefing can feed an impact assessment rather than sit beside one.

1. Rationale: agents built on shared foundation models can herd, and the tools meant to detect and interrupt herding are today certified on aggregate fidelity, a criterion this battery shows can invert the decision ranking.
2. Options: the surveillance sentinels and intervention rules compared above, including doing nothing (the untreated market).
3. Costs and benefits: decision accuracy, false alerts and false halts, burden by participant class, containment in the mean and in the tail, all with intervals; the cost frontier states on which declared weight each option is optimal.
4. Monitoring and evaluation: the ledger and evidence pack make every figure replayable; the held out family, the conformal guarantee and the red team are the review that a certified tool should pass again after deployment.

## What the central bank and regulator reports ask for, and what this run answers

| | Need flagged | Source | Status | Evidence in this run |
|---|---|---|---|---|
| N1 | Close the data gaps on AI adoption and use; indicators and a common taxonomy | FSB 2024 (recommendation 1); FSB 2025; IOSCO 2026 Table 7 | partial | indicators block computed from the run; the data gaps register lists what needs firm reporting |
| N2 | Monitor third party concentration, criticality and substitutability of AI providers | FSB 2025 case study; IOSCO 2026 Table 4; Bank of England 2025 | answered | vendor Herfindahl index up to 0.248, top vendor share 0.40, dislocations likelier from share 0.3; from supplied data the split is observed from the vendor column |
| N3 | Detect herding, correlated positioning and collusion between AI agents | IOSCO 2025 and 2026 (market risks); Bank of England 2025; IMF 2024 | answered | 8 sentinels ranked by decision F1; certified tail_dependence; ignition family for collusion; herd against quiet drawdown 0.18439231138729043 against 0.06707654859515887 |
| N4 | Test AI systems in an environment segregated from production, in stressed and unstressed conditions | IOSCO 2021 Measure 2, reaffirmed 2026 | answered | every scenario is simulated in a network restricted sandbox with quiet and stressed families, held out and empirical families |
| N5 | Circuit breaker and kill switch policies, calibrated and evidenced | IOSCO 2026 (market risk evidence); Breeden 2026; IMF 2024 | answered | 8 rules scored on containment and false halts; best on the faulty model episode static_circuit_breaker at 0.46 |
| N6 | Contingency for a third party model that fails or misbehaves | IOSCO 2026 Table 4 (contingency planning); FSB 2025 | answered | vendor fault family: best rule static_circuit_breaker contains 0.46 |
| N7 | Liquidity risk when AI liquidity providers withdraw in stress | IMF 2024; IOSCO 2026 (liquidity management plans) | answered | liquidity withdrawal family: best rule kill_switch contains 0.79 |
| N8 | Disinformation and deepfake driven market moves | FSB 2024; IOSCO 2025 (malicious uses) | answered | misinformation family: best rule static_circuit_breaker contains 0.41 |
| N9 | Risk based, proportionate supervision with a stated level of human oversight | IOSCO 2026 Box 2 | answered | appraisal by tier and proportionality; recommended tier 4 (market wide halt); every rule carries its human oversight level |
| N10 | Recordkeeping, audit trail and explainability of AI driven decisions | IOSCO 2026 Table 6; FSB 2026 sound practices | answered | hash chained signed ledger, critic vetting of every number, transparency record, flags explained per agent in the network panel |
| N11 | Model validation, anomaly alerts and a methodology for suspension | IOSCO 2026 Table 3 (model risk management) | answered | conformal false alert guarantee at 0.25 on 8 calibration scenarios; autonomy gate; emergency stop |
| N12 | Measure macro risk: the effect of aggregate firm conduct on system wide stability | IOSCO 2025 (knowledge gap); FSB 2024 | partial | aggregate conduct to system outcome measured in the sandbox (dose response, Shapley attribution, tail risk); not a measurement of the real market |
| N13 | Adversarial robustness: data poisoning, prompt injection, agents gaming the surveillance | IOSCO 2026 Table 3; FSB 2024 (cyber) | answered | injection suite 11 of 11 contained; adversarial evasion worst case F1 0.0; matrix game |
| N14 | Cross border alignment of indicators so authorities can compare | FSB 2025 (next steps); IOSCO 2026 (coordination) | answered | exchange record in the evidence pack with the indicators in a fixed schema |
| N15 | AI monitoring AI, with accountable human oversight | FSB 2026 consultation; IOSCO 2026 (AI as a judge) | answered | sentinels, critic and red team are AI monitoring AI; named preparer and approver with SMF or certified function at both gates |

Of the 15 needs, 13 are answered by this run, 2 in part and 0 not on this battery. Indicators in the families the IOSCO toolkit and the FSB monitoring report ask for: adoption share of AI driven agents up to 0.70, vendor Herfindahl index up to 0.248 with a top vendor share of 0.40 (substitutability proxy 0.60), herd against quiet post shock drawdown 0.184 against 0.067, persona output jump 1.50 for a one bucket change of state, expected shortfall of the dislocation 0.310. The held out drift of decision F1, the sandbox analogue of model drift, is largest for Lead lag ignition sentinel. Five indicators in those families need firm reporting and cannot be read from a synthetic run; they are listed in the artefacts as the data gaps register.

| Rule | Human oversight as deployed in HSL | Note |
|---|---|---|
| Market wide circuit breaker | human on the loop | venue rule; a supervisor can suspend it |
| Sentinel informed dynamic throttle | human in the loop | targeted action on named agents warrants approval |
| Sentinel informed kill switch | human in the loop | cancellation for named agents warrants approval |
| LULD style price band (US) | human out of the loop | mechanical band; oversight is in calibration |
| Market wide circuit breaker (US) | human on the loop | venue rule with declared levels |
| Venue volatility interruption (EU) | human on the loop | venue rule; parameters set by the venue |
| Responsive enforcement ladder | human on the loop | escalation with a supervisor able to halt escalation |
| Learned policy (model based RL) | human in control | a learned policy is advisory until validated in a pilot |

## Tail risk of the dislocation: value at risk, expected shortfall and the extreme value tail

Over the 36 herding scenarios the untreated post shock drawdown has mean 0.128, value at risk 0.183 and expected shortfall 0.310 at level 0.90. A generalised Pareto fit to the 11 excesses over 0.141 has shape 0.32 and gives a probability of 0.047 of a drawdown beyond 0.281 (empirical share 0.056).

| Rule | ES treated | ES reduction | 95% interval | Mean reduction |
|---|---|---|---|---|
| Venue volatility interruption (EU) | 0.182 | 0.41 | -0.02 to 0.60 | 0.19 |
| Market wide circuit breaker | 0.186 | 0.40 | -0.09 to 0.67 | 0.32 |
| Sentinel informed dynamic throttle | 0.190 | 0.39 | -0.05 to 0.59 | 0.21 |
| LULD style price band (US) | 0.195 | 0.37 | 0.07 to 0.55 | 0.22 |
| Responsive enforcement ladder | 0.217 | 0.30 | 0.07 to 0.44 | 0.15 |
| Market wide circuit breaker (US) | 0.269 | 0.13 | -0.04 to 0.24 | 0.04 |
| Sentinel informed kill switch | 0.286 | 0.08 | -0.99 to 0.53 | 0.07 |
| Learned policy (model based RL) | 0.290 | 0.06 | -0.01 to 0.13 | 0.02 |

Expected shortfall is the mean of the worst dislocations, the ones a supervisor is paid to prevent, and unlike value at risk it is coherent (McNeil, Frey and Embrechts 2015). A rule whose mean reduction exceeds its ES reduction contains the typical herd better than the severe one. The extreme value fit is descriptive at this sample size; the number of excesses is stated beside it.

## The certification as a game against the evader

Rows are sentinels, columns the 12 evasions found by the red team that still dislocated the market, entries decision F1. The maximin sentinel is Volatility trigger with a guaranteed F1 of 0.00 against the worst evasion; the adversary's best pure counter holds every sentinel to at most 0.40. A supervisor who randomised which sentinel is armed could guarantee 0.16 by mixing Volatility trigger 0.29, Endogeneity (Hawkes branching ratio) 0.41, Lead lag ignition sentinel 0.30; the value of unpredictability is 0.16.

## A learned market wide policy, and what logged data could have told a supervisor

A tabular model of the market's response to intervention was fitted from 16 runs logged under an epsilon soft behaviour policy (9283 steps, 91% of state action pairs observed) and solved by value iteration with a halt costing 0.020 and a throttle 0.005 per step. The learned policy halts in 9% of states and throttles in 9%; it is scored as a rule in the intervention monitor and is advisory.

| Policy | Importance sampling | Doubly robust | Model based | Simulated on policy |
|---|---|---|---|---|
| Learned policy (model based RL) | -0.031 | 0.122 | -0.052 | -0.066 |
| do nothing | -0.031 | 0.125 | -0.053 | -0.057 |
| Market wide circuit breaker | -0.056 | -0.118 | -0.157 | -0.189 |
| Sentinel informed dynamic throttle | -0.031 | 0.125 | -0.053 | -0.057 |
| Sentinel informed kill switch | -0.031 | 0.125 | -0.053 | -0.057 |
| LULD style price band (US) | -0.039 | 0.036 | -0.081 | -0.079 |
| Market wide circuit breaker (US) | -0.031 | 0.143 | -0.057 | -0.073 |
| Venue volatility interruption (EU) | -0.039 | -0.009 | -0.076 | -0.084 |
| Responsive enforcement ladder | -0.031 | 0.125 | -0.053 | -0.057 |

Off policy evaluation answers the pilot's question: what would this rule have been worth, using only trajectories logged under another policy. On this battery the mean absolute error against the simulated value is 0.044 for importance sampling, 0.155 for the doubly robust estimator and 0.010 for the fitted model; the fitted model's value comes closest. Importance sampling truncates as soon as the logged action differs from the target's and the doubly robust recursion compounds model error over a long horizon, so neither can be trusted on its own at this sample size. The sandbox can measure the error because it can simulate the truth; a pilot cannot, which is why this audit belongs before one.

## Regulatory options appraisal and the enforcement ladder

Baseline: do nothing: the untreated herd (three worlds, herd path). Non regulatory option: monitor and warn: certify a sentinel, intervene by no rule. Tests: containment of at least 0.30, false halts within 0.25, and for targeted rules a burden on agents that were not destabilising of at most 0.50 of the burden on those that were.

| Tier | Rule | Instrument | Containment | False halts | ES reduction | Burden ratio | Passes | Legal basis |
|---|---|---|---|---|---|---|---|---|
| 1 targeted throttle | Sentinel informed dynamic throttle | risk based, targeted | 0.21 | 0.00 | 0.39 | 0.33 | containment failed | RTS 6 Art 12 by analogy; MAR Art 12 and Annex II for the conduct |
| 2 targeted kill | Sentinel informed kill switch | risk based, targeted | 0.07 | 0.00 | 0.08 | 0.34 | containment failed | RTS 6 Art 12; MAR Art 12 and Annex II for the conduct |
| 3 price band or venue halt | LULD style price band (US) | command and control | 0.22 | 0.00 | 0.37 | 1.07 | containment failed | MiFID II Art 48(5); LULD plan (US) |
| 3 price band or venue halt | Venue volatility interruption (EU) | command and control | 0.19 | 0.00 | 0.41 | 1.20 | containment failed | MiFID II Art 48(5); ESMA circuit breaker guidelines |
| 3 price band or venue halt | Learned policy (model based RL) | adaptive command and control | 0.02 | 0.00 | 0.06 | 1.05 | containment failed | MiFID II Art 48(5) (as a venue rule); advisory only in HSL |
| 4 market wide halt | Market wide circuit breaker | command and control | 0.32 | 0.00 | 0.40 | 1.19 | all | MiFID II Art 48(5); RTS 7 |
| 4 market wide halt | Responsive enforcement ladder | command and control | 0.15 | 0.00 | 0.30 | 0.35 | containment failed |  |
| 4 market wide halt | Market wide circuit breaker (US) | command and control | 0.04 | 0.00 | 0.13 | 1.35 | containment failed | MiFID II Art 48(5); market wide breaker rules of the venue |

Responsive regulation recommends tier 4 (market wide halt): Market wide circuit breaker, command and control, basis MiFID II Art 48(5); RTS 7. 1 rules are eligible. The principle is responsive regulation: the lowest tier that meets the containment target within the false halt budget and the proportionality limit. The legal basis column is a pointer to the power a UK or EU authority would name, not legal advice.

## Observed data brought to the sandbox

| Dataset | Classification | Rows | Source | In the evidence pack | Hash |
|---|---|---|---|---|---|
| labelled_flows.csv | public | 3600 | upload | yes | bf47b2157e7df1fd |

Anchoring of labelled_flows.csv against the battery's quiet family: vol 0.0061 against 0.0025 (ratio 2.44, outside the band); kurtosis 2.8764 against 2.9599 (ratio 0.97, within the band); abs autocorr 1 -0.0230 against -0.0249 (ratio n/a, outside the band); max drawdown 0.1624 against 0.0400 (ratio 4.06, outside the band). 1 of 4 statistics fall within a factor of two.

Observed window of labelled_flows.csv: 12 participants over 300 steps. Volatility trigger did not alert, peak stress 1.41, flagged 0 (0.00 of participants); Correlation clustering did not alert, peak stress 0.00, flagged 0 (0.00 of participants); Network community sentinel did not alert, peak stress 0.00, flagged 0 (0.00 of participants); Absorption ratio alerted, peak stress 1.35, flagged 5 (0.42 of participants); Buy sell imbalance (LSV herding measure) did not alert, peak stress 0.99, flagged 0 (0.00 of participants); Endogeneity (Hawkes branching ratio) did not alert, peak stress 0.83, flagged 0 (0.00 of participants); Lead lag ignition sentinel did not alert, peak stress 0.84, flagged 0 (0.00 of participants); Tail dependence (tail concordance) did not alert, peak stress 0.00, flagged 0 (0.00 of participants). There is no ground truth for observed data, so these are counts only; no participant is named and counts below 5 are withheld.

Every dataset passed one quarantine: size and type limits, text only, a schema check, a spreadsheet formula check, a personal identifier scan that refuses rather than redacts, and a classification with a no write down rule. Held out empirical scenarios take their shock and volatility from the observed data and are in this battery.

| Dataset | Volatility | Shock | Impact | Momentum window | Fundamentalists | Vendor share and correlation | Split | Participants |
|---|---|---|---|---|---|---|---|---|
| labelled_flows.csv | 0.0061 | 0.085 | 0.0050 | 5 | 0.09 | 0.39 at 0.42, 0.31 at 0.20 | observed from the vendor column | 12 |

Each dataset was used to calibrate the simulator: volatility from the observed returns, the shock from the tail of rolling window drawdowns, price impact from the regression of returns on aggregate flow, the momentum window from the past window that best predicts the next return, the fundamentalist fraction from the observed speed of reversion, and the vendor split from the vendor column where the data carries one (observed) or from communities in the flow correlation matrix (inferred: a correlated group may be a shared model, a shared information source or a shared hedging need). Two families followed: a calibrated synthetic market with these parameters and the generator's ground truth, and a hybrid market in which the observed return path is the news and the synthetic agents respond to it. Clamps and notes: kappa: 0.003284 clamped to 0.005; vendor_rho: -0.02552 clamped to 0.2; vendor shares scaled to sum to 0.70.

Calibration shift. The calibrated structure sits below the destabilising thresholds, so its families carry no positives; they test false alerts and containment, not localisation.

## Security posture at release

15 controls pass, 2 warn, 0 fail. Warnings: identities come from an authenticating proxy (auth mode open; names are self declared, fine for a demo, not for production); approvers tied to a register of regulated persons (no register configured; approvers are self declared (set HSL_REGISTER)). Each control applies a chapter of Anderson's Security Engineering; the mapping is in the security framework document of the evidence pack. A failing control blocks release.

## Backtests: observed episodes and the certification procedure

Walk forward. Over 4 folds of the calibration scenarios, the tool certified on the earlier folds was scored on the next: mean regret against the best tool on the test fold 0.27, worst 0.71, and the certified tool was still the best on 33% of test folds. fold 1: certified Endogeneity (Hawkes branching ratio) at 0.11 against Tail dependence (tail concordance) at 0.82; fold 2: certified Tail dependence (tail concordance) at 0.63 against Tail dependence (tail concordance) at 0.63; fold 3: certified Buy sell imbalance (LSV herding measure) at 0.52 against Tail dependence (tail concordance) at 0.61.

labelled_flows.csv: 1 episode (Marked 0 drawdown 0.089 at step 156, event column).

| Sentinel | Episodes detected | Median lead (steps) | Alerts per 100 quiet steps | Recall on labelled positives |
|---|---|---|---|---|
| Volatility trigger | 1.00 | 18 | 3.50 | 0.00 |
| Correlation clustering | 0.00 | n/a | 0.00 | n/a |
| Network community sentinel | 0.00 | n/a | 0.00 | n/a |
| Absorption ratio | 1.00 | -54 | 0.50 | 1.00 |
| Buy sell imbalance (LSV herding measure) | 0.00 | n/a | 0.00 | n/a |
| Endogeneity (Hawkes branching ratio) | 0.00 | n/a | 0.00 | n/a |
| Lead lag ignition sentinel | 0.00 | n/a | 0.00 | n/a |
| Tail dependence (tail concordance) | 0.00 | n/a | 0.00 | n/a |

This is a timing and workload backtest. The tape says when a sentinel alerted relative to the observed event and how often it alerts in quiet stretches; it does not say who the destabilising participants were, so precision is not reported and recall is on the labelled positives only.

| Rule | Mean containment over episodes | Worst episode |
|---|---|---|
| Market wide circuit breaker | 0.33 | 0.33 |
| Sentinel informed dynamic throttle | 0.00 | 0.00 |
| Sentinel informed kill switch | 0.00 | 0.00 |
| LULD style price band (US) | -0.00 | -0.00 |
| Market wide circuit breaker (US) | 0.05 | 0.05 |
| Venue volatility interruption (EU) | 0.03 | 0.03 |
| Responsive enforcement ladder | 0.00 | 0.00 |
| Learned policy (model based RL) | 0.00 | 0.00 |

Each episode was replayed as a hybrid market: the observed return path as the news, the calibrated synthetic population responding, every rule applied; containment is against the untreated hybrid run of the same episode.

## Rule library

| Rule | Jurisdiction | Modelled on |
|---|---|---|
| Market wide circuit breaker | generic | rolling return limit halting the whole market |
| Sentinel informed dynamic throttle | generic | sentinel informed targeted throttle of flagged agents |
| Sentinel informed kill switch | EU (firm level analogue) | RTS 6 Article 12 kill functionality applied to sentinel flagged agents: immediate cancellation for a dwell period |
| LULD style price band (US) | US | Limit Up-Limit Down Plan: 5% band around a five minute reference price, 15 second limit state, five minute pause; mapped to steps |
| Market wide circuit breaker (US) | US | Market wide circuit breaker levels of 7%, 13% and 20% decline from the reference close: 15 minute halts at levels one and two, halt for the day at level three; mapped to steps |
| Venue volatility interruption (EU) | EU | MiFID II Article 48(5) and the ESMA guidelines on circuit breaker calibration: dynamic collar on the last price and static collar on a reference price; a breach triggers a volatility interruption of set length; parameters are illustrative |
| Responsive enforcement ladder | generic (enforcement pyramid) | Ayres and Braithwaite 1992 enforcement pyramid: escalate from a targeted throttle to kill functionality to a market wide halt only when the lower rung fails; step down on recovery |

Durations are simulation steps and parameters are illustrative; the library lets one battery compare regimes, it does not reproduce any venue's calibration.

## Scope and limitations

The battery holds 51 scenarios: 36 herding, 8 quiet and 7 held out. Synthetic markets stylise real microstructure. All outputs are comparative rankings of tools and rules on this battery. They are not forecasts and do not recommend live intervention. Sentinel and rule thresholds were calibrated on the demonstration families; the held out and adversarial rows show where that calibration does and does not carry.

Evidence grades: A means at least 12 scenarios and a 95% interval half width below 0.10; B means at least 6 scenarios and a half width below 0.20; C means anything weaker.

## Provenance

HSL 3.9.2, code fingerprint b75c8eccaf693320, battery hash 4bf2b1c1e6282df0, flags for targeted rules from Network community sentinel, bootstrap resamples 400, numpy 2.4.4, scipy 1.17.1.

*All figures are computed from logged simulation artefacts (artefacts.json); the drafting layer cannot alter them. Every step is recorded in the signed rationale ledger, which any reviewer can replay with `python -m hsl.ledger verify`.*