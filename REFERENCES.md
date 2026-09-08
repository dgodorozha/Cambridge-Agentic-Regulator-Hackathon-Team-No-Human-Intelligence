# Referenced works

This file is the separate list of works that the Herding Scenario Lab
draws on, requested for the submission. Each entry states what the build
takes from it. Entries are grouped by the part of the build they inform.
URLs are the publisher's or the repository's own; nothing here was
fabricated and every entry was checked against its source.

## Code provenance

No code was copied from any third party repository. Every module in `hsl/`
was written for this project from the papers cited below. The repositories
listed under "Repositories consulted" were read for design (interfaces,
what a market simulator exposes, how injection benchmarks are structured);
their licences do not attach to this codebase. Vendored front end
libraries and their licences are unchanged from version 2 and are listed in
`README.md` (TradingView Lightweight Charts, Apache 2.0; ECharts, Apache
2.0; Perspective, Apache 2.0; Bedstead font, CC0).

## Regulators and standard setters

- Financial Stability Board (2026), *Sound Practices for Responsible Adoption
  of Artificial Intelligence (AI): Consultation report*, 10 June 2026.
  https://www.fsb.org/2026/06/sound-practices-for-responsible-adoption-of-artificial-intelligence-ai-consultation-report/
  Twelve sound practices; explicit attention to agentic AI and to AI
  monitoring AI. HSL's supervised multi agent design with named human gates
  is the shape of that recommendation.
- Financial Stability Board (2025), *Monitoring Adoption of AI and Related
  Vulnerabilities in the Financial Sector*. The indicator framework the
  concentration dose response is meant to feed.
- Bank of England (2026), Sarah Breeden, "Agents of change", panel at the
  ECB Forum on Central Banking, Sintra, 30 June 2026.
  https://www.bankofengland.co.uk/speech/2026/june/sarah-breeden-panel-at-the-european-central-bank-forum-on-central-banking-2026
  Names herding by agents built on common models, market wide kill switches
  as an option, and the simulation work with the BIS Innovation Hub and the
  Bundesbank. The kill switch and market wide breaker rules are the
  mechanisms under discussion.
- BIS Innovation Hub (2026), *Project Logos: observing the behaviour of
  LLM-based agents in a simulated financial market environment* (with the
  Bank of England and the Deutsche Bundesbank).
  https://www.bis.org/about/bisih/topics/suptech_regtech/logos.htm
  LLM agents as portfolio managers in a synthetic market. HSL's persona
  traders are the auditable, distilled form of the same channel.
- Bank of England (2025), *Financial Stability in Focus: AI in the financial
  system*. Correlated positioning, vendor concentration and herding channels
  (cited in the problem statement).
- International Monetary Fund (2024), *Global Financial Stability Report*,
  chapter 3, AI and capital markets. Herding, data oligopolies and market
  concentration (cited in the problem statement).
- U.S. Securities and Exchange Commission (2011), press release 2011-84 on
  the Limit Up-Limit Down plan; Nasdaq, *LULD: Frequently Asked Questions*;
  Cboe, *Limit Up/Down FAQ*. https://www.sec.gov/news/press/2011/2011-84.htm
  Source of the band widths (5% and 10%), the five minute reference price,
  the 15 second limit state and the five minute pause behind
  `LULDStyleBand`.
- NYSE, market wide circuit breaker levels (7%, 13% and 20% declines).
  Behind `MarketWideBreaker`.
- Directive 2014/65/EU (MiFID II), Article 48(5) (venues must be able to
  halt or constrain trading on a significant price movement); Commission
  Delegated Regulation (EU) 2017/589 (RTS 6), Article 12 (kill
  functionality); ESMA (2017), *Guidelines on the calibration of circuit
  breakers*. Behind `VenueVolatilityHalt` and the framing of the kill
  switch rule.
- Regulation (EU) No 596/2014 (MAR), Annex II, indicators of manipulative
  behaviour. The ignition family follows the momentum ignition pattern.

