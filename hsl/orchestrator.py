"""Orchestrator: plans the scenario battery from a policy question, enforces
the two human approval gates, runs the pipeline, chains every step into the
signed rationale ledger and drafts the supervisory briefing.

Gate 1: named sign off of the exact battery (by hash) before any simulation.
Gate 2: named approval before the briefing is written to disk, armed only
        after the critic passes.

Batch use:
  python -m hsl.orchestrator --approve-battery --approve-briefing \
      --approver "R. Ahmed" --preparer "D. Godorozha" --outdir runs/cli

Replay of an evidence pack:
  python -m hsl.orchestrator --battery battery.json --approve-battery \
      --approve-briefing --approver "<name>" --outdir replay
"""

import argparse
import datetime
import json
import os
import secrets
import sys

from . import provenance
from .briefing import draft_briefing, to_html
from .critic import critic_check
from .evidence import build_pack
from .ledger import Ledger, NumpyEncoder, verify
from .atrs import atrs_record, render_markdown
from .reports import exchange_record
from .families import FamilyStore, validate_family, expand_family, load_family_file, family_hash
from .agents import AgentRegistry, validate_agent, register as register_agent, load_agent_file, bind_agent_hashes, agent_hash, registry_snapshot as agents_snapshot
from .simulator import CUSTOM_NOTES
from .ingest import quarantine, empirical_family, persist_datasets, keep_recent
from .calibrate import calibrate, calibrated_family, hybrid_family, observed_snapshot, register_observed
from .question import interpret as interpret_question, question_family
from .register import PersonRegister

register_match = None
from .security import posture
from .personas import bind_persona_hashes, register, PersonaPolicy, registry_snapshot
from .pipeline import run_battery
from .simulator import ScenarioSpec, scenario_battery, battery_hash

DEFAULT_Q = ("Would a sentinel informed dynamic throttle have contained a "
             "flash dislocation with 40 per cent of agents on one foundation "
             "model vendor, and which surveillance candidate should be "
             "certified?")


def new_run_id():
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def include_families(specs, log, family_docs=None, store=None, author=""):
    """Add the authority's own families to a planned battery: documents
    passed directly (CLI --family) and the enabled families of the store.
    Every inclusion is validated and logged with the definition's hash."""
    added = []
    docs = list(family_docs or [])
    if store is not None:
        docs.extend(x["family"] for x in store.enabled())
    for doc in docs:
        ok, fam, errors, notes = validate_family(doc)
        if not ok:
            log("family_rejected", name=str(doc.get("name", ""))[:40], errors=errors)
            continue
        if any(s.family == fam["name"] for s in specs):
            continue
        new = expand_family(fam)
        specs.extend(new)
        CUSTOM_NOTES[fam["name"]] = (fam["note"] or "custom family") + " (defined by the authority)"
        log("family_included", name=fam["name"], sha256=family_hash(fam), n_scenarios=len(new),
            author=author, clamped=notes, holdout=fam["holdout"], quiet=fam["quiet"])
        added.append(fam["name"])
    return added


def demo_battery(specs):
    """The three minute profile: one scenario each of the strong herd, the
    evader, the colluding ignition, the faulty vendor model and the LLM
    persona monoculture, three quiet markets and one held out pair, all at
    400 steps and 100 agents so the whole run fits a demonstration. Declared
    in the ledger; never a certification battery."""
    import dataclasses
    keep = {"herd_high": 1, "evader": 1, "ignition": 1, "vendor_fault": 1, "persona_llm": 1, "quiet": 3,
            "holdout_herd": 1, "holdout_quiet": 1}
    out, seen = [], {}
    for sp in specs:
        if sp.family not in keep or seen.get(sp.family, 0) >= keep[sp.family]:
            continue
        seen[sp.family] = seen.get(sp.family, 0) + 1
        shift = 200 - (sp.shock_time or 300)
        changes = {"t_steps": 400, "n_agents": min(sp.n_agents, 100)}
        if sp.shock_time is not None:
            changes["shock_time"] = 200
        for f in ("ignition_time", "vendor_fault_time", "liquidity_withdrawal_time"):
            v = getattr(sp, f)
            if v is not None:
                changes[f] = max(20, v + shift)
        out.append(dataclasses.replace(sp, **changes))
    return out


