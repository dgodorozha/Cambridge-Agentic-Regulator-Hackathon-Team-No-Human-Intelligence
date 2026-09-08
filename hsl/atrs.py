"""Algorithmic transparency record, generated from the run.

The UK Algorithmic Transparency Recording Standard (ATRS) is the register a
public body keeps of the algorithmic tools it uses in decisions with public
effect: a plain language summary (tier 1) and a detailed record (tier 2)
covering the owner and the accountable senior manager, the description and
rationale, how the tool sits in the decision process, its specification,
its data, and its risks and mitigations. It is mandatory for UK central
government departments and the arm's length bodies that deliver public
services; the Data Standards Authority recommends it across the wider
public sector.

HSL writes a record in that structure at release, from the artefacts and
the approvals of the run and nothing else, so an authority that adopts
the tool has the register entry ready and every figure in it traceable to
the evidence pack. The critic vets the record's numbers against the
artefacts the same way it vets the briefing. The field names follow the
published ATRS template; a record is a draft for the accountable owner to
review, not a published entry.
"""

import datetime

from . import __version__
from .sentinels import SENTINEL_LABELS


def _f(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _lab(n):
    return SENTINEL_LABELS.get(n, str(n).replace("_", " "))


def atrs_record(artefacts, approvals, run_id, organisation="", team="", contact=""):
    """Structured record (dict) in ATRS tiers and sections."""
    a = artefacts
    bat = a.get("battery", {})
    g = a.get("decision_gap", {})
    gb = a.get("decision_gap_bootstrap", {})
    prov = a.get("provenance", {})
    inj = (a.get("redteam") or {}).get("injection") or {}
    cf = a.get("conformal") or {}
    ap = a.get("appraisal") or {}
    gate2 = approvals.get("gate2") or {}
    gate1 = approvals.get("gate1") or {}
    approver = gate2.get("actor") or gate1.get("actor") or ""
    approver_role = gate2.get("role") or gate1.get("role") or approvals.get("approver_role") or ""
    preparer = approvals.get("preparer") or ""
    preparer_role = approvals.get("preparer_role") or ""
    certified = a.get("certified")
    first_cf = next(iter(cf.values())) if cf else {}
    model = prov.get("model") if prov.get("llm_enabled") else None
    today = datetime.date.today().isoformat()

    tier1 = {
        "name": "Herding Scenario Lab (HSL)",
        "description": ("A decision first sandbox in which a public authority stress tests candidate "
                        "surveillance sentinels and intervention rules against synthetic AI agent markets "
                        "and certifies them on decision accuracy rather than aggregate fidelity. Outputs "
                        "are comparative rankings on a declared scenario battery with intervals; the tool "
                        "never trades, never touches live market data and never recommends live intervention."),
        "website_url": "",
        "contact_email": contact,
    }
    owner = {
        "organisation": organisation,
        "team": team,
        "senior_responsible_owner": approver,
        "senior_responsible_owner_role": approver_role,
        "senior_responsible_owner_register": ((gate2.get("register") or gate1.get("register") or {}).get("irn", "")
                                              and f"{(gate2.get('register') or gate1.get('register'))['function']}, "
                                                  f"reference {(gate2.get('register') or gate1.get('register'))['irn']}, "
                                                  f"{(gate2.get('register') or gate1.get('register'))['source']}") or "",
        "record_prepared_by": preparer,
        "record_prepared_by_role": preparer_role,
        "external_supplier_involvement": ("A frontier language model is called for battery planning, "
                                          "persona distillation and briefing prose, single shot and server "
                                          f"side ({model})." if model else
                                          "None. No external model is configured; every path runs "
                                          "deterministically from the artefacts."),
        "data_access_processing_or_sharing": "No data leaves the authority's environment; the run is "
                                             "synthetic and self contained.",
    }
    description = {
        "detailed_description": (
            f"Version {__version__}. Each run plans a battery of synthetic markets ({bat.get('n_scenarios')} "
            f"scenarios in {len(bat.get('families', []))} families on this run), simulates them, scores "
            f"{g.get('n_tools')} surveillance sentinels on aggregate fidelity and on decision accuracy "
            f"(which agents are destabilising), scores {len(a.get('rules', {}))} intervention rules on "
            f"containment and false halts, and reports the decision gap between the two rankings with a "
            f"bootstrap probability of inversion, a conformal false alert guarantee, counterfactual "
            f"attribution, a truth dependence audit, a cost frontier, tail risk and survival measures, a red "
            f"team and a regulatory options appraisal."),
        "scope": ("Certification of surveillance tools and calibration of intervention rules for agentic "
                  "herding and market manipulation, in market monitoring, policy design and supervision. "
                  "Out of scope: live surveillance, enforcement decisions about any firm or person, and "
                  "any use with real personal or confidential supervisory data."),
        "benefit": ("Replaces certification on aggregate fidelity, which on this run ranks the tools "
                    f"close to the reverse of their decision accuracy (decision gap {_f(g.get('decision_gap'))}, "
                    f"probability of inversion {_f(gb.get('p_inversion'))}), with certification on the decision "
                    "the tool exists to inform, with intervals, a guarantee and a replayable trail."),
        "previous_process": ("Back tests against historical episodes containing almost no agentic herding, "
                             "and validation of synthetic environments on aggregate statistics."),
        "alternatives_considered": ("Do nothing (the untreated herd is the baseline in every run); monitor and "
                                    "warn without intervention (the non regulatory option in the appraisal); "
                                    "a fixed battery instead of a model planned one (the fixed battery is the "
                                    "fallback whenever no model is configured or its plan fails validation)."),
    }
    decision = {
        "process_integration": ("The tool sits before certification. A policy officer poses a question; the "
                                "battery is approved at Gate 1 by a named approver; the run executes; the "
                                "critic verifies; the briefing is released at Gate 2 by a named approver. The "
                                "briefing is advisory input to a supervisory decision taken by people."),
        "provided_information": ("A ranked evidence graded briefing, the artefacts with intervals, the signed "
                                 "ledger and the evidence pack; on this run the tool certified within the "
                                 f"false alert budget is {_lab(certified)}."),
        "frequency_and_scale_of_usage": "Per policy question; each run is a few minutes on one machine.",
        "human_decisions_and_review": ("Two mandatory human gates with refusal and recorded reasons; four eyes "
                                       "between preparer and approver; an emergency stop that halts execution "
                                       "and seals the partial ledger; the autonomy gate reports how much "
                                       "execution the evidence would back and defaults to none."),
        "required_training": ("Familiarity with the decision gap, the false alert budget, the evidence grades "
                              "and the limitations section of the briefing; the ASK page answers questions "
                              "from the artefacts only."),
        "appeals_and_review": ("Every figure is recomputed from per scenario rows by the critic and can be "
                               "replayed from the evidence pack by a third party; gate refusals and reasons "
                               "are in the ledger."),
    }
    spec = {
        "system_architecture": ("Planner, scenario synthesiser (agent based market simulator with RL traders "
                                "and distilled LLM personas), sentinels under test, intervention harness, "
                                "evaluator, attribution, audits, red team, critic, drafter, signed ledger. "
                                "Pure Python; runs offline."),
        "phase": "Prototype (hackathon build); pilot with delayed pseudonymised venue data is the next phase.",
        "maintenance": "Versioned code with a changelog; every run records the software and library versions.",
        "models": ("Tabular Q learning traders; distilled persona policy tables (hashed); eight sentinels "
                   "(volatility, correlation, network, absorption ratio, imbalance, endogeneity, lead lag, "
                   "tail dependence); a model based learned intervention policy (advisory)"
                   + (f"; {model} for planning, personas and prose." if model else ".")),
        "software_versions": {k: v for k, v in prov.items() if k in ("hsl_version", "python", "numpy", "scipy",
                                                                     "networkx", "platform")},
    }
    dsets = [e["summary"] for e in ((a.get("data") or {}).get("datasets") or [])]
    data = {
        "source_data_name": ("Synthetic scenario battery generated by the HSL simulator"
                             + (", plus observed datasets brought through quarantine: "
                                + ", ".join(f"{x['name']} ({x['classification']}, sha256 {x['sha256'][:16]})"
                                            for x in dsets) if dsets else "")),
        "data_modality": "Simulated prices, returns and per agent order flows",
        "data_description": (f"{bat.get('n_scenarios')} scenarios, seeds recorded, battery hash "
                             f"{str(prov.get('battery_hash', ''))[:16]}; generators "
                             f"{', '.join(bat.get('generators', []))}."),
        "data_quantities": f"{bat.get('n_scenarios')} runs of up to 600 steps and up to 150 agents",
        "sensitive_attributes": ("None. No personal data, no confidential supervisory information"
                                 + ("; licensed or pseudonymised rows stay in the run directory and are not in the evidence pack."
                                    if any(not x["packable"] for x in dsets) else ", no proprietary datasets.")),
        "data_completeness_and_representativeness": (
            "Synthetic by design; the battery is anchored to published ranges and includes held out "
            "families with a different population; the truth dependence audit reports whether rankings "
            "survive a change of generator."),
        "source_data_url": "",
        "data_collection": "Generated at run time from recorded seeds.",
        "data_cleaning": "Not applicable.",
        "data_sharing_agreements": "None required.",
        "data_access_and_storage": "Run directory under the authority's control; evidence pack with a manifest.",
    }
    risks = [
        {"name": "Sim to real gap", "mitigation": "Synthetic only; comparative rankings with intervals, never "
                                                  "forecasts; provenance and anchoring recorded."},
        {"name": "Certification that only holds under one generator",
         "mitigation": "Truth dependence audit under alternative generators; the briefing states whether rank "
                       "one survives."},
        {"name": "False alert budget that is only an estimate",
         "mitigation": (f"Conformal threshold with a finite sample guarantee at {_f(first_cf.get('alpha'))} on "
                        f"{first_cf.get('n_calibration')} calibration scenarios." if first_cf else
                        "Conformal threshold with a finite sample guarantee.")},
        {"name": "A certified tool an adversary can evade",
         "mitigation": "Budgeted adversarial search and the sentinel against evader game; robustness margin in "
                       "the briefing."},
        {"name": "Prompt injection through model facing surfaces",
         "mitigation": (f"Injection suite on every run; {inj.get('n_contained')} of {inj.get('n_cases')} cases "
                        f"contained on this run; the critic requires every case contained." if inj else
                        "Injection suite on every run; the critic requires every case contained.")},
        {"name": "Hallucinated figures in prose",
         "mitigation": "Every number is computed, not generated; the critic vets every number in the briefing "
                       "and in this record against the artefacts at printed precision."},
        {"name": "Overreliance and false confidence",
         "mitigation": "Evidence grades and limitations in every briefing; named human release; advisory only."},
        {"name": "Interruption of legitimate participants by a rule",
         "mitigation": ("Burden by participant class, false halt rate, proportionality test in the options "
                        "appraisal" + (f"; the appraisal recommends tier {ap['recommended']['tier']} "
                                       f"({ap['recommended']['tier_label']})." if ap.get("recommended") else
                                       "; no rule passed all tests on this run.")) if ap else
                       "Burden by participant class and false halt rate."},
    ]
    impact = [{"name": "HSL critic report",
               "description": "Independent checks recomputed from the per scenario rows at release",
               "date": today, "link": "critic.json in the evidence pack"},
              {"name": "Ledger replay", "description": "Hash chained, HMAC signed record of every step and gate",
               "date": today, "link": "ledger.jsonl in the evidence pack"}]
    return {"standard": "Algorithmic Transparency Recording Standard (UK), structure of the published template",
            "status": "draft for the accountable owner's review; not a published record",
            "run_id": run_id, "date": today, "hsl_version": __version__,
            "tier_1": tier1,
            "tier_2": {"owner_and_responsibility": owner, "description_and_rationale": description,
                       "decision_making_process": decision, "tool_specification": spec, "data": data,
                       "risks_mitigations_and_impact_assessments": {"risks": risks, "impact_assessments": impact}}}


def render_markdown(rec):
    L = []
    w = L.append
    w("# Algorithmic transparency record: Herding Scenario Lab")
    w("")
    w(f"Structure: {rec['standard']}. Status: {rec['status']}. Run {rec['run_id']}, {rec['date']}, "
      f"HSL {rec['hsl_version']}.")
    w("")
    w("## Tier 1")
    w("")
    for k, v in rec["tier_1"].items():
        w(f"- **{k.replace('_', ' ')}**: {v or 'to be completed'}")
    w("")
    w("## Tier 2")
    for sec, body in rec["tier_2"].items():
        w("")
        w(f"### {sec.replace('_', ' ').capitalize()}")
        w("")
        if sec == "risks_mitigations_and_impact_assessments":
            w("| Risk | Mitigation |")
            w("|---|---|")
            for r in body["risks"]:
                w(f"| {r['name']} | {r['mitigation']} |")
            w("")
            w("| Impact assessment | Description | Date | Link |")
            w("|---|---|---|---|")
            for i in body["impact_assessments"]:
                w(f"| {i['name']} | {i['description']} | {i['date']} | {i['link']} |")
        else:
            for k, v in body.items():
                if isinstance(v, dict):
                    v = ", ".join(f"{kk} {vv}" for kk, vv in v.items())
                w(f"- **{k.replace('_', ' ')}**: {v if v not in (None, '') else 'to be completed'}")
    w("")
    w("Every figure above is read from the artefacts of the run and vetted by the critic; blank fields are "
      "for the adopting authority to complete.")
    return "\n".join(L) + "\n"