## Herding, endogeneity and manipulation measures

- Lakonishok, J., Shleifer, A. and Vishny, R. W. (1992), "The impact of
  institutional trading on stock prices", *Journal of Financial Economics*
  32(1), 23-43. The buy sell imbalance herding measure behind
  `ImbalanceSentinel`.
- Christie, W. G. and Huang, R. D. (1995), "Following the pied piper: do
  individual returns herd around the market?", *Financial Analysts Journal*
  51(4), 31-37; Chang, E. C., Cheng, J. W. and Khorana, A. (2000), "An
  examination of herd behavior in equity markets: an international
  perspective", *Journal of Banking and Finance* 24(10), 1651-1679. The return
  dispersion measures; noted in `herding.py` as needing a cross section of
  assets and therefore not implemented in this single asset market.
- Filimonov, V. and Sornette, D. (2012), "Quantifying reflexivity in
  financial markets: toward a prediction of flash crashes", *Physical Review
  E* 85, 056108. https://arxiv.org/abs/1201.3572 The branching ratio as the
  share of endogenous activity, behind `EndogeneitySentinel`.
- Hardiman, S. J., Bercot, N. and Bouchaud, J.-P. (2013), "Critical
  reflexivity in financial markets: a Hawkes process analysis", *European
  Physical Journal B* 86, 442. https://arxiv.org/abs/1302.1405 Estimation
  caveats for the branching ratio (the sentinel profiles the decay over a
  grid rather than fixing it).
- Bacry, E., Mastromatteo, I. and Muzy, J.-F. (2015), "Hawkes processes in
  finance", *Market Microstructure and Liquidity* 1(1).
  https://arxiv.org/abs/1502.04592 Survey; the endogeneity interpretation
  of the branching ratio used in the sentinel docstring.
- Kritzman, M., Li, Y., Page, S. and Rigobon, R. (2011), "Principal
  components as a measure of systemic risk", *Journal of Portfolio
  Management* 37(4), 112-126. The absorption ratio (version 2 sentinel).

## Market generators and price impact

- Kirman, A. (1993), "Ants, rationality, and recruitment", *Quarterly
  Journal of Economics* 108(1), 137-156. Recruitment as the herding
  mechanism of the imitation generator.
- Lux, T. and Marchesi, M. (1999), "Scaling and criticality in a stochastic
  multi-agent model of a financial market", *Nature* 397, 498-500.
  Chartist and fundamentalist switching that depends on the trend; the
  imitation generator's trend dependent recruitment.
- Bouchaud, J.-P., Farmer, J. D. and Lillo, F. (2009), "How markets slowly
  digest changes in supply and demand", in *Handbook of Financial Markets:
  Dynamics and Evolution*, Elsevier; Toth, B., Lemperiere, Y., Deremble, C.,
  de Lataillade, J., Kockelkoren, J. and Bouchaud, J.-P. (2011), "Anomalous
  price impact and the critical nature of liquidity in financial markets",
  *Physical Review X* 1, 021006. The square root impact law behind the
  `sqrt_impact` generator.
- Meng, S. and Chen, X. (2026), "Artificial Intelligence and Systemic Risk:
  A Unified Model of Performative Prediction, Algorithmic Herding, and
  Cognitive Dependency in Financial Markets", arXiv:2604.03272.
  https://arxiv.org/abs/2604.03272 The convexity of systemic risk coupling
  in the AI adoption share, the prediction the concentration dose response
  tests. Cited in the problem statement.

## LLM agents in markets, collusion and monoculture

- Lopez-Lira, A. (2025), "Can Large Language Models Trade? Testing
  Financial Theories with LLM Agents in Market Simulations",
  arXiv:2504.10789. https://arxiv.org/abs/2504.10789 Prompts generate
  correlated behaviours in LLM agent markets; the persona distillation
  makes that mechanism reproducible and auditable.