def include_agents(log, agent_docs=None, registry=None, author=""):
    """Register the authority's agent templates: documents passed directly
    (CLI --agent) and the stored registry. Every registration is validated
    and logged with the definition's hash."""
    names = []
    if registry is not None:
        names.extend(registry.load_all())
    for doc in (agent_docs or []):
        ok, ag, errors, notes = validate_agent(doc)
        if not ok:
            log("agent_rejected", name=str(doc.get("name", ""))[:40], errors=errors)
            continue
        register_agent(ag)
        log("agent_registered", name=ag["name"], sha256=agent_hash(ag), author=author, clamped=notes)
        names.append(ag["name"])
    return names


def plan_battery(question: str, log, client=None, data_files=None, data_class="public",
                 family_docs=None, store=None, author="", agent_docs=None, registry=None):
    """Parse the policy question into a scenario battery. With a model
    configured the herding families are model planned within hard bounds;
    otherwise (and always for the guardrail families) the fixed battery."""
    used_llm = False
    if client is not None and client.available:
        from .llm import plan_battery_llm
        specs, used_llm = plan_battery_llm(question, client, log)
    else:
        demo = os.environ.get("HSL_ASSURANCE", "").strip().lower() == "demo"
        specs = scenario_battery(seeds_per=1 if demo else int(os.environ.get("HSL_SEEDS", "3")),
                                 include_rl=not demo)     # no RL population to train in the three minute profile
    if os.environ.get("HSL_ASSURANCE", "").strip().lower() == "demo":
        specs = demo_battery(specs)
        log("demo_battery", n_scenarios=len(specs), families=sorted({s.family for s in specs}),
            note="twelve short scenarios for a three minute demonstration; not a certification battery")
    for path in (data_files or []):
        try:
            with open(path, "rb") as f:
                ds = quarantine(os.path.basename(path), f.read(), classification=data_class)
            if ds.get("ok"):
                specs.extend(empirical_family(ds))
                cal = calibrate(ds)
                ds["calibration"] = cal
                if cal:
                    specs.extend(calibrated_family(ds, cal))
                    specs.extend(hybrid_family(ds, cal))
                    log("dataset_calibrated", name=ds["name"], sha256=ds["sha256"], params=cal["params"],
                        diagnostics=cal["diagnostics"], clamped=cal["clamped"], params_sha256=cal["params_sha256"])
        except OSError as e:
            log("dataset_unreadable", path=str(path)[:200], error=str(e)[:120])
    if os.environ.get("HSL_ASSURANCE", "").strip().lower() == "demo":
        # one scenario per data driven family keeps the demonstration inside three minutes
        seen_d = {}
        trimmed = []
        for sp in specs:
            fam = sp.family
            if fam == "empirical" or fam.startswith("calibrated_") or fam.startswith("hybrid_"):
                if seen_d.get(fam, 0) >= 1:
                    continue
                seen_d[fam] = 1
            trimmed.append(sp)
        specs = trimmed
    include_agents(log, agent_docs, registry, author)
    include_families(specs, log, family_docs, store, author)
    # the question, read deterministically: a family for the case it names
    parse = interpret_question(question)
    if parse["family"] and not any(s.family == "question" for s in specs):
        specs.extend(question_family(parse, log))
    elif not parse["interpreted"]:
        log("question_not_interpreted", question=(question or "")[:300])
    bind_agent_hashes(specs, log)
    personas = bind_persona_hashes(specs, client if (client is not None and client.available) else None, log)
    log("battery_planned", question=question, n_scenarios=len(specs),
        scenarios=[s.name for s in specs], battery_hash=battery_hash(specs),
        planner="llm" if used_llm else "fixed",
        personas={k: {"source": v["source"], "table_sha256": v["table_sha256"]}
                  for k, v in personas.items()})
    return specs


