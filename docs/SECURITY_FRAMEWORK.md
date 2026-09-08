# HSL security framework

This document is the platform's security argument, organised by the
chapters of Ross Anderson, *Security Engineering: A Guide to Building
Dependable Distributed Systems*, 3rd edition (Wiley, 2020). Each section
states what the chapter argues, what it implies for a supervisory sandbox,
and which control in the code carries it. `python -m hsl.security posture`
checks the deployment against the controls; the `SEC` panel shows the same
check live, and the result is written into `artefacts.json` at release. A
failing control blocks Gate 2.

## 1. What is security engineering (chapter 1)

The book opens with the point that security is a system property: policy,
mechanism, assurance and incentives together. HSL's policy is written
(this document and the ATRS record), its mechanisms are in `hsl/security.py`,
`hsl/ingest.py`, `hsl/connectors.py`, `hsl/ledger.py` and the gates, its
assurance is the test suite, the critic and the posture check, and its
incentives are the named roles at the gates.

## 2. Who is the opponent (chapter 2)

Threat model, in order of likelihood for a regulator's sandbox:

- An insider who wants a certification to come out a particular way:
  addressed by separation of duty at the gates, a signed ledger that records
  every refusal and reason, and a critic that recomputes the headline claims
  from the rows.
- A firm whose agents adapt to the certified sentinel: addressed by the red
  team, the sentinel against evader game and the robustness margin.
- Anyone who can put text in front of the model: addressed by the injection
  suite, fixed prompts, bounded planner output and number vetting.
- An attacker on the network or the supply chain: addressed by the air gap
  by default, the egress allowlist, the asset hash manifest and pinned
  dependencies.
- The platform's own authors: addressed by the fact that every number in a
  briefing or a transparency record must appear in the artefacts.

## 3. Psychology and usability (chapter 3)

Security that fights the user fails. Gate refusals require a reason and
record it; approvals bind to a hash the approver can see; the emergency
stop is one click and never asks for confirmation; nothing is hidden in a
setting. Warnings in the posture check say what to do, not just what is
wrong.

## 4. Protocols and 5. cryptography (chapters 4 and 5)

The ledger is a hash chain with an HMAC over each entry under a key held
only in the environment (`HSL_SECRET`); replay verifies both the chain and
the signatures. Credentials for connectors are read from `HSL_KEY_<SOURCE>`
and never written to a file, a ledger entry or a log line. Transport
security is the proxy's job: the deployment files terminate TLS in front
of the service, and the service binds to the loopback.

## 6. Access control (chapter 6)

Roles and least privilege: `viewer` (view, ask), `preparer` (plan, upload,
fetch), `approver` (gate, stop), `admin`. In header auth mode the role and
identity come from the authenticating proxy (`X-HSL-Role`, `X-HSL-User`);
in open mode, a demo, every caller is admin and the posture check says so.
The gate callback refuses an action a role does not hold before it does
anything else.

## 7. Distributed systems (chapter 7)

Concurrency and naming: one run at a time under a lock; run identifiers are
time ordered and unique; the battery hash names the exact set of scenarios
an approval covers; a persona table is bound by hash so a replay refuses a
changed table.

## 8. Economics (chapter 8)

The people who bear the cost of a bad certification (consumers, the market)
are not the people who choose the tool. HSL makes the cost visible: the
cost frontier, the burden by participant class, the proportionality test
in the appraisal, and evidence grades that fall when a claim rests on few
scenarios.

## 9. Multilevel security and 10. boundaries (chapters 9 and 10)

The sandbox is a low classification compartment. Data classification
(`synthetic`, `public`, `pseudonymised`, `licensed`) is attached at
quarantine; `confidential` and `personal` are refused, not stored. The no
write down rule: `pseudonymised` and `licensed` rows may enter a run
directory but never an evidence pack, which carries their hash and
aggregates only. One quarantine boundary serves uploads and connectors
alike, so no path around it exists.

## 11. Inference control (chapter 11)

Observed per participant data yields counts and shares, never identifiers,
and a window with fewer than the query set size (five participants) yields
no per participant output at all. The network panel's inspector shows
agents of synthetic markets only.

## 12. Banking and bookkeeping (chapter 12)

The chapter's model of a well run ledger, dual control and the Clark
Wilson integrity model (well formed transactions, separation of duty,
audit) is HSL's control architecture: the append only signed ledger, the
two gates held by different people, and the critic as the integrity
verification procedure that no transaction can bypass.

## 21. Network attack and defence (chapter 21)

Outbound: connectors are off by default; when on, only named hosts, HTTPS
only, no redirect to another host, a timeout and a size cap. Inbound: the
service listens on the loopback, every response carries a content security
policy, `nosniff`, `no-store` and `frame-ancestors 'self'`; ASK is rate
limited per identity; uploads are limited by size and type; CSV and JSON
only; spreadsheet formula injection is refused on the way in and
neutralised on the way out.

## 26. Surveillance or privacy (chapter 26)

The platform holds no personal data by design and checks that it does not:
the identifier scan refuses a dataset rather than redacting it, because a
redacted file still records that the data existed. The transparency record
states the same in the data section.

## 27. Secure systems development and 28. assurance (chapters 27 and 28)

Pinned dependencies; vendored front end assets with a sha256 manifest
verified at posture time (`python -m hsl.security manifest` after any asset
change, `verify` to check); 72 unit tests and a browser test; the critic's
checks recorded per run; an evidence pack any third party can replay;
sample outputs shipped with the code so a reviewer can compare.

## 29. Beyond "computer says no" (chapter 29)

The book closes on accountability. HSL's answer is the named preparer and
approver with their functions, the reasons recorded for every refusal, the
transparency record written for the accountable owner, and the rule that
nothing here recommends a live intervention.

## Residual risks

- Open auth mode is a demonstration setting; production needs the proxy.
- The posture check is a self check, not a penetration test.
- The connectors to licensed sources depend on vendor client libraries
  that were not exercised in the sandbox; only the replay path is tested.
- Quarantine scans are pattern based; a determined uploader could evade
  the identifier scan, which is why classification is also declared and
  recorded against a name.