- Yang, Y., Zhang, Y., Wu, M., Zhang, K., Zhang, Y., Yu, H., Hu, Y. and
  Wang, B. (2025), "TwinMarket: A Scalable Behavioral and Social Simulation
  for Financial Markets", *NeurIPS 2025*. https://arxiv.org/abs/2502.01506
  LLM agents with behavioural biases including herding; stylised facts as
  realism checks.
- Li, J., Liu, Y., Liu, W., Fang, S., Wang, L., Xu, C. and Bian, J. (2025),
  "MarS: a Financial Market Simulation Engine Powered by Generative
  Foundation Model", *ICLR 2025*. https://arxiv.org/abs/2409.07486
  Simulation as detection system and agent training environment; the
  "order level generator as the truth" view that motivates the truth
  dependence audit.
- Fish, S., Gonczarowski, Y. A. and Shorrer, R. I. (2024, updated 2025),
  "Algorithmic Collusion by Large Language Models", arXiv:2404.00806.
  https://arxiv.org/abs/2404.00806 LLM pricing agents reach
  supracompetitive outcomes autonomously; prompt wording matters. Motivates
  the colluding cluster family and the persona prompt hashing.
- Calvano, E., Calzolari, G., Denicolo, V. and Pastorello, S. (2020),
  "Artificial intelligence, algorithmic pricing, and collusion", *American
  Economic Review* 110(10), 3267-3297. Tacit collusion by learning
  algorithms; background to the colluding cluster.
- "Evaluating LLM Agent Collusion in Double Auctions" (2025), Workshop on
  Multi-Agent Systems in the Era of Foundation Models, *ICML 2025*.
  https://arxiv.org/abs/2507.01413 Collusion in continuous markets and
  its dependence on communication and oversight pressure.
- Lin, R. Y., Ojha, S., Cai, K. and Chen, M. (2024), "Strategic Collusion
  of LLM Agents: Market Division in Multi-Commodity Competitions", Language
  Gamification workshop, *NeurIPS 2024*; "Institutional AI: Governing LLM
  Collusion in Multi-Agent Cournot Markets via Public Governance Graphs"
  (2026), arXiv:2601.11369. Runtime governance of colluding agents; the
  argument for observability artefacts such as the ledger.
- Danielsson, J. and Uthemann, A. (2025), "Artificial intelligence and
  financial crises". Authorities need their own AI engines; the reason HSL
  is built to be run by an authority (cited in the problem statement).

## Certification, attribution and evaluation methodology

- Vovk, V., Gammerman, A. and Shafer, G. (2005), *Algorithmic Learning in a
  Random World*, Springer. Conformal p values and the exchangeability
  guarantee behind `conformal.py`.
- Laxhammar, R. and Falkman, G. (2010), "Conformal prediction for
  distribution-independent anomaly detection in streaming vessel data",
  *Proceedings of the First International Workshop on Novel Data Stream
  Pattern Mining Techniques*; Laxhammar, R. (2014), *Conformal anomaly
  detection*, PhD thesis, University of Skovde. Conformal anomaly
  detection as the framing of a false alert guarantee.
- Bates, S., Candes, E., Lei, L., Romano, Y. and Sesia, M. (2023), "Testing
  for outliers with conformal p-values", *Annals of Statistics* 51(1),
  149-178. Calibration set outlier testing with finite sample control.
- Bashari, M., Sesia, M. and Romano, Y. (2025), "Robust Conformal Outlier
  Detection under Contaminated Reference Data", *ICML 2025*.
  https://proceedings.mlr.press/v267/bashari25a.html Conservativeness of
  the guarantee when the calibration set is not perfectly clean; the reason
  the held out quiet rate is reported beside the bound.