def specs_from_file(path):
    with open(path) as f:
        data = json.load(f)
    specs = data.get("specs", data) if isinstance(data, dict) else data
    if isinstance(data, dict):
        for ag in (data.get("agents") or {}).values():
            register_agent({k: v for k, v in ag.items() if k != "sha256"})
        for sha, series in (data.get("observed_series") or {}).items():
            register_observed(sha, series)
        for name, p in (data.get("personas") or {}).items():
            register(PersonaPolicy(name, p["table"], p.get("source", "replayed"),
                                   p.get("description", ""), p.get("prompt_sha256", ""),
                                   p.get("model")))
    out = []
    for d in specs:
        d = dict(d)
        for k in ("vendor_shares", "vendor_rhos"):
            if k in d:
                d[k] = tuple(d[k])
        if d.get("custom_agents"):
            d["custom_agents"] = tuple((str(a), float(b)) for a, b in d["custom_agents"])
        if d.get("custom_agent_hashes"):
            d["custom_agent_hashes"] = tuple(str(h) for h in d["custom_agent_hashes"])
        out.append(ScenarioSpec(**d))
    return out


def gate(name, approved, approver, log, extra=None):
    log("gate", actor=approver or "unknown", gate=name, decision="approved" if approved else "refused",
        register=(register_match if approved else None),
        approver=approver, **(extra or {}))
    if not approved:
        raise SystemExit(
            f"[GATE] {name} requires human approval. Re-run with the "
            f"corresponding --approve flag and --approver <name>.")


def write_run_files(outdir, artefacts, extras, specs):
    def dump(name, obj):
        with open(os.path.join(outdir, name), "w") as f:
            json.dump(obj, f, indent=1, cls=NumpyEncoder)
    dump("artefacts.json", artefacts)
    dump("rows.json", extras["rows"])
    dump("aut.json", extras["aut"])
    dump("net.json", extras["net"] or [])
    used = {s.persona for s in specs if s.persona_share > 0 and s.persona}
    dump("battery.json", {"battery_hash": battery_hash(specs),
                          "specs": [s.describe() for s in specs],
                          "personas": {k: v for k, v in registry_snapshot().items() if k in used},
                          "agents": {k: v for k, v in agents_snapshot().items()
                                     if any(k == a for s in specs for a, _ in s.custom_agents)},
                          "observed_series": {k: v for k, v in observed_snapshot().items()
                                              if any(s.hybrid_sha == k for s in specs)}})
    dump("tapes.json", extras["tapes"])
    dump("three.json", extras["three"])