- Zhang, S., Zhou, C., Liu, Y., Zhang, P., Lin, X. and Pan, S. (2025),
  "Conformal Anomaly Detection in Event Sequences", *ICML 2025*.
  https://proceedings.mlr.press/v267/zhang25dn.html Finite sample false
  positive control for event sequence detectors, the class the endogeneity
  sentinel belongs to.
- Shapley, L. S. (1953), "A value for n-person games", in *Contributions to
  the Theory of Games II*, Princeton University Press; Tarashev, N., Borio,
  C. and Tsatsaronis, K. (2010), "Attributing systemic risk to individual
  institutions", BIS Working Papers No 308.
  https://www.bis.org/publ/work308.htm The Shapley attribution of system
  wide risk to members, applied here to agent groups by counterfactual
  silencing.
- Godorozha, D. and co-authors (2026), "Accurate Networks, Wrong Banks:
  Reconstruction Quality Depends on the Decision It Informs", submitted to
  *ICAIF 2026*. The decision gap, the "fail each in turn" decision criterion
  and the truth dependence design that version 3 transports to sentinels.
- Wilder, B., Dilkina, B. and Tambe, M. (2019), "Melding the data-decisions
  pipeline: decision-focused learning for combinatorial optimization",
  *AAAI 2019*; Mandi, J., Kotary, J., Berden, S., Mulamba, M., Bucarey, V.,
  Guns, T. and Fioretto, F. (2024), "Decision-focused learning: foundations,
  state, challenges, and future directions", *Journal of Artificial
  Intelligence Research* 80, 1623-1701. Scoring a tool by the loss of the
  decision it informs; the cost frontier.
- Lee, R., Mengshoel, O. J., Saksena, A., Gardner, R. W., Genin, D.,
  Silbermann, J., Owen, M. and Kochenderfer, M. J. (2020), "Adaptive Stress
  Testing: Finding Likely Failure Events with Reinforcement Learning",
  *Journal of Artificial Intelligence Research* 69, 1165-1201.
  https://jair.org/index.php/jair/article/view/12190 Searching a simulator
  for failure; the budgeted black box form is the adversarial evasion
  search.
- Debenedetti, E., Zhang, J., Balunovic, M., Beurer-Kellner, L., Fischer,
  M. and Tramer, F. (2024), "AgentDojo: A Dynamic Environment to Evaluate
  Prompt Injection Attacks and Defenses for LLM Agents", *NeurIPS 2024*,
  Datasets and Benchmarks track.
  https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract.html
  Injection tasks embedded in the data an agent processes; the shape of the
  injection containment suite.
- Iravani, S., Orfanoudaki, A., Markakis, M. and Szpruch, L., "The Limits of
  Autonomy in Agentic AI" (Oxford). Score triggered autonomy (version 2
  autonomy gate).

## Course readings behind version 3.2

- McNeil, A. J., Frey, R. and Embrechts, P. (2015), *Quantitative Risk
  Management: Concepts, Techniques and Tools*, revised edition, Princeton
  University Press. Value at risk, expected shortfall and coherence,
  dependence measures and tail dependence, extreme value theory (the Risk
  module chapters 3, 7 and 8).
- Embrechts, P., McNeil, A. and Straumann, D. (2002), "Correlation and
  dependence in risk management: properties and pitfalls", in *Risk
  Management: Value at Risk and Beyond*, Cambridge University Press. Why
  correlation misses joint extremes; the tail dependence sentinel.
- Pickands, J. (1975), "Statistical inference using extreme order
  statistics", *Annals of Statistics* 3(1), 119-131; Balkema, A. A. and de
  Haan, L. (1974), "Residual life time at great age", *Annals of
  Probability* 2(5), 792-804. The generalised Pareto limit behind the peaks
  over threshold fit.
- Kaplan, E. L. and Meier, P. (1958), "Nonparametric estimation from
  incomplete observations", *Journal of the American Statistical
  Association* 53(282), 457-481. The survival estimator.
- Cox, D. R. (1972), "Regression models and life-tables", *Journal of the
  Royal Statistical Society B* 34(2), 187-220. The proportional hazards
  model and partial likelihood (ST411 part 5).
- Sutton, R. S. and Barto, A. G. (2018), *Reinforcement Learning: An
  Introduction*, 2nd edition, MIT Press. Tabular model based control and
  value iteration (ST455 lectures 3 and 9; AI in Games lab 6).
- Precup, D., Sutton, R. S. and Singh, S. (2000), "Eligibility traces for
  off-policy policy evaluation", *ICML 2000*. Per decision importance
  sampling.
- Jiang, N. and Li, L. (2016), "Doubly robust off-policy value evaluation
  for reinforcement learning", *ICML 2016*; Thomas, P. and Brunskill, E.
  (2016), "Data-efficient off-policy policy evaluation for reinforcement
  learning", *ICML 2016*. The doubly robust estimator and weight clipping
  (ST455 lecture 11).
- Auer, P., Cesa-Bianchi, N. and Fischer, P. (2002), "Finite-time analysis
  of the multiarmed bandit problem", *Machine Learning* 47, 235-256. UCB1,
  the evasion search.
- von Neumann, J. (1928), "Zur Theorie der Gesellschaftsspiele",
  *Mathematische Annalen* 100, 295-320. The minimax theorem behind the
  matrix game (AI in Games).
- Holley, R. A. and Liggett, T. M. (1975), "Ergodic theorems for weakly
  interacting infinite systems and the voter model", *Annals of
  Probability* 3(4), 643-663; Castellano, C., Fortunato, S. and Loreto, V.
  (2009), "Statistical physics of social dynamics", *Reviews of Modern
  Physics* 81, 591-646. The voter model (6CCS3AIN week 9, D. Kohan
  Marzagao).
- Ayres, I. and Braithwaite, J. (1992), *Responsive Regulation:
  Transcending the Deregulation Debate*, Oxford University Press. The
  enforcement pyramid behind the ladder and the appraisal.
- Baldwin, R. and Black, J. (2008), "Really responsive regulation", *Modern
  Law Review* 71(1), 59-94; Black, J. (2005), "The emergence of risk-based
  regulation and the new public risk management in the United Kingdom",
  *Public Law*, 512-548. Risk based and responsive instrument choice.
- Baldwin, R., Cave, M. and Lodge, M. (2012), *Understanding Regulation*,
  2nd edition, Oxford University Press. Instrument types (command and
  control and the alternatives), enforcement strategies.
- HM Government (2023), *Better Regulation Framework: Guidance*, September
  2023. Do nothing baseline, non regulatory options, proportionality.
- Directive 2014/65/EU Article 48(5); Commission Delegated Regulations (EU)
  2017/584 (RTS 7) and 2017/589 (RTS 6); Regulation (EU) No 596/2014 (MAR)
  Article 12 and Annex II; Financial Services and Markets Act 2000 section
  1D and Part XI. The legal basis column of the appraisal (pointers, not
  advice).

## Security engineering

- Anderson, R. (2020), *Security Engineering: A Guide to Building Dependable
  Distributed Systems*, 3rd edition, Wiley. The framework document maps
  chapters 1 to 12, 21, 26 to 29 to the platform's controls.
- Clark, D. D. and Wilson, D. R. (1987), "A comparison of commercial and
  military computer security policies", *IEEE Symposium on Security and
  Privacy*. The integrity model behind the gates, the ledger and the critic
  (Anderson chapter 12).
- Saltzer, J. H. and Schroeder, M. D. (1975), "The protection of
  information in computer systems", *Proceedings of the IEEE* 63(9),
  1278-1308. Least privilege, separation of privilege and complete
  mediation, the principles behind the roles and the single quarantine.
- Bell, D. E. and LaPadula, L. J. (1973), *Secure Computer Systems:
  Mathematical Foundations*, MITRE Technical Report 2547. The no write down
  rule applied to data classification (Anderson chapter 9).