def run_pipeline(question, outdir, approve_battery=False, approve_briefing=False,
                 approver=None, preparer=None, battery_file=None, secret=None,
                 approver_role=None, preparer_role=None, data_files=None, data_class="public",
                 client=None, four_eyes=False, family_files=None, families_store=None, agent_files=None,
                 register_path=None, register_required=None):
    os.makedirs(outdir, exist_ok=True)
    run_id = new_run_id()
    secret = secret or os.environ.get("HSL_SECRET") or None
    log = Ledger(os.path.join(outdir, "ledger.jsonl"), run_id, secret=secret,
                 actor="orchestrator")
    log("run_started", actor=preparer or "cli", question=question, preparer=preparer,
        provenance=provenance())

    specs = specs_from_file(battery_file) if battery_file else plan_battery(
        question, log, client, data_files=data_files, data_class=data_class,
        family_docs=[d for f in (family_files or []) for d in load_family_file(f)],
        store=FamilyStore(families_store) if families_store else None, author=preparer or "",
        agent_docs=[d for f in (agent_files or []) for d in load_agent_file(f)],
        registry=AgentRegistry(families_store) if families_store else None)
    if battery_file:
        log("battery_loaded", path=battery_file, n_scenarios=len(specs),
            battery_hash=battery_hash(specs))
    bh = battery_hash(specs)
    if four_eyes and approver and preparer and approver.strip().lower() == preparer.strip().lower():
        raise SystemExit("[GATE] four eyes: the approver must differ from the preparer.")
    from .register import is_dev_identity, dev_mode_on
    if dev_mode_on():
        if preparer and is_dev_identity(preparer) and not preparer_role:
            preparer_role = preparer.strip()
        if approver and is_dev_identity(approver) and not approver_role:
            approver_role = approver.strip()
    if preparer and not preparer_role:
        raise SystemExit("[GATE] the preparer's function is required (--preparer-role), for example 'certified function'"
                         + (" or Developer1 in dev mode." if dev_mode_on() else "."))
    if approver and (approve_battery or approve_briefing) and not approver_role:
        raise SystemExit("[GATE] the approver's function is required (--approver-role), for example 'SMF24'"
                         + (" or Developer2 in dev mode." if dev_mode_on() else "."))
    register = PersonRegister(register_path or None, required=(register_required or None))
    global register_match
    register_match = None
    if approver and (approve_battery or approve_briefing):
        verdict = register.check(approver, approver_role)
        if not verdict["ok"]:
            raise SystemExit(f"[GATE] register: {verdict['reason']}")
        register_match = verdict.get("match")
        if register_match and not approver_role:
            approver_role = register_match["function"]
    gate("scenario_battery_signoff", approve_battery, approver, log, {"battery_hash": bh})
    g1_ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    from config import Config as _Cfg
    datasets = []
    for path in (data_files or []):
        with open(path, "rb") as f:
            ds = quarantine(os.path.basename(path), f.read(), uploader=preparer or "", classification=data_class)
        log("dataset_quarantine", name=os.path.basename(path), ok=ds.get("ok"), reason=ds.get("reason"),
            sha256=ds.get("sha256"), classification=data_class)
        if not ds.get("ok"):
            raise SystemExit(f"[DATA] {path} refused: {ds.get('reason')}")
        datasets.append(ds)
    datasets = keep_recent(datasets)
    for ds in datasets:                       # the fit planned with travels with the dataset into the artefacts
        if ds.get("ok") and "calibration" not in ds:
            ds["calibration"] = calibrate(ds)
    if datasets:
        idx = persist_datasets(datasets, outdir)
        log("datasets_persisted", files=[x["file"] for x in idx], packable=[x["file"] for x in idx if x["packable"]])
    artefacts, extras = run_battery(specs, log, question=question,
                                    assurance=_Cfg().assurance_budget, datasets=datasets or None)
    artefacts["security"] = posture(_Cfg(), datasets=[{"name": d["name"], "classification": d["classification"]}
                                                     for d in datasets])
    log("security_posture", status=artefacts["security"]["status"], n_fail=artefacts["security"]["n_fail"],
        n_warn=artefacts["security"]["n_warn"])
    write_run_files(outdir, artefacts, extras, specs)

    critic = critic_check(artefacts, rows=extras["rows"], approved_battery_hash=bh,
                          ledger_path=log.path, secret=secret, log=log)
    if not critic["ok"]:
        with open(os.path.join(outdir, "critic.json"), "w") as f:
            json.dump(critic, f, indent=1)
        raise SystemExit("[CRITIC] verification failed; Gate 2 is sealed. See critic.json.")

    approvals = {"preparer": preparer, "preparer_role": preparer_role or "",
                 "gate1": {"actor": approver, "role": approver_role or "", "ts": g1_ts, "register": register_match}}
    text = draft_briefing(artefacts, critic, approvals, run_id)
    used_llm = False
    if client is not None and client.available:
        from .llm import draft_briefing_llm
        text, used_llm = draft_briefing_llm(artefacts, client, text, log)
    record = atrs_record(artefacts, dict(approvals, approver_role=approver_role or ""), run_id)
    record_md = render_markdown(record)
    critic = critic_check(artefacts, rows=extras["rows"], approved_battery_hash=bh,
                          ledger_path=log.path, secret=secret, briefing_text=text, log=log,
                          atrs_text=record_md)
    if not critic["ok"]:
        raise SystemExit("[CRITIC] briefing failed number vetting; release refused.")
    gate("briefing_release", approve_briefing, approver, log,
         {"critic_ok": True, "llm_drafted": used_llm})
    approvals["gate2"] = {"actor": approver, "role": approver_role or "", "register": register_match,
                          "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    record = atrs_record(artefacts, dict(approvals, approver_role=approver_role or ""), run_id)
    with open(os.path.join(outdir, "atrs_record.json"), "w") as f:
        json.dump(record, f, indent=1)
    with open(os.path.join(outdir, "atrs_record.md"), "w") as f:
        f.write(render_markdown(record))
    with open(os.path.join(outdir, "exchange_record.json"), "w") as f:
        json.dump(exchange_record(artefacts, run_id), f, indent=1)
    _fw = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "SECURITY_FRAMEWORK.md")
    if os.path.isfile(_fw):
        with open(_fw) as f, open(os.path.join(outdir, "security_framework.md"), "w") as g:
            g.write(f.read())
    text = draft_briefing(artefacts, critic, approvals, run_id) if not used_llm else text
    with open(os.path.join(outdir, "briefing.md"), "w") as f:
        f.write(text)
    with open(os.path.join(outdir, "briefing.html"), "w") as f:
        f.write(to_html(text))
    with open(os.path.join(outdir, "critic.json"), "w") as f:
        json.dump(critic, f, indent=1)
    with open(os.path.join(outdir, "approvals.json"), "w") as f:
        json.dump(approvals, f, indent=1)
    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump({"run_id": run_id, "question": question, "stage": "released",
                   "preparer": preparer, "approver": approver,
                   "preparer_role": preparer_role or "", "approver_role": approver_role or "",
                   "battery_hash": bh, "decision_gap": artefacts["decision_gap"]["decision_gap"],
                   "created": g1_ts}, f, indent=1)
    log("briefing_released", actor=approver, path=os.path.join(outdir, "briefing.md"),
        approver=approver, sha256=__import__("hashlib").sha256(text.encode()).hexdigest())
    pack, manifest = build_pack(outdir)
    log("evidence_pack_built", path=pack, files=list(manifest["files"]))
    rep = verify(log.path, secret)
    return artefacts, {"run_id": run_id, "ledger": rep, "pack": pack, "critic": critic}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m hsl.orchestrator")
    ap.add_argument("--question", default=DEFAULT_Q)
    ap.add_argument("--outdir", default="runs/cli")
    ap.add_argument("--battery", default=None, help="replay a battery.json")
    ap.add_argument("--approve-battery", action="store_true")
    ap.add_argument("--approve-briefing", action="store_true")
    ap.add_argument("--approver", default=None)
    ap.add_argument("--register", default=os.environ.get("HSL_REGISTER") or None,
                    help="register of regulated persons (CSV or JSON) the approver is checked against")
    ap.add_argument("--approver-role", default=None,
                    help="the approver's SMF or certified function, recorded at the gates")
    ap.add_argument("--preparer-role", default=None)
    ap.add_argument("--family", action="append", default=None,
                    help="a JSON family document (or list) defined by the authority; repeatable")
    ap.add_argument("--families-store", default=os.environ.get("HSL_RUNS_DIR", "runs"),
                    help="directory whose families.json holds the stored families (enabled ones join the plan)")
    ap.add_argument("--agent", action="append", default=None,
                    help="a JSON agent template (or list) defined by the authority; repeatable")
    ap.add_argument("--data", action="append", default=None,
                    help="CSV or JSON dataset to bring through quarantine (repeatable)")
    ap.add_argument("--data-class", default="public",
                    help="synthetic | public | pseudonymised | licensed (confidential and personal are refused)")
    ap.add_argument("--preparer", default=None)
    ap.add_argument("--four-eyes", action="store_true")
    ap.add_argument("--llm", action="store_true", help="use the model for planning and prose if a key is set")
    args = ap.parse_args(argv)
    client = None
    if args.llm:
        from .llm import make_client
        from config import Config as _Cfg
        client = make_client(_Cfg())
    artefacts, info = run_pipeline(args.question, args.outdir, args.approve_battery,
                                   args.approve_briefing, args.approver, args.preparer,
                                   battery_file=args.battery, client=client,
                                   four_eyes=args.four_eyes, approver_role=args.approver_role, preparer_role=args.preparer_role,
                                   data_files=args.data, data_class=args.data_class,
                                   family_files=args.family, families_store=args.families_store,
                                   agent_files=args.agent, register_path=args.register)
    print(json.dumps({"run_id": info["run_id"],
                      "decision_gap": artefacts["decision_gap"],
                      "p_inversion": artefacts["decision_gap_bootstrap"]["p_inversion"],
                      "ledger": {k: info["ledger"][k] for k in ("ok", "entries", "signed")},
                      "critic_checks": info["critic"]["n_checks"],
                      "evidence_pack": info["pack"]}, indent=2))
    print(f"\nDone. See {args.outdir}/briefing.md")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