## Central bank and regulator reports on AI in markets (version 3.4)

- Financial Stability Board (2024), *The Financial Stability Implications
  of Artificial Intelligence*, November 2024. Vulnerabilities (third party
  dependencies, market correlations, cyber, model risk) and the
  recommendation to close data gaps.
- Financial Stability Board (2025), *Monitoring Adoption of AI and Related
  Vulnerabilities in the Financial Sector*, October 2025.
  https://www.fsb.org/2025/10/fsb-outlines-next-steps-for-authorities-on-ai-monitoring/
  Data gaps and taxonomies; indicators of criticality, concentration and
  substitutability of third party providers; cross border alignment.
- International Organization of Securities Commissions (2025), *Artificial
  Intelligence in Capital Markets: Use Cases, Risks, and Challenges*,
  CR/01/2025. https://www.iosco.org/library/pubdocs/pdf/IOSCOPD788.pdf
  Herding, collusion and third party concentration flagged for monitoring;
  the macro risk measurement gap.
- International Organization of Securities Commissions (2026), *Supervisory
  Toolkit for AI Use in Capital Markets*, FR/02/2026, May 2026.
  https://www.iosco.org/library/pubdocs/pdf/IOSCOPD823.pdf Risk based
  supervision and the human oversight classes (Box 2), market risk
  evidence (stress testing, circuit breaker and kill switch policies),
  third party contingency planning (Table 4), recordkeeping (Table 6) and
  the indicators of Table 7.
- Bank of England (2025), *Financial Stability in Focus: AI in the financial
  system*, April 2025; Breeden, S. (2026), speech at the ECB Forum on
  Central Banking, Sintra, 30 June 2026. Correlated positioning, vendor
  concentration, kill switches.
- International Monetary Fund (2024), *Global Financial Stability Report*,
  October 2024, chapter 3. Herding, liquidity withdrawal by AI liquidity
  providers, market concentration.

## Accountability and registration

- Financial Conduct Authority, *Senior Managers and Certification Regime*
  and PS26/6 *Senior Managers and Certification Regime review* (April 2026).
  https://www.fca.org.uk/publications/policy-statements/ps26-6-senior-managers-certification-regime-review
  Individual accountability through senior manager approval, certification
  functions and the conduct rules; the role fields at the gates.
- Government Digital Service, *Algorithmic Transparency Recording Standard
  Hub*, including the template and the mandatory scope and exemptions
  policy (December 2024).
  https://www.gov.uk/government/collections/algorithmic-transparency-recording-standard-hub
  The structure of the transparency record HSL writes at release.
- Regulation (EU) 2024/1689 (AI Act) Article 49 and Regulation (EU)
  2026/1744 (Digital Omnibus on AI). Registration of high risk systems in
  the EU database, deferred to 2 December 2027 for Annex III systems.

## Repositories consulted (design only; no code copied)

- microsoft/MarS, https://github.com/microsoft/MarS (MIT). Order level
  simulation as a detection and training environment.
- FreedomIntelligence/TwinMarket, https://github.com/FreedomIntelligence/TwinMarket
  (MIT). LLM agent market simulation with a matching engine and behavioural
  personas.
- alejandroll10/llm_trading_sim, https://github.com/alejandroll10/llm_trading_sim.
  Structured decisions from LLM agents; the case for distilling rather than
  calling a model at every step.
- jpmorganchase/abides-jpmc-public (ABIDES, ABIDES-Markets, ABIDES-Gym),
  https://github.com/jpmorganchase/abides-jpmc-public (BSD style). The
  interface a market simulator exposes to strategic agents; the
  `ExternalPolicy` integration surface of version 2.
- JAX-LOB (Frey and others 2023), https://arxiv.org/abs/2308.13289. Limit
  order book simulation at scale; noted as the route to an order book
  version of HSL.
- ethz-spylab/agentdojo, https://github.com/ethz-spylab/agentdojo (MIT).
  Structure of injection tasks and defences.
- sisl/AdaptiveStressTesting.jl, https://github.com/sisl/AdaptiveStressTesting.jl.
  Reference implementation of adaptive stress testing.

## Course material supplied by the team (version 3.2)

The methods below were implemented from the team's own course notes and
the published sources they teach. No text or code from the notes was copied
into the build.

- LSE ST411, Generalized Linear Modelling and Survival Analysis (Kakou and
  Kuha), lecture 5: survival functions, Kaplan and Meier (1958), "Nonparametric
  estimation from incomplete observations", *Journal of the American
  Statistical Association* 53, 457-481; Cox (1972), "Regression models and
  life-tables", *Journal of the Royal Statistical Society B* 34, 187-220;
  Greenwood's variance; Breslow's treatment of ties. Behind `survival.py`.
- LSE Quantitative Risk Management (Zhu), chapters 3, 7 and 8, after McNeil,
  A. J., Frey, R. and Embrechts, P. (2015), *Quantitative Risk Management:
  Concepts, Techniques and Tools*, revised edition, Princeton University
  Press; Artzner, P., Delbaen, F., Eber, J.-M. and Heath, D. (1999),
  "Coherent measures of risk", *Mathematical Finance* 9(3), 203-228. Behind
  expected shortfall, tail containment and the tail dependence sentinel;
  extreme value theory (chapter 8) is noted as the route to a tail index of
  dislocation severity once the battery is large enough to fit one.
- LSE ST455, Reinforcement Learning (Shi), lecture 9 (model based
  reinforcement learning and planning) and QMUL ECS7002P, AI in Games, lab 3
  (Monte Carlo tree search and stochastic games): Auer, P., Cesa-Bianchi, N.
  and Fischer, P. (2002), "Finite-time analysis of the multiarmed bandit
  problem", *Machine Learning* 47, 235-256; Kocsis, L. and Szepesvari, C.
  (2006), "Bandit based Monte-Carlo planning", *ECML 2006*. Behind the UCB1
  adversary in `redteam.py`.
- KCL 6CCS3AIN, Artificial Intelligence Reasoning and Decision Making
  (Kohan Marzagao), week 9, consensus mechanisms, the voter model: Clifford,
  P. and Sudbury, A. (1973), "A model for spatial conflict", *Biometrika*
  60(3), 581-588; Holley, R. A. and Liggett, T. M. (1975), "Ergodic theorems
  for weakly interacting infinite systems and the voter model", *Annals of
  Probability* 3(4), 643-663. Behind the `voter` generator.
- LSE Regulation, Strategy and Enforcement (Baldwin), enforcement and
  better regulation: Ayres, I. and Braithwaite, J. (1992), *Responsive
  Regulation: Transcending the Deregulation Debate*, Oxford University Press;
  Baldwin, R. and Black, J. (2008), "Really responsive regulation", *Modern
  Law Review* 71(1), 59-94; Parker, C. and Lehmann Nielsen, V. (2009),
  "Corporate compliance systems", *Administration and Society* 41(1), 3-37;
  HM Government (2023), *Better Regulation Framework: guidance*. Behind the
  responsive ladder rule and the impact assessment summary.
- QMUL, International Financial Regulation and Banking Standards (Walker):
  the framing of supervisory objectives and market integrity in the briefing;
  no method was taken from these notes.

## Industry context

- Simudyne (London): agent based simulation for banks and regulators;
  licensed the U.S. Office of Financial Research crisis model; Barclays led
  its Series A. Context for why authorities buy simulation rather than build
  it, and why HSL is open and replayable.
- Solidus Labs (New York): trade surveillance across digital and
  traditional assets; announced an agentic compliance model built on its
  HALO platform (May 2025). Context for agentic surveillance operations;
  HSL sits one step earlier, at certification of the tools such operations
  rely on.
