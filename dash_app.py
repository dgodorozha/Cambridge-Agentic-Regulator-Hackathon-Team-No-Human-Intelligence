"""HSL TERMINAL v2: the supervisory workflow at terminal density, built to
be run by an authority.

Run with:  python dash_app.py   (then open http://127.0.0.1:8050)

What changed from the hackathon build (see CHANGELOG.md for the itemised
list): every run lives in its own directory under HSL_RUNS_DIR with a
signed, append only ledger; identities come from a trusted proxy header in
production and from named fields in demo mode; the preparer and the gate
approver must differ (four eyes); gates can be refused with recorded
reasons; an emergency stop halts orchestration mid run; the network panel
and the tape show the live run, indexed by scenario and step; ASK is
answered server side from the artefacts; the critic runs fourteen checks
before Gate 2 arms; the released briefing ships in an evidence pack that
any reviewer can replay.

Function codes
  1 MKT  market tape            6 CSF  case file (native pivot; Perspective one click away)
  2 NET  correlation network    7 LDG  rationale ledger
  3 GAP  decision gap           8 RUN  run control / gates / briefing
  4 SEN  sentinel telemetry     9 ASK  run oracle
  5 INT  intervention monitor   0 AUT  autonomy gate      REG  run registry     RSK  assurance (v3)
"""

import datetime
import logging
import os
import json
import re
import threading
import time
from collections import defaultdict, deque

logging.getLogger("werkzeug").setLevel(logging.ERROR)

import numpy as np  # noqa: E402
import flask
from dash import Dash, Input, Output, State, dcc, html, no_update, ctx  # noqa: E402
from dash import ClientsideFunction  # noqa: E402
from dash.exceptions import PreventUpdate  # noqa: E402
from flask import request as freq, send_from_directory, jsonify, abort  # noqa: E402

from config import Config  # noqa: E402
from runstore import RunStore, SERVABLE, utc_now  # noqa: E402
from hsl import __version__, provenance  # noqa: E402
from hsl.orchestrator import plan_battery, new_run_id, DEFAULT_Q  # noqa: E402
from hsl.pipeline import run_battery  # noqa: E402
from hsl.simulator import battery_hash, SimulationStopped, FAMILY_NOTES  # noqa: E402
from hsl.sentinels import ALL_SENTINELS, SENTINEL_LABELS  # noqa: E402
from hsl.evaluate import best_certifiable  # noqa: E402
from hsl.ledger import Ledger, verify as ledger_verify  # noqa: E402
from hsl.critic import critic_check  # noqa: E402
from hsl.atrs import atrs_record, render_markdown
from hsl.reports import exchange_record
from hsl.register import PersonRegister
from hsl._common import nice_name as _nice
from hsl.families import FamilyStore, template as family_template, BOUNDS as FAMILY_BOUNDS, MAX_FAMILIES
from hsl.agents import (AgentRegistry, template as agent_template, BOUNDS as AGENT_BOUNDS, SIGNALS as AGENT_SIGNALS,
                        MAX_AGENTS, validate_agent, probe as probe_agent)
from hsl.connectors import CONNECTORS, ConnectorError, fetch_dataset
from hsl.ingest import quarantine, empirical_family, persist_datasets, keep_recent
from hsl.calibrate import calibrate, calibrated_family, hybrid_family, observed_snapshot
from hsl.security import posture, authorize, CLASSIFICATIONS
from hsl.briefing import draft_briefing, to_html  # noqa: E402
from hsl.ask import answer as ask_answer  # noqa: E402
from hsl.llm import make_client, ask_llm, draft_briefing_llm  # noqa: E402

CFG = Config()
FAMILIES = FamilyStore(CFG.runs_dir)
REGISTER = PersonRegister(CFG.register_path or None, required=(CFG.register_required or None))
AGENTS = AgentRegistry(CFG.runs_dir)
AGENTS.load_all()
STORE = RunStore(CFG.runs_dir)
CLIENT = make_client(CFG)
BUILD = f"{__version__} {datetime.date.today().isoformat()}"
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")

AMBER, MUTED = "#f6b52a", "#5d6a80"
INFO, BAD = "#6cb5ff", "#ff5f5f"

# ---------------------------------------------------------------- state --
LOCK = threading.RLock()
STOP = threading.Event()


def _fresh_state():
    return {
        "run_id": None, "run_dir": None, "log": None, "started": None,
        "stage": "idle",     # idle|planning|planned|rejected|running|halted|evaluated|refused|released|error
        "phase": "Awaiting run control", "busy": False, "err": None,
        "seq": 0, "ticks": [], "marks": [], "alerts": [], "ledger_rows": [],
        "rev": 0, "rows_rev": 0, "net_rev": 0,
        "question": DEFAULT_Q, "preparer": None, "stop_actor": None,
        "specs": None, "battery_hash": None, "n_specs": 0,
        "sent_rows": [], "summary": None, "holdout": None,
        "gap": None, "gap_m": None, "gb": None, "gbm": None, "aut": None,
        "rules": None, "rl": None, "three": None, "tapes_done": [], "scen_current": None,
        "critic": None, "briefing": None, "artefacts": None, "approvals": {},
        "ledger_report": None, "llm_used": False,
        "assurance": {},      # version 3 stages as they complete
        "preparer_role": "",  # optional SMF or certified function of the preparer
        "datasets": [],       # quarantined datasets waiting for the next plan
        "posture": None,      # security self check (SEC panel)
        "step": "plan",       # workflow rail: plan|gate1|battery|rules|assurance|critic|gate2|released
    }


S = _fresh_state()


def _mut(**kw):
    with LOCK:
        S.update(kw)


def _bump(**kw):
    with LOCK:
        S.update(kw)
        S["rev"] += 1


def _emit_tick(scen, step, log_price):
    with LOCK:
        S["seq"] += 1
        S["ticks"].append((S["seq"], scen, int(step), float(np.exp(log_price))))


def _mark(scen, mark):
    with LOCK:
        S["seq"] += 1
        S["marks"].append((S["seq"], dict(mark, scen=scen)))


def _role():
    """Caller's role: from the proxy header in header auth mode, admin in open mode (a demo)."""
    if CFG.auth_mode == "header":
        try:
            return (flask.request.headers.get(CFG.role_header) or "viewer").strip().lower()
        except Exception:  # noqa: BLE001
            return "viewer"
    return "admin"


def _may(action):
    return authorize(_role(), action)


def _alert(lvl, msg):
    with LOCK:
        S["seq"] += 1
        S["alerts"].append((S["seq"], {"t": time.strftime("%H:%M:%S"), "lvl": lvl, "msg": msg}))


class StreamLedger(Ledger):
    """Ledger that also streams each entry into the LDG panel."""

    def __call__(self, event, actor=None, **payload):
        rec = super().__call__(event, actor=actor, **payload)
        with LOCK:
            S["seq"] += 1
            S["ledger_rows"].append((S["seq"], {
                "seq": rec["seq"], "ts": rec["ts"][11:19], "event": event,
                "actor": rec["actor"], "hash": rec["hash"][:16],
                "keys": ",".join(list(payload)[:5])}))
        return rec


# ---------------------------------------------------------- identity ------
def identity(field_value):
    """Who is acting. In header mode the trusted proxy header is the only
    source; in open (demo) mode the named field is."""
    if CFG.auth_mode == "header":
        try:
            u = (freq.headers.get(CFG.user_header) or "").strip()
        except RuntimeError:
            u = ""
        return u or None
    return (field_value or "").strip()[:80] or None


def authorised_approver(actor, role=None):
    if not actor:
        return False, "a named approver is required"
    if CFG.auth_mode == "open" and not (role or "").strip():
        return False, "the approver's function is required (an SMF or certified function" + \
            (", or Developer2 in dev mode)" if CFG.dev_mode else ")")
    if CFG.approvers and actor.lower() not in CFG.approvers:
        return False, f"{actor} is not on the approver list"
    if CFG.four_eyes and S["preparer"] and actor.strip().lower() == S["preparer"].strip().lower():
        return False, "four eyes: the approver must differ from the preparer"
    verdict = REGISTER.check(actor, role)
    if not verdict["ok"]:
        return False, verdict["reason"]
    return True, ""


# --------------------------------------------------- streaming hooks ------
def _tick_hook(spec):
    name = spec.name

    def hook(t, state):
        if len(state["prices"]):
            _emit_tick(name, t - 1, state["prices"][-1])
        if CFG.tick_pace:
            time.sleep(CFG.tick_pace)
        return {}
    return hook


def _progress(event, **kw):
    run_id = S["run_id"]
    if event == "scenario_start":
        sp, i, n = kw["spec"], kw["i"], kw["n"]
        _mut(phase=f"Battery {i + 1} of {n}: {_nice(sp.name)} simulating", scen_current=sp.name,
             step="battery")
        _alert("info", f"Battery {i + 1:02d}/{n:02d} {sp.name} running "
                       f"({FAMILY_NOTES.get(sp.family) or _nice(sp.family)})")
    elif event == "scenario_done":
        sp, res, _outs, tape = kw["spec"], kw["res"], kw["outs"], kw["tape"]
        _emit_tick(sp.name, sp.t_steps - 1, res.prices[-1])
        for m in tape["marks"]:
            _mark(sp.name, m)
        for r in kw["rows"]:
            if r["quiet"]:
                if r["false_alert"]:
                    _alert("alert", f"False alert on {_nice(r['scenario'])} from {SENTINEL_LABELS.get(r['sentinel'], r['sentinel'])}")
            elif r["first_alert"] is not None:
                lead = r["lead_time"]
                _alert("ok" if lead > 0 else "alert",
                       f"{SENTINEL_LABELS.get(r['sentinel'], r['sentinel'])} alert on {_nice(r['scenario'])} "
                       f"at t={r['first_alert']}, lead {lead:+d}, F1 {r['f1']:.2f}")
        with LOCK:
            S["sent_rows"] = S["sent_rows"] + kw["rows"]
            S["summary"] = kw["summary"]
            S["tapes_done"] = S["tapes_done"] + [{"name": sp.name, "family": sp.family,
                                                   "quiet": sp.quiet, "holdout": sp.holdout,
                                                   "shock": sp.shock_time, "T": sp.t_steps,
                                                   "post_shock_dd": round(tape["post_shock_dd"], 4),
                                                   "pre_shock_vol": round(tape["pre_shock_vol"], 2)}]
            S["rows_rev"] += 1
            S["rev"] += 1
        STORE.write_json(run_id, "rows.json", S["sent_rows"])
        if kw.get("net"):
            STORE.write_json(run_id, "net.json", kw["net"])
            with LOCK:
                S["net_rev"] += 1
    elif event == "gap":
        aut = kw["aut"]
        STORE.write_json(run_id, "aut.json", aut)
        _bump(gap=kw["gap"], gap_m=kw["gap_moments"], gb=kw["gap_bootstrap"],
              gbm=kw["gap_bootstrap_moments"], aut=aut, summary=kw["summary"],
              holdout=kw["holdout"], sent_rows=kw["rows"], step="rules",
              phase="Decision gap and autonomy gates set, scoring the intervention rules")
        g = kw["gap"]
        _alert("ok", f"Decision gap {g['decision_gap']:.2f}, tau {g['kendall_tau']:+.2f}, "
                     f"P(inversion) {kw['gap_bootstrap']['p_inversion']:.2f}")
    elif event == "rules":
        _bump(rules=kw["rules"], phase="Rules scored, measuring RL emergence")
        for rn, v in kw["rules"].items():
            _alert("info", f"Rule {v.get('label', rn)}: containment {v['containment']:.2f}, "
                           f"false halt {v['false_halt_rate']}")
    elif event == "three_worlds_start":
        _mut(phase="Three worlds, the same shock streaming")
    elif event == "assurance":
        stage = kw.pop("stage")
        labels = {"attribution": "Assurance: conformal certification and cost frontier set, attributing "
                                 "the dislocation to agent groups (Shapley)",
                  "truth_audit": "Assurance: attribution done, re running the reduced battery under "
                                 "alternative generators",
                  "concentration": "Assurance: truth audit done, sweeping vendor concentration",
                  "redteam": "Assurance: dose response done, adversarial evasion search and injection suite",
                  "done": "Assurance complete, critic running"}
        with LOCK:
            S["assurance"] = dict(S["assurance"], **kw)
            S["phase"] = labels.get(stage, "Assurance")
            S["step"] = "critic" if stage == "done" else "assurance"
            S["rev"] += 1
        if "conformal" in kw:
            cc = [k for k, v in kw["conformal"].items() if v.get("guarantee_achievable")]
            _alert("ok", f"Conformal guarantee achievable for {len(cc)} of {len(kw['conformal'])} sentinels "
                         f"at alpha {next(iter(kw['conformal'].values()))['alpha']:.2f}")
        if "attribution" in kw and kw["attribution"]:
            for e in kw["attribution"]["scenarios"]:
                _alert("info", f"Attribution of {_nice(e['scenario'])}: top impact {_nice(e['impact_ordering'][0])} "
                               f"({e['shapley'][e['impact_ordering'][0]]:.3f})")
        if "truth" in kw and kw["truth"]:
            r1 = kw["truth"].get("rank_one_under_every_generator")
            _alert("ok" if r1 else "alert",
                   (f"Truth audit: {SENTINEL_LABELS.get(r1, r1)} holds rank one under every generator"
                    if r1 else f"Truth audit: no sentinel holds rank one under every generator "
                               f"(max rank shift {kw['truth']['max_rank_shift_any']})"))
        if "dose" in kw and kw["dose"]:
            d = kw["dose"]
            _alert("info", f"Concentration: response {'convex' if d['convex'] else 'not convex'}, "
                           f"dislocation threshold share {_fmt(d.get('dislocation_threshold_share'))}")
        if "redteam" in kw and kw["redteam"]:
            ev, inj = kw["redteam"].get("evasion"), kw["redteam"].get("injection")
            if ev:
                _alert("alert" if (ev.get("robustness_margin") or 0) > 0.2 else "info",
                       f"Red team: worst case F1 {_fmt(ev.get('worst_case_f1'))} against battery "
                       f"{_fmt(ev.get('battery_f1_certified'))} for {SENTINEL_LABELS.get(ev.get('certified'), ev.get('certified'))}")
            if inj:
                _alert("ok" if inj["all_contained"] else "alert",
                       f"Injection suite: {inj['n_contained']} of {inj['n_cases']} cases contained")


# ------------------------------------------------------------ workers ----
def _worker_plan(question, preparer):
    run_id = None
    try:
        run_id = new_run_id()
        d = STORE.create(run_id)
        log = StreamLedger(os.path.join(d, "ledger.jsonl"), run_id, secret=CFG.secret,
                           actor="orchestrator")
        with LOCK:
            keep_rev = S["rev"]
            S.update(_fresh_state())
            S.update(run_id=run_id, run_dir=d, log=log, stage="planning", busy=True,
                     question=question, preparer=preparer, started=utc_now(), step="plan",
                     phase="Planning the battery, training the RL population if cold (about 20 s)",
                     rev=keep_rev + 1)
        STOP.clear()
        log("run_started", actor=preparer, question=question, preparer=preparer,
            provenance=provenance(), auth_mode=CFG.auth_mode, four_eyes=CFG.four_eyes,
            llm_enabled=CFG.llm_enabled)
        STORE.update_meta(run_id, question=question, preparer=preparer, stage="planning",
                          created=utc_now())
        _alert("info", "Plan requested, training the RL population if cold")
        specs = plan_battery(question, log, CLIENT if CFG.llm_enabled else None, store=FAMILIES,
                             author=preparer or "", registry=AGENTS)
        with LOCK:
            dsets = list(S["datasets"])
        for ds in dsets:
            log("dataset_quarantine", name=ds["name"], ok=True, sha256=ds["sha256"],
                classification=ds["classification"], n_rows=ds["n_rows"], source=ds.get("source", "upload"))
            specs.extend(empirical_family(ds))
            cal = calibrate(ds)
            ds["calibration"] = cal
            if cal:
                specs.extend(calibrated_family(ds, cal))
                specs.extend(hybrid_family(ds, cal))
                log("dataset_calibrated", name=ds["name"], sha256=ds["sha256"], params=cal["params"],
                    diagnostics=cal["diagnostics"], clamped=cal["clamped"], params_sha256=cal["params_sha256"])
        if dsets:
            idx = persist_datasets(dsets, STORE.path(run_id))
            log("datasets_persisted", files=[x["file"] for x in idx],
                packable=[x["file"] for x in idx if x["packable"]])
        if dsets:
            from hsl.simulator import battery_hash as _bh
            log("battery_extended", empirical=[s.name for s in specs if s.family == "empirical"],
                battery_hash=_bh(specs))
        bh = battery_hash(specs)
        from hsl.personas import registry_snapshot as _personas
        from hsl.agents import registry_snapshot as _agents
        used_p = {s.persona for s in specs if s.persona_share > 0 and s.persona}
        STORE.write_json(run_id, "battery.json",
                         {"battery_hash": bh, "specs": [s.describe() for s in specs],
                          "personas": {k: v for k, v in _personas().items() if k in used_p},
                          "agents": {k: v for k, v in _agents().items()
                                     if any(k == a for s in specs for a, _ in s.custom_agents)},
                          "observed_series": {k: v for k, v in observed_snapshot().items()
                                              if any(s.hybrid_sha == k for s in specs)}})
        if STOP.is_set():
            log("emergency_stop", actor=S["stop_actor"], stage="planning")
            _bump(stage="halted", phase="Emergency stop, planning halted")
            STORE.update_meta(run_id, stage="halted")
            return
        _bump(stage="planned", specs=specs, battery_hash=bh, n_specs=len(specs), step="gate1",
              phase=f"Battery planned, {len(specs)} scenarios, hash {bh[:12]}, awaiting Gate 1")
        STORE.update_meta(run_id, stage="planned", battery_hash=bh, n_scenarios=len(specs))
        _alert("ok", f"Battery planned: {len(specs)} scenarios, hash {bh[:12]}, Gate 1 armed")
    except Exception as e:  # noqa: BLE001 - surfaced to the panel
        _bump(stage="error", err=repr(e)[:300], phase="Planning failed")
        _alert("alert", f"Planning failed {e!r}"[:200])
        if run_id:
            STORE.update_meta(run_id, stage="error")
    finally:
        _mut(busy=False)


def _worker_run():
    run_id = S["run_id"]
    try:
        with LOCK:
            specs, log, q, bh = S["specs"], S["log"], S["question"], S["battery_hash"]
        t0 = time.time()
        with LOCK:
            dsets = list(S["datasets"])
        artefacts, extras = run_battery(specs, log, tick_hook=_tick_hook, progress=_progress,
                                        stop=STOP, question=q, assurance=CFG.assurance_budget,
                                        datasets=dsets or None)
        artefacts["security"] = posture(CFG, datasets=[{"name": x["name"], "classification": x["classification"]}
                                                       for x in dsets])
        log("security_posture", status=artefacts["security"]["status"], n_fail=artefacts["security"]["n_fail"],
            n_warn=artefacts["security"]["n_warn"])
        with LOCK:
            S["posture"] = artefacts["security"]
        STORE.write_json(run_id, "artefacts.json", artefacts)
        STORE.write_json(run_id, "rows.json", extras["rows"])
        STORE.write_json(run_id, "aut.json", extras["aut"])
        STORE.write_json(run_id, "net.json", extras["net"] or [])
        STORE.write_json(run_id, "tapes.json", extras["tapes"])
        STORE.write_json(run_id, "three.json", extras["three"])
        critic = critic_check(artefacts, rows=extras["rows"], approved_battery_hash=bh,
                              ledger_path=log.path, secret=CFG.secret, log=log)
        STORE.write_json(run_id, "critic.json", critic)
        rep = ledger_verify(log.path, CFG.secret)
        _bump(stage="evaluated", artefacts=artefacts, critic=critic, ledger_report=rep,
              rl=artefacts["rl_emergence"], three=extras["three"], rows_rev=S["rows_rev"] + 1,
              net_rev=S["net_rev"] + 1, step="gate2" if critic["ok"] else "critic",
              phase=f"Critic {'passed' if critic['ok'] else 'failed'}, "
                    f"{'Gate 2 armed' if critic['ok'] else 'Gate 2 sealed'}, "
                    f"run {time.time() - t0:.0f} s")
        STORE.update_meta(run_id, stage="evaluated", critic_ok=critic["ok"],
                          decision_gap=artefacts["decision_gap"]["decision_gap"],
                          p_inversion=artefacts["decision_gap_bootstrap"]["p_inversion"])
        _alert("ok" if critic["ok"] else "alert",
               f"Critic verification {'passed' if critic['ok'] else 'FAILED'} "
               f"({critic['n_checks']} checks, {critic['n_failed']} failed)")
    except SimulationStopped as e:
        log = S["log"]
        log("emergency_stop", actor=S["stop_actor"] or "unknown", scenario=str(e))
        _bump(stage="halted", phase="Emergency stop, run halted, partial ledger sealed")
        STORE.update_meta(run_id, stage="halted", stopped_by=S["stop_actor"])
        STORE.pack(run_id)
        _alert("alert", f"Emergency stop by {S['stop_actor']} during {e}")
    except Exception as e:  # noqa: BLE001
        _bump(stage="error", err=repr(e)[:300], phase="Run failed")
        _alert("alert", f"Run failed {e!r}"[:200])
        STORE.update_meta(run_id, stage="error")
    finally:
        _mut(busy=False)


# ---------------------------------------------------------------- app ----
app = Dash(__name__, title="HSL TERMINAL", suppress_callback_exceptions=True,
           assets_ignore=r"echarts\.min\.js",
           assets_path_ignore=["psp", "wasm"])
server = app.server
# request bodies: an upload arrives base64 encoded inside a callback POST
server.config["MAX_CONTENT_LENGTH"] = int(CFG.upload_max_mb * 1024 * 1024 * 4 / 3) + 512 * 1024

_ASK_BUCKET = defaultdict(deque)


@server.before_request
def _guard():
    if CFG.auth_mode == "header" and freq.method == "POST" and \
            freq.path in ("/_dash-update-component", "/ask"):
        if not (freq.headers.get(CFG.user_header) or "").strip():
            abort(401)


@server.after_request
def _headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob:; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
        "connect-src 'self'; worker-src 'self' blob:; frame-src 'self'; frame-ancestors 'self'; "
        "object-src 'none'; base-uri 'self'")
    if freq.path.startswith(("/run/", "/runs.json", "/ask", "/healthz", "/version")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@server.route("/healthz")
def _healthz():
    return jsonify({"ok": True, "version": __version__, "stage": S["stage"],
                    "run_id": S["run_id"], "busy": S["busy"]})


@server.route("/version")
def _version():
    return jsonify({"version": __version__, "build": BUILD, "config": CFG.public(),
                    "provenance": provenance()})


@server.route("/runs.json")
def _runs():
    return jsonify(STORE.index())


@server.route("/run/<run_id>/<name>")
def _run_file(run_id, name):
    if not RUN_ID_RE.match(run_id) or name not in SERVABLE or not STORE.exists(run_id):
        abort(404)
    p = STORE.path(run_id, name)
    if name == "evidence_pack.zip":
        # rebuild only when absent or older than the artefacts it packs
        newest = max((os.path.getmtime(STORE.path(run_id, f)) for f in ("artefacts.json", "briefing.md",
                                                                          "critic.json", "approvals.json")
                      if os.path.isfile(STORE.path(run_id, f))), default=0)
        if not os.path.isfile(p) or os.path.getmtime(p) < newest:
            STORE.pack(run_id)
    if not os.path.isfile(p):
        return server.response_class("null", mimetype="application/json")
    return send_from_directory(STORE.path(run_id), name)


def _snapshot():
    with LOCK:
        lr = S["ledger_report"]
        if S["log"] is not None and (lr is None or S["stage"] in ("running", "planning")):
            lr = {"entries": S["log"].seq, "head": S["log"].head, "signed": S["log"].seq,
                  "ok": None}
        return {"stage": S["stage"], "question": S["question"], "run_id": S["run_id"],
                "preparer": S["preparer"], "approvals": dict(S["approvals"]),
                "specs": [sp.describe() for sp in (S["specs"] or [])],
                "summary": S["summary"], "holdout": S["holdout"], "gap": S["gap"],
                "gap_moments": S["gap_m"], "gap_bootstrap": S["gb"],
                "gap_bootstrap_moments": S["gbm"], "rules": S["rules"],
                "aut": (S["artefacts"] or {}).get("autonomy") if S["artefacts"] else
                ({k: {kk: vv for kk, vv in v.items() if kk != "scores"} for k, v in S["aut"].items()}
                 if S["aut"] else None),
                "rl": S["rl"], "three": (S["artefacts"] or {}).get("three_worlds"),
                "critic": S["critic"], "ledger": lr, "briefing": S["briefing"],
                "artefacts": S["artefacts"] or ({"conformal": S["assurance"].get("conformal"),
                                                 "frontier": S["assurance"].get("frontier"),
                                                 "attribution": S["assurance"].get("attribution"),
                                                 "truth_audit": S["assurance"].get("truth"),
                                                 "concentration": S["assurance"].get("dose"),
                                                 "redteam": S["assurance"].get("redteam")}
                                                if S["assurance"] else None)}


@server.route("/ask", methods=["POST"])
def _ask():
    body = freq.get_json(force=True, silent=True) or {}
    q = str(body.get("q", ""))[:600].strip()
    if not q:
        return jsonify({"error": "empty question"}), 400
    # the rate limit key is the proxy identity in header mode and the client
    # address otherwise; a name typed into the request body is not a key
    who = (identity(None) if CFG.auth_mode == "header" else None) or freq.remote_addr or "anon"
    now = time.time()
    if len(_ASK_BUCKET) > 5000:                          # bound the table over long uptimes
        for k in [k for k, v in _ASK_BUCKET.items() if not v or now - v[-1] > 60]:
            _ASK_BUCKET.pop(k, None)
    bucket = _ASK_BUCKET[who]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= CFG.ask_rate:
        return jsonify({"error": "rate limit"}), 429
    bucket.append(now)
    snap = _snapshot()
    res = ask_answer(snap, q)
    brain = "deterministic, from the artefacts"
    log = S["log"]
    if CFG.llm_enabled and log is not None:
        text = ask_llm(q, res["sources"], res["text"], CLIENT, log)
        if text:
            res["text"] = text
            brain = f"{CLIENT.provider} {CLIENT.model}, grounded on vetted context"
    if log is not None:
        log("ask", actor=who, question=q[:200], intent=res["intent"],
            sources=[c["id"] for c in res["sources"]], brain=brain)
    return jsonify({"text": res["text"], "sources": res["sources"], "brain": brain,
                    "intent": res["intent"]})


# ------------------------------------------------------------ layout -----
def _panel(idx, code, title, body, header_extra=None):
    right = header_extra if header_extra is not None else html.Span(
        "", className="ph-live", id=f"ph-live-{code}")
    return html.Section([
        html.Header([
            html.Span(str(idx), className="ph-num"),
            html.Span(code, className="ph-code"),
            html.Span(title, className="ph-title"),
            right,
        ], className="p-head"),
        html.Div(body, className="p-body", id=f"body-{code}"),
    ], className="panel", id=f"panel-{code}", **{"data-code": code})


def _mkt_body():
    return [
        html.Div([
            html.Button("Tape", id="mkt-tape-btn", className="mode on"),
            html.Button("3 worlds", id="mkt-3w-btn", className="mode", disabled=True,
                        title="Same shock: quiet, herd, throttle (after the run)"),
            html.Select([html.Option("Live", value="__live__")], id="mkt-sel", className="sel"),
            html.Span(id="mkt-read", className="mkt-read"),
        ], className="mkt-modes"),
        html.Div(id="mkt-chart"),
        html.Div(id="mkt-three", style={"display": "none"}),
    ]


def _howto(intro, steps, note=None):
    """Instructional page header: what the page does and how to use it, in order."""
    return html.Div([html.Div(intro, className="howto-intro"),
                     html.Ol([html.Li(s) for s in steps], className="howto-steps")]
                    + ([html.Div(note, className="howto-note")] if note else []), className="howto")


def _agt_static():
    return [
        _howto("Define an agent of your own, test it, then use it in a family.",
               ["Describe the strategy in the editor: each term is a signal and a coefficient (momentum, "
                "mispricing against fundamental, the crowd's last flow, a vendor's shared signal, own inventory, "
                "volatility, time since the shock). Add a gate if the agent should sit out below a threshold, "
                "outside a window or above a volatility level; add a lag, a cap, noise or a burst as needed.",
                "Click Probe. One herd market runs with the agent at 20% and the table shows its signature: how "
                "it moves with momentum, whether its members act together, whether it pushes the price away from "
                "fundamental, and what it does to the dislocation. Nothing is stored yet.",
                "Set destabilising to true, false or auto (auto labels the class from the overshoot test), then "
                "click Validate and store.",
                "Reference the template by name in a family under custom_agents with a share, in FAM. Its hash "
                "is bound into the battery at Gate 1, the critic checks it, and it appears by name in the network "
                "panel and the attribution."],
               "There is no code in a template; every value is bounded and clamps are reported."),
        html.Div([
            html.Div([html.Label("Agent template (JSON)", htmlFor="agt-json"),
                      dcc.Textarea(id="agt-json", value=json.dumps(agent_template(), indent=1), rows=14,
                                   spellCheck=False, maxLength=6000)], style={"flex": "2"}),
            html.Div([html.Label("Signals"),
                      html.Div(", ".join(AGENT_SIGNALS), className="gap-note mono"),
                      html.Label("Bounds"),
                      html.Div([html.Div(f"{k}: {v[0]} to {v[1]}", className="mono") for k, v in AGENT_BOUNDS.items()],
                               className="gap-note", style={"columns": "2"}),
                      html.Div(f"destabilising: true, false or auto (large, acting together, pushing the price away "
                               f"from fundamental). At most {MAX_AGENTS} stored templates.", className="gap-note")],
                     style={"flex": "1", "paddingLeft": "12px"})], style={"display": "flex", "gap": "8px"}),
        html.Div([html.Button("Probe", id="agt-probe", className="act"),
                  html.Button("Validate and store", id="agt-add", className="act gate"),
                  html.Button("Reset to template", id="agt-template", className="act")], className="btn-row"),
        html.Div(id="agt-result"),
        html.Div([html.Label("Stored templates: choose one to remove it", htmlFor="agt-pick"),
                  dcc.RadioItems(id="agt-pick", options=[], inline=True, className="seg", inputClassName="seg-in",
                                 labelClassName="seg-lab"),
                  html.Div([html.Button("Remove", id="agt-remove", className="act refuse")], className="btn-row")]),
        html.Div(id="agt-list"),
    ]


def _agt_list():
    items = AGENTS.list()
    if not items:
        return html.Div("No stored agent templates. Families can use only the built in classes.", className="await")
    rows = [{"n": x["agent"]["name"], "t": ", ".join(f"{k} {v:+.2f}" for k, v in x["agent"]["terms"].items()),
             "g": ", ".join(k for k in ("threshold", "lag", "withdraw_if_vol_above", "active_from", "active_until")
                            if x["agent"].get(k)) + (" burst" if (x["agent"]["burst"] or {}).get("len") else "") or "none",
             "d": str(x["agent"]["destabilising"]), "a": x["author"], "when": x["added"][:16], "h": x["sha256"][:12]}
            for x in items]
    return [html.Div(f"{len(items)} stored template{'s' if len(items) != 1 else ''}; reference one in a family as "
                     f"custom_agents: [{{\"agent\": \"name\", \"share\": 0.1}}]", className="feed-cap"),
            _table(rows, ["n", "t", "g", "d", "a", "when", "h"],
                   heads=["template", "terms", "gates", "label", "author", "added", "sha256"])]


def _fam_static():
    b = FAMILY_BOUNDS
    return [
        _howto("Define a scenario family of your own and add it to the next battery.",
               ["Edit the document on the left. Only the name is required; everything else defaults to the "
                "demonstration herd. Describe the market in the note.",
                "Set the structure: vendor shares and correlations, the shock size and time, the population and "
                "the generator. Add a mechanism if the question needs one (faulty vendor model, liquidity "
                "withdrawal, misinformation, colluding ignition, an LLM persona, evader cohorts, or one of your "
                "own agent templates under custom_agents).",
                "Click Validate and store. Values outside the bounds on the right are clamped and each clamp is "
                "listed; reserved names and impossible timings are refused with the reason.",
                "Return to RUN and click Plan. Every enabled family joins the battery, enters the hash approved "
                "at Gate 1 and is written to the ledger with your name and the definition's own hash."],
               "Disable a family to keep it without planning it; remove it to delete it from the library."),
        html.Div([
            html.Div([html.Label("Family document (JSON)", htmlFor="fam-json"),
                      dcc.Textarea(id="fam-json", value=json.dumps(family_template(), indent=1), rows=16,
                                   spellCheck=False, maxLength=6000)], style={"flex": "2"}),
            html.Div([html.Label("Bounds"),
                      html.Div([html.Div(f"{k}: {v[0]} to {v[1]}", className="mono") for k, v in b.items()],
                               className="gap-note", style={"columns": "2"}),
                      html.Div(["Generators: shared signal, imitation, sqrt impact, voter. Personas: momentum "
                                "follower, trend vol capped, contrarian. Built in family names are reserved. "
                                f"At most {MAX_FAMILIES} stored families."], className="gap-note")],
                     style={"flex": "1", "paddingLeft": "12px"})], style={"display": "flex", "gap": "8px"}),
        html.Div([html.Button("Validate and store", id="fam-add", className="act gate"),
                  html.Button("Reset to template", id="fam-template", className="act")], className="btn-row"),
        html.Div(id="fam-result"),
        html.Div([html.Label("Stored families: choose one, then enable, disable or remove it", htmlFor="fam-pick"),
                  dcc.RadioItems(id="fam-pick", options=[], inline=True, className="seg", inputClassName="seg-in",
                                 labelClassName="seg-lab"),
                  html.Div([html.Button("Enable", id="fam-enable", className="act"),
                            html.Button("Disable", id="fam-disable", className="act"),
                            html.Button("Remove", id="fam-remove", className="act refuse")], className="btn-row")]),
        html.Div(id="fam-list"),
    ]


def _fam_list():
    items = FAMILIES.list()
    if not items:
        return html.Div("No stored families. The demonstration battery runs alone.", className="await")
    rows = [{"n": x["family"]["name"], "on": html.Span("in next plan" if x.get("enabled", True) else "disabled",
                                                          className="chip " + ("ok" if x.get("enabled", True) else "")),
             "s": str(x["family"]["seeds"]), "g": x["family"]["generator"],
             "v": ", ".join(f"{a:.2f}/{r:.2f}" for a, r in zip(x["family"]["vendor_shares"], x["family"]["vendor_rhos"])),
             "m": ", ".join(k for k in ("vendor_fault_time", "liquidity_withdrawal_time", "false_shock_len",
                                        "manipulator_share", "persona_share", "evader_cohorts", "holdout", "quiet")
                            if x["family"].get(k)) or "none",
             "a": x["author"], "t": x["added"][:16], "h": x["sha256"][:12]} for x in items]
    return [html.Div(f"{len(items)} stored, {sum(1 for x in items if x.get('enabled', True))} in the next plan",
                     className="feed-cap"),
            _table(rows, ["n", "on", "s", "g", "v", "m", "a", "t", "h"],
                   heads=["family", "status", "seeds", "generator", "share/rho", "mechanisms", "author", "added", "sha256"])]


def _dat_static():
    return [
        _howto("Bring observed data into the sandbox for the next battery.",
               ["Choose the classification first: public, synthetic, licensed or pseudonymised. It decides what "
                "may leave the run directory; licensed and pseudonymised rows never enter an evidence pack.",
                "Either drop a CSV or JSON file (a timestamp and price column; optionally participant and flow), "
                "or pick a connector, type the symbol or series and a date range, and click Fetch. Connectors are "
                "off unless the deployment enables them; replay reads a fixture from sample_data.",
                "Every dataset passes one quarantine before it is kept: size and type limits, a schema check, a "
                "formula check, a personal identifier scan that refuses rather than redacts, and a hash for the "
                "ledger. A refusal says why.",
                "Return to RUN and click Plan. Accepted data anchors the quiet family against the observed "
                "returns, adds a held out empirical family with the observed shock and volatility, and, where "
                "per participant flow is present, runs the sentinels on it with a query set size floor of five."],
               "The list below shows what waits for the next plan and whether each dataset may enter the pack."),
        html.Div([
            html.Div([html.Label("Classification", htmlFor="dat-class"),
                      dcc.RadioItems(id="dat-class", value="public", inline=True, className="seg",
                                     inputClassName="seg-in", labelClassName="seg-lab",
                                     options=[{"label": f"{k}: {v['note']}", "value": k}
                                              for k, v in CLASSIFICATIONS.items() if v["allowed"]])],
                     className="dat-col"),
            html.Div([html.Label("Upload CSV or JSON"),
                      dcc.Upload(id="dat-upload", multiple=False, max_size=CFG.upload_max_mb * 1024 * 1024,
                                 children=html.Div(["drop a file here or ", html.B("browse")]),
                                 className="dat-upload")], className="dat-col")], className="dat-row"),
        html.Div([
            html.Div([html.Label("Connector", htmlFor="dat-source"),
                      dcc.RadioItems(id="dat-source", value="replay", inline=True, className="seg",
                                     inputClassName="seg-in", labelClassName="seg-lab",
                                     options=[{"label": k, "value": k} for k in CONNECTORS])],
                     className="dat-col"),
            html.Div([html.Label("Symbol or series (replay: a fixture name in sample_data)", htmlFor="dat-symbol"),
                      dcc.Input(id="dat-symbol", type="text", placeholder="for example EXR/D.USD.EUR.SP00.A",
                                autoComplete="off", maxLength=160)], className="dat-col"),
            html.Div([html.Label("From", htmlFor="dat-start"),
                      dcc.Input(id="dat-start", type="text", placeholder="YYYY-MM-DD", maxLength=10)],
                     className="dat-col dat-narrow"),
            html.Div([html.Label("To", htmlFor="dat-end"),
                      dcc.Input(id="dat-end", type="text", placeholder="YYYY-MM-DD", maxLength=10)],
                     className="dat-col dat-narrow"),
            html.Div([html.Label(" "), html.Button("Fetch", id="dat-fetch", className="act",
                                                   title="connectors are off unless HSL_CONNECTORS=on; replay always works")],
                     className="dat-col dat-narrow")], className="dat-row"),
        html.Div(id="dat-result"),
        html.Div(f"Connectors {'on' if CFG.connectors else 'off (air gapped; replay only)'}"
                 + (f"; egress allowlist {', '.join(CFG.egress_allowlist)}" if CFG.egress_allowlist else ""),
                 className="gap-note"),
        html.Div(id="dat-list"),
    ]



def _run_static():
    header_mode = CFG.auth_mode == "header"
    ident = [html.Label("Acting identity"),
             html.Div(id="ident-chip", className="ident")] if header_mode else [
        html.Label("Prepared by", htmlFor="who"),
        dcc.Input(id="who", type="text", placeholder="analyst preparing the battery",
                  autoComplete="off", maxLength=80),
        html.Label("Approver at the gates", htmlFor="approver"),
        dcc.Input(id="approver", type="text", placeholder="named supervisor (must differ from preparer)"
                  if CFG.four_eyes else "named supervisor", autoComplete="off", maxLength=80),
        html.Label("Approver's function (SMF or certified role; required)", htmlFor="approver-role"),
        dcc.Input(id="approver-role", type="text", placeholder=("for example SMF24, or Developer2 in dev mode" if CFG.dev_mode else "for example SMF24 or certified function"),
                  autoComplete="off", maxLength=80),
        html.Label("Preparer's function (required)", htmlFor="who-role"),
        dcc.Input(id="who-role", type="text", placeholder=("for example certified function, or Developer1 in dev mode" if CFG.dev_mode else "for example certified function or team"),
                  autoComplete="off", maxLength=80)]
    hidden = [] if not header_mode else [
        dcc.Input(id="who", type="hidden", value=""), dcc.Input(id="approver", type="hidden", value=""),
        dcc.Input(id="approver-role", type="hidden", value=""), dcc.Input(id="who-role", type="hidden", value="")]
    return [
        html.Label("Policy question", htmlFor="q"),
        dcc.Textarea(id="q", value=DEFAULT_Q, rows=3, spellCheck=False, maxLength=600),
        *ident, *hidden,
        html.Label("Reason (required to refuse a gate; recorded in the ledger)", htmlFor="reason"),
        dcc.Textarea(id="reason", rows=2, spellCheck=False, maxLength=400,
                     placeholder="why the battery or the briefing is refused"),
        html.Div([
            html.Button("Plan", id="plan", className="act", title="Plan the battery"),
            html.Button("Stop", id="stop", className="act stopbtn", disabled=True,
                        title="Emergency stop: halts orchestration now"),
            html.Button("New run", id="newrun", className="act",
                        title="Clear the terminal for a fresh run; datasets, families and agents are kept"),
        ], className="btn-row"),
        html.Div([
            html.Button("Gate 1: approve battery", id="g1a", className="act gate", disabled=True),
            html.Button("Refuse", id="g1r", className="act refuse", disabled=True),
        ], className="btn-row"),
        html.Div([
            html.Button("Gate 2: release briefing", id="g2a", className="act gate", disabled=True),
            html.Button("Refuse", id="g2r", className="act refuse", disabled=True),
        ], className="btn-row"),
        html.Div(id="run-status"),
    ]


def _sen_body():
    return [html.Div(id="sen-summary"),
            html.Div("Alert feed", className="feed-cap"),
            html.Div(id="sen-alerts", className="feed")]


RAIL = [("plan", "Plan"), ("gate1", "Gate 1"), ("battery", "Battery"), ("rules", "Rules"),
        ("assurance", "Assurance"), ("critic", "Critic"), ("gate2", "Gate 2"), ("released", "Released")]
FKEYS = [("1", "MKT", "Market tape"), ("2", "NET", "Correlation network"), ("3", "GAP", "Decision gap"),
         ("4", "SEN", "Sentinel telemetry"), ("5", "INT", "Intervention monitor"), ("6", "CSF", "Case file"),
         ("7", "LDG", "Rationale ledger"), ("8", "RUN", "Run control"), ("9", "ASK", "Run oracle"),
         ("0", "AUT", "Autonomy gate"), ("K", "RSK", "Assurance"), ("D", "DAT", "Data desk"), ("F", "FAM", "Scenario library"), ("A", "AGT", "Agent workshop"),
         ("S", "SEC", "Security posture"), ("R", "REG", "Run registry")]


def _rail():
    """The workflow rail: one segment per step, lit as the run advances."""
    with LOCK:
        stage, step, critic = S["stage"], S["step"], S["critic"]
    order = [k for k, _ in RAIL]
    cur = order.index(step) if step in order else 0
    out = []
    for i, (key, label) in enumerate(RAIL):
        cls = "rail-step"
        if stage == "idle":
            pass
        elif stage == "released":
            cls += " ok" if key == "released" else " done"
        elif i < cur:
            cls += " done"
        elif i == cur:
            if stage in ("error", "halted"):
                cls += " fail"
            elif stage in ("rejected", "refused"):
                cls += " fail"
            elif stage == "evaluated" and key == "critic" and critic and not critic["ok"]:
                cls += " fail"
            else:
                cls += " active"
        out.append(html.Span(label, className=cls, **{"data-step": key}))
    return out


FRONT_INDEX = [
    ("MKT", "market tape: every simulated price step, live, one scenario at a time"),
    ("NET", "agent correlation network of the live run, before and after the shock"),
    ("GAP", "the decision gap with its bootstrap: fidelity against decision rankings"),
    ("SEN", "sentinel telemetry with intervals, held out results and the alert feed"),
    ("INT", "intervention monitor: containment, dislocation probability, burden by class"),
    ("CSF", "case file: pivot the per scenario evidence"),
    ("LDG", "rationale ledger: the signed hash chain, entry by entry, with replay"),
    ("RUN", "run control: identities, gates with refusal, emergency stop, briefing"),
    ("ASK", "run oracle: grounded answers computed from the artefacts"),
    ("AUT", "autonomy gate: backed execution, in sample and leave one out"),
    ("RSK", "assurance: conformal guarantee, cost frontier, attribution, truth audit, dose response, red team"),
    ("DAT", "data desk: upload observed data or fetch from a connector, through quarantine, into the battery"),
    ("FAM", "scenario library: families the authority defines, validated, stored with provenance, in the next plan"),
    ("AGT", "agent workshop: agent templates the authority defines in a safe declarative language, probed before use"),
    ("SEC", "security posture: the deployment checked against the controls, with the chapter each applies"),
    ("REG", "run registry: every past run, its status and its evidence pack"),
]

app.layout = html.Div([
    dcc.Interval(id="iv-fast", interval=500),
    dcc.Interval(id="iv-slow", interval=1000),
    dcc.Store(id="cursor", data={"seq": 0, "three": False}),
    dcc.Store(id="sink4"),
    dcc.Store(id="rev-store", data=-1),
    dcc.Store(id="stream"), dcc.Store(id="sink"), dcc.Store(id="sink2"), dcc.Store(id="sink3"),

    html.Div([
        html.Div([html.Span(className="brand-glyph"), html.Span("HSL", className="brand-code"),
                  html.Span("Herding Scenario Lab", className="brand-name")], className="brand"),
        html.Div([html.Span("›", className="cmd-prompt"),
                  dcc.Input(id="cmd", type="text", placeholder="function code", autoComplete="off",
                            debounce=False),
                  html.Span("GO", className="go-key", title="Enter"),
                  html.Span(id="cmd-msg")], className="cmdline"),
        html.Span(id="phase-line", children="Awaiting run control"),
        html.Span([html.Span(id="run-chip", className="run-chip"),
                   html.Span("IDLE", id="live-stage", className="st-idle"),
                   html.Span("--:--:--", id="clock")], className="top-right"),
    ], className="top-bar"),
    html.Div(_rail(), id="rail", className="rail"),

    html.Main([
        html.Div([
        _panel(1, "MKT", "Market tape", _mkt_body(),
               header_extra=html.Span(id="tick-read", className="ph-live")),
        html.Div(className="gutter gutter-v", id="gut-v-1", **{"data-kind": "v"}),
        _panel(2, "NET", "Correlation network", html.Iframe(
            id="net-frame", src="/assets/network.html", className="net-frame")),
        ], className="trow", id="trow-1"),
        html.Div(className="gutter gutter-h", id="gut-h-1", **{"data-kind": "h"}),
        html.Div([
        _panel(3, "GAP", "Decision gap", html.Div(id="gap-body")),
        html.Div(className="gutter gutter-v", id="gut-v-2", **{"data-kind": "v"}),
        _panel(4, "SEN", "Sentinel telemetry", _sen_body()),
        html.Div(className="gutter gutter-v", id="gut-v-3", **{"data-kind": "v"}),
        _panel(5, "INT", "Intervention monitor", html.Div(id="int-body")),
        html.Div(className="gutter gutter-v", id="gut-v-4", **{"data-kind": "v"}),
        _panel(6, "CSF", "Case file", html.Div(id="csf-body"),
               header_extra=html.A("open pivot", id="csf-frame", href="/assets/casefile.html?v=0",
                                   target="_blank", className="ph-live ph-link",
                                   title="Interactive Perspective pivot in a new tab")),
        ], className="trow", id="trow-2"),
        html.Div(className="gutter gutter-h", id="gut-h-2", **{"data-kind": "h"}),
        html.Div([
        _panel(7, "LDG", "Rationale ledger",
               [html.Div(id="ldg-verify", className="feed-cap"),
                html.Div(id="ldg-feed", className="feed")]),
        html.Div(className="gutter gutter-v", id="gut-v-5", **{"data-kind": "v"}),
        _panel(8, "RUN", "Run control, gates and briefing", _run_static()),
        ], className="trow", id="trow-3"),
        _panel(0, "AUT", "Autonomy gate, backed execution", html.Div(id="aut-body")),
        _panel("K", "RSK", "Assurance: guarantee, frontier, attribution, audits, red team",
               html.Div(id="rsk-body")),
        _panel("D", "DAT", "Data desk: upload and connectors, through quarantine", _dat_static()),
        _panel("F", "FAM", "Scenario library: families defined by the authority", _fam_static()),
        _panel("A", "AGT", "Agent workshop: agent templates defined by the authority", _agt_static()),
        _panel("S", "SEC", "Security posture", html.Div(id="sec-body")),
        _panel("R", "REG", "Run registry", html.Div(id="reg-body")),
    ], className="term-grid", id="grid"),

    html.Footer([
        html.Div([html.Button([html.I(k), c], className="fkey", title=t, **{"data-code": c})
                  for k, c, t in FKEYS], className="fkeys"),
        html.Div(html.Div(id="ticker-text", children=(
            "HSL terminal ready. Name a preparer and an approver and plan the battery. "
            "Nothing simulates before Gate 1 and nothing is released before Gate 2. "
            "Every step is chained into a signed ledger.")), className="tape-wrap")], className="ticker"),

    html.Div([
        html.Div([
            html.Span("9", className="ph-num"), html.Span("ASK", className="ph-code"),
            html.Span("Run oracle", className="ph-title"),
            html.Span("answers are computed from this run's artefacts on the server; "
                      "a model, when configured, only phrases them", className="ch-meta"),
            html.Span(id="ch-brain", className="ch-meta ch-brain"),
            html.Button("Grid (Esc)", id="ch-back")], id="ch-head"),
        html.Div([
            html.Div([
                html.Div(id="ch-log"),
                html.Div([
                    dcc.Input(id="ch-in", type="text", autoComplete="off", maxLength=600,
                              placeholder="ask about a sentinel, the decision gap, a scenario, "
                                          "a rule, the autonomy gate, the ledger, or what the "
                                          "authority should certify"),
                    html.Button("Send ⏎", id="ch-send")], id="ch-inrow")],
                id="ch-left"),
            html.Div([html.H4("Sources used"), html.Div(id="ch-src")], id="ch-right")],
            id="ch-body")], id="chatpage"),

    html.Div(html.Div([
        html.Pre(["HSL", html.Span("▌", className="blink"),
                  html.Span("Herding Scenario Lab", className="fp-name")]),
        html.P("A public authority stress tests surveillance sentinels and intervention rules on "
               "synthetic AI agent markets, and certifies on decision accuracy rather than "
               "aggregate fidelity.", className="sub"),
        html.P("Team No Human Intelligence for the C:\\>DIR Global 'Agentic Regulator' Hackathon. "
               "For market monitoring and enforcement teams.", className="sub2"),
        html.Div([html.Div([
            html.Span(c, className="tag"), html.Span(t, className="desc"),
            html.Span({"ASK": "9", "AUT": "0", "RSK": "RSK", "REG": "REG", "DAT": "DAT", "SEC": "SEC", "FAM": "FAM", "AGT": "AGT"}.get(c, str(i + 1)), className="st")],
            className="slot", **{"data-code": c}) for i, (c, t) in enumerate(FRONT_INDEX)],
            id="front-index"),
        html.Div([html.Button("Enter ⏎", id="fenter"),
                  html.Button("Start a run", id="frun")], className="row"),
        html.P(["Type a code and press ", html.Code("GO"), " to open a page, or a digit ",
                html.Code("0 to 9"), ". ", html.Code("Esc"), " restores the grid and ",
                html.Code("FRONT"), " reopens this page."], className="duck"),
        html.P(f"Build {BUILD}   auth {CFG.auth_mode}   four eyes "
               f"{'on' if CFG.four_eyes else 'off'}   model "
               f"{'on' if CFG.llm_enabled else 'off'}   ledger key "
               f"{'configured' if not CFG.ephemeral_secret else 'ephemeral (set HSL_SECRET)'}",
               className="duck build")],
        className="inner"), id="front"),
], id="root")


# ------------------------------------------------------------ callbacks --
@app.callback(Output("stream", "data"), Output("cursor", "data"),
              Input("iv-fast", "n_intervals"), State("cursor", "data"),
              prevent_initial_call=True)
def _poll(_, cur):
    cur = cur or {"seq": 0, "three": False}
    since = cur.get("seq", 0)
    with LOCK:
        payload = {
            "seq": S["seq"], "stage": S["stage"], "phase": S["phase"], "run_id": S["run_id"],
            "scen": S["scen_current"],
            "ticks": [[sc, st, v] for q, sc, st, v in S["ticks"] if q > since],
            "marks": [m for q, m in S["marks"] if q > since],
            "alerts": [a for q, a in S["alerts"] if q > since],
            "ledger": [r for q, r in S["ledger_rows"] if q > since],
            "tapes_done": S["tapes_done"],
        }
        if S["three"] is not None and not cur.get("three"):
            payload["three"] = {k: S["three"][k] for k in ("shock", "quiet", "herd", "treated")}
            payload["three_dd"] = S["three"].get("post_shock_dd")
            cur = dict(cur, three=True)
        if S["run_id"] is None and cur.get("three"):
            cur = dict(cur, three=False)
    return payload, dict(cur, seq=payload["seq"])


app.clientside_callback(
    ClientsideFunction(namespace="hsl", function_name="onStream"),
    Output("sink", "data"), Input("stream", "data"), prevent_initial_call=True)


def _fmt(x, nd=2):
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def _pct(x):
    return "n/a" if x is None else f"{round(x * 100):d}%"


def _ci(ci, nd=2):
    if not ci or ci[0] is None:
        return ""
    return f"[{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"


def _lab(n):
    return SENTINEL_LABELS.get(n, str(n).replace("_", " "))


_NUMERIC = re.compile(r"^[-+]?(\d|n/a|\[|withdrawn)")


def _table(rows, cols, cls="data", heads=None):
    """Right aligns any column whose cells are numeric (numbers, intervals,
    n/a) so that decimals line up; the first column stays left aligned."""
    heads = heads or cols
    numeric = []
    for k, c in enumerate(cols):
        vals = [str(r.get(c, "")) for r in rows]
        numeric.append(k > 0 and vals and all(_NUMERIC.match(v.strip()) for v in vals if v.strip()))

    def cell(v):
        return _nice(v) if isinstance(v, str) else v

    def cls_for(k, v):
        if numeric[k]:
            return "num"
        return "wrap" if isinstance(v, str) and len(v) > 48 else ""
    return html.Table([
        html.Thead(html.Tr([html.Th(_nice(h) if isinstance(h, str) else h, className="num" if numeric[k] else "")
                            for k, h in enumerate(heads)])),
        html.Tbody([html.Tr([html.Td(cell(r.get(c, "")), className=cls_for(k, r.get(c, "")))
                             for k, c in enumerate(cols)]) for r in rows])], className=cls)


def _bar(label, val, vmax, color, text=None, ci=None):
    pct = 0 if not vmax else max(0.0, min(1.0, (val or 0) / vmax)) * 100
    kids = [html.Div(style={"width": f"{pct:.1f}%", "background": color}, className="bar-fill")]
    if ci and ci[0] is not None:
        lo = max(0.0, min(1.0, ci[0] / vmax)) * 100
        hi = max(0.0, min(1.0, ci[1] / vmax)) * 100
        kids.append(html.Div(style={"left": f"{lo:.1f}%", "width": f"{max(0.0, hi - lo):.1f}%"},
                             className="bar-ci"))
    return html.Div([
        html.Span(label, className="bar-k"),
        html.Div(kids, className="bar-track"),
        html.Span(text if text is not None else _fmt(val), className="bar-v"),
    ], className="bar-row")


def _kv(k, v, cls="v"):
    return html.Div([html.Span(k, className="k"), html.Span(v, className=cls)], className="kv")


_SECTION_LABELS = {"what the reports ask for": "Reports", "certification with a false alert guarantee": "Guarantee",
                   "supervisory cost frontier": "Cost frontier", "counterfactual attribution": "Attribution",
                   "truth dependence audit": "Truth audit", "concentration dose response": "Dose response",
                   "time to dislocation": "Survival", "tail risk": "Tail risk",
                   "sentinel against evader": "Game", "learned policy and off policy evaluation": "Learned policy",
                   "regulatory options appraisal": "Appraisal", "red team": "Red team", "alert feed": "Alert feed",
                   "backtests": "Backtests"}


def _short_label(text):
    t = str(text)
    key = t.split(":")[0].split("(")[0].strip().lower()
    for k, v in _SECTION_LABELS.items():
        if key.startswith(k):
            return v
    for sep in (":", "(", ","):
        t = t.split(sep)[0]
    t = t.strip()
    return (t[:26] + "\u2026") if len(t) > 27 else t


def _sectioned(children, merge_from=None, merged_label="Details"):
    """Split a flat panel body into selectable sections at each gap-name
    header. With merge_from=k, sections from the kth onward are merged into
    one, for bodies with many short blocks."""
    secs, cur = [], None
    for ch in children if isinstance(children, list) else [children]:
        cls = getattr(ch, "className", "") or ""
        if cls.startswith("gap-name") or cls.startswith("feed-cap"):
            cur = [ch.children if isinstance(ch.children, str) else "Section", [ch]]
            secs.append(cur)
        else:
            if cur is None:
                cur = ["Overview", []]
                secs.append(cur)
            cur[1].append(ch)
    if merge_from is not None and len(secs) > merge_from + 1:
        head, tail = secs[:merge_from], secs[merge_from:]
        merged = [merged_label, [x for _, kids in tail for x in kids]]
        secs = head + [merged]
    if len(secs) < 2:
        return children
    btns = [html.Button(_short_label(lab), className="sec-btn" + (" on" if i == 0 else ""), **{"data-sec": str(i)})
            for i, (lab, _) in enumerate(secs)]
    return [html.Div(btns, className="sec-row")] + \
        [html.Div(kids, className="sec" + (" on" if i == 0 else ""), **{"data-sec": str(i)})
         for i, (_, kids) in enumerate(secs)]


def _gap_body():
    if not S["summary"]:
        return html.Div("Awaiting battery: fidelity and decision rankings render here as the "
                        "scenarios complete.", className="await")
    s, out = S["summary"], []
    for name, v in s.items():
        out.append(html.Div(_lab(name), className="gap-name"))
        out.append(_bar("Fidelity", v["aggregate_fidelity"], 1.0, MUTED, ci=v["ci"]["aggregate_fidelity"]))
        out.append(_bar("Decision F1", v["decision_f1"], 1.0, AMBER, ci=v["ci"]["decision_f1"]))
    g, gm, gb, gbm = S["gap"], S["gap_m"], S["gb"], S["gbm"]
    if g:
        head = [html.Div([
            _kv("Decision gap", f"{g['decision_gap']:.2f}", "v big"),
            _kv("Kendall tau", f"{g['kendall_tau']:+.2f}"),
            _kv("P(inversion)", f"{gb['p_inversion']:.2f}"),
            _kv("Gap, multi moment", f"{gm['decision_gap']:.2f}"),
            _kv("P(inversion), multi moment", f"{gbm['p_inversion']:.2f}"),
        ], className="kv-row")]
        cert = best_certifiable(s)
        tail = [
            html.Div(["Fidelity  ", html.B(" › ".join(_lab(x) for x in g["fidelity_ranking"]))], className="rank-line"),
            html.Div(["Decision  ", html.B(" › ".join(_lab(x) for x in g["decision_ranking"]))], className="rank-line"),
            html.Div(f"Bars show the point estimate; the thin band is the 95% bootstrap interval over "
                     f"{gb['n_scenarios']} scenarios. With {g['n_tools']} tools tau takes few values; quote "
                     f"P(inversion).", className="gap-note"),
            html.Div(("Best tool within the false alert budget: " + _lab(cert)) if cert else
                     "No tool is within the false alert budget.", className="gap-note strong"),
        ]
        out = head + out + tail
    else:
        out.append(html.Div("Partial: rankings settle when the battery completes.", className="gap-note"))
    return out


def _sen_summary():
    if not S["summary"]:
        return html.Div("Awaiting battery", className="await")
    cols = ["sentinel", "fid", "fidm", "f1", "ci", "gr", "prec", "rec", "lead", "fa", "hold"]
    heads = ["sentinel", "fid", "fid (mom)", "F1", "95% CI", "grade", "prec", "rec", "lead", "false alert", "held out F1"]
    hold = S["holdout"] or {}
    rows = []
    for k, v in S["summary"].items():
        rows.append({"sentinel": _lab(k), "fid": _fmt(v["aggregate_fidelity"]),
                     "fidm": _fmt(v.get("fidelity_moments")), "f1": _fmt(v["decision_f1"]),
                     "ci": _ci(v["ci"]["decision_f1"]), "gr": v["grade"]["decision_f1"],
                     "prec": _fmt(v["precision"]), "rec": _fmt(v["recall"]),
                     "lead": _fmt(v["mean_lead_time"], 0),
                     "fa": _fmt(v["false_alert_rate"]) + ("" if v.get("within_budget", True) else " ✗"),
                     "hold": _fmt(hold.get(k, {}).get("decision_f1")) if hold else "…"})
    done = len({r["scenario"] for r in S["sent_rows"]})
    cap = html.Div(f"Scenarios scored {done:02d}/{S['n_specs']:02d}. A cross marks a false alert "
                   f"rate above the {_fmt(next(iter(S['summary'].values())).get('false_alert_budget', 0.25))} budget",
                   className="feed-cap")
    compact_cols = ["sentinel", "f1", "gr", "fa", "hold"]
    compact_heads = ["sentinel", "F1", "grade", "false alert", "held out F1"]
    return [cap, html.Div(_table(rows, compact_cols, heads=compact_heads), className="sen-compact"),
            html.Div(_table(rows, cols, heads=heads), className="sen-full")]


def _aut_body():
    if not S["aut"]:
        return html.Div("Awaiting battery: the autonomy gate is scored from the evaluated "
                        "scenarios.", className="await")
    out = [html.Div(
        "Score triggered autonomy: each sentinel's per scenario herding score (peak stress inside "
        "the pre emption window, normalised) is split by two gates set to the zero claim tails of "
        "this battery. Below the low gate the system stands behind no intervention; above the high "
        "gate it may trigger the targeted throttle, unless that action is withdrawn because the "
        "tool's localisation cannot beat the flag everyone baseline by 25%. The band between, and "
        "every withdrawn tail, escalates to the named supervisor. In sample breadth holds by "
        "construction; the leave one out figures refit the gates without each scenario and are the "
        "ones to quote.", className="aut-intro")]
    for name, v in S["aut"].items():
        out.append(html.Div(_lab(name), className="gap-name"))
        dots = [html.Span(className="aut-dot" + (" q" if p["quiet"] else ""),
                          title=f"{p['scenario']}, s={p['s']:.2f}",
                          style={"left": f"{p['s'] * 100:.1f}%"}) for p in v["scores"]]
        band = html.Span(className="aut-band", style={
            "left": f"{v['t_lo'] * 100:.1f}%",
            "width": f"{max(0.0, (v['t_hi'] - v['t_lo'])) * 100:.1f}%"})
        out.append(html.Div([band] + dots, className="aut-axis"))
        out.append(html.Div([
            html.Span("auto clear", className="aut-lab"),
            html.Span("escalate", className="aut-lab mid"),
            html.Span("auto throttle" + ("" if v["throttle_ok"] else ", withdrawn"),
                      className="aut-lab" + ("" if v["throttle_ok"] else " off"))],
            className="aut-labels"))
        loo = v["loo"]
        bits = [f"in sample backs {_pct(v['breadth'])}", f"auto clear {_pct(v['clear'])}",
                (f"auto throttle {_pct(v['throttle'])}" if v["throttle_ok"] else
                 f"throttle withdrawn (lift {v['lift']:.2f} below {v['lift_bar']:.2f})"),
                f"leave one out backs {_pct(loo['backed'])} with {loo['claims']} claims "
                f"({_pct(loo['claim_rate'])})"]
        out.append(html.Div(", ".join(bits), className="chip " + ("ok" if loo["claims"] == 0 else "warn")))
    out.append(html.Div("Construct: score triggered guaranteed autonomy, after Iravani, Orfanoudaki, "
                        "Markakis and Szpruch, 'The Limits of Autonomy in Agentic AI' (Oxford). Quiet "
                        "scenarios are the round markers.", className="gap-note"))
    return out


def _int_body():
    if not S["rules"]:
        return html.Div("Awaiting rules: circuit breaker, targeted throttle and kill switch are "
                        "scored after the battery.", className="await")
    out = []
    for name, v in S["rules"].items():
        out.append(html.Div(v.get("label", name), className="gap-name"))
        out.append(_bar("DD untreated", v["mean_post_shock_dd_untreated"], 0.30, MUTED,
                        _fmt(v["mean_post_shock_dd_untreated"], 3)))
        out.append(_bar("DD treated", v["mean_post_shock_dd_treated"], 0.30, INFO,
                        _fmt(v["mean_post_shock_dd_treated"], 3)))
        out.append(_bar("Containment", max(0.0, v["containment"]), 1.0, AMBER,
                        f"{v['containment']:.2f} {_ci(v['containment_ci'])} {v['grade']}",
                        ci=[max(0.0, v["containment_ci"][0]), max(0.0, v["containment_ci"][1])]))
        b = v.get("burden_by_class", {})
        chips = [
            html.Span(f"dislocation P {_fmt(v['crash_prob_untreated'])} → {_fmt(v['crash_prob_treated'])}",
                      className="chip"),
            html.Span(f"false halt {_fmt(v['false_halt_rate'])}",
                      className="chip " + ("ok" if not v["false_halt_rate"] else "bad")),
            html.Span(f"engaged pre shock {_pct(v.get('pre_shock_engagement'))}", className="chip"),
            html.Span(f"burden on destabilising {_fmt(b.get('destabilising'))}", className="chip"),
            html.Span(f"burden on others {_fmt(b.get('non_destabilising'))}", className="chip"),
            html.Span(f"burden on fundamentalists {_fmt(b.get('fundamentalist'))}",
                      className="chip " + ("bad" if (b.get("fundamentalist") or 0) >= 0.5 * (b.get("destabilising") or 1e-9) and v.get("targeted") else "")),
        ]
        out.append(html.Div(chips, className="chip-row"))
    three = S["three"]
    if three:
        d = three.get("post_shock_dd", {})
        out.append(html.Div([
            _kv("Quiet, post shock DD", _fmt(d.get("quiet"), 3)),
            _kv("Herd", _fmt(d.get("herd"), 3), "v bad"),
            _kv("Throttle", _fmt(d.get("treated"), 3)),
            _kv("Herd pre shock vol ×", _fmt(three.get("pre_shock_vol", {}).get("herd"), 1)),
        ], className="kv-row"))
    if S["rl"]:
        e = S["rl"]
        out.append(html.Div(
            f"RL emergence: policy convergence {_fmt(e.get('policy_convergence'))}, momentum slope "
            f"{_fmt(e.get('momentum_slope'))}. Sentinel F1 on the emergent herd: "
            + ", ".join(f"{_lab(k)} {_fmt(v)}" for k, v in (e.get("sentinel_f1_on_rl_herd") or {}).items()) + ".",
            className="gap-note"))
    return out

def _rsk_body():
    a = S["artefacts"] or {}
    asr = S["assurance"] or {}
    cf = a.get("conformal") or asr.get("conformal")
    fr = a.get("frontier") or asr.get("frontier")
    at = a.get("attribution") or asr.get("attribution")
    ta = a.get("truth_audit") or asr.get("truth")
    dose = a.get("concentration") or asr.get("dose")
    rt = a.get("redteam") or asr.get("redteam") or {}
    if not any([cf, fr, at, ta, dose, rt]):
        return html.Div("Awaiting battery: the assurance stages run after the rules are scored. "
                        "Conformal certification, the supervisory cost frontier, Shapley attribution, "
                        "the truth dependence audit, the concentration dose response and the red team "
                        "render here as each completes.", className="await")
    out = []
    rp = a.get("reports")
    if rp:
        out.append(html.Div(f"What the reports ask for: {rp['n_answered']} answered, {rp['n_partial']} partial, "
                            f"{rp['n_open']} open of {len(rp['needs'])} needs", className="gap-name"))
        rows = [{"i": n["id"], "n": n["need"], "s": html.Span(n["status"], className="chip " + {"answered": "ok", "partial": "warn", "open": "bad"}[n["status"]]),
                 "e": n["evidence"], "src": n["source"]} for n in rp["needs"]]
        out.append(_table(rows, ["i", "n", "s", "e", "src"], heads=["", "need flagged", "status", "evidence in this run", "source"]))
        tc = rp["indicators"]["third_party_concentration"]; ch = rp["indicators"]["correlation_and_herding"]
        out.append(html.Div(f"Indicators (IOSCO 2026 Table 7, FSB 2025): vendor HHI up to {_fmt(tc['vendor_hhi_max'], 3)}, "
                            f"top vendor share {_fmt(tc['top_vendor_share_max'])}, substitutability proxy "
                            f"{_fmt(tc['substitutability_proxy'])}; herd against quiet drawdown {_fmt(ch['herd_post_shock_dd'], 3)} "
                            f"against {_fmt(ch['quiet_post_shock_dd'], 3)}; persona output jump "
                            f"{_fmt(rp['indicators']['input_output_sensitivity']['persona_max_action_jump'])}. "
                            f"Data gaps needing firm reporting: {len(rp['indicators']['data_gaps'])}.", className="gap-note"))
    if cf:
        out.append(html.Div("Certification with a false alert guarantee", className="gap-name"))
        rows = [{"s": _lab(n), "n": v["n_calibration"],
                 "b": _fmt(v["guaranteed_false_alert_bound"]) if v["guarantee_achievable"] else "n/a",
                 "t": _fmt(v["threshold_score"]), "p": _fmt(v["power_calibration_herd"]),
                 "h": _fmt(v["false_alert_rate_holdout"]), "ph": _fmt(v["power_holdout_herd"])}
                for n, v in cf.items()]
        out.append(_table(rows, ["s", "n", "b", "t", "p", "h", "ph"],
                          heads=["sentinel", "n cal", "guaranteed FA", "threshold", "power (cal)",
                                 "held out FA", "power (held out)"]))
        cc = a.get("conformally_certifiable") or []
        if cc:
            out.append(html.Div("Conformally certifiable, in decision order: " + " › ".join(_lab(x) for x in cc),
                                className="gap-note strong"))
    if fr and fr.get("sentinels"):
        fs, frr = fr["sentinels"], fr["rules"]
        out.append(html.Div("Supervisory cost frontier", className="gap-name"))
        out.append(html.Div([
            html.Div(["Sentinels  ", html.B("; ".join(f"{_lab(g['tool'])} c {g['c_from']:.2f} to {g['c_to']:.2f}"
                                                        for g in fs["segments"]))], className="rank-line"),
            html.Div(["Rules  ", html.B("; ".join(f"{(a.get('rules') or S['rules'] or {}).get(g['tool'], {}).get('label', g['tool'])} "
                                                    f"c {g['c_from']:.2f} to {g['c_to']:.2f}" for g in frr["segments"]))],
                     className="rank-line"),
            html.Div(f"At the declared weight c = {fs['c_declared']:.2f}: sentinel {_lab(fs['best_at_declared'])}, "
                     f"rule {(a.get('rules') or S['rules'] or {}).get(frr['best_at_declared'], {}).get('label', frr['best_at_declared'])}. "
                     f"Loss = c × false alert (halt) rate + (1 - c) × miss (dislocation) rate.",
                     className="gap-note")]))
    if at and at.get("scenarios"):
        out.append(html.Div("Counterfactual attribution (Shapley, post shock drawdown)", className="gap-name"))
        rows = [{"sc": e["scenario"], "o": " › ".join(f"{g} {e['shapley'][g]:.3f}" for g in e["impact_ordering"]),
                 "f": _fmt(e["drawdown_full"], 3), "z": _fmt(e["drawdown_all_silenced"], 3)}
                for e in at["scenarios"]]
        out.append(_table(rows, ["sc", "o", "f", "z"], heads=["scenario", "impact ordering", "full DD", "all silenced"]))
        rows = [{"s": _lab(n), "sh": _fmt(v["mean_share_on_top_group"]), "tau": _fmt(v["mean_tau_flags_vs_impact"])}
                for n, v in at["by_sentinel"].items()]
        out.append(_table(rows, ["s", "sh", "tau"], heads=["sentinel", "flags on top impact group", "tau flags vs impact"]))
    sv = a.get("survival")
    if sv and sv.get("kaplan_meier"):
        out.append(html.Div("Time to dislocation (Kaplan Meier, Cox)", className="gap-name"))
        rows = [{"arm": (a.get("rules") or {}).get(arm, {}).get("label", arm.replace("_", " ")),
                 "n": str(k["n"]), "ev": str(k["events"]),
                 "med": "not reached" if k["median"] is None else f"{k['median']:.0f}",
                 "s20": _fmt(k["survival_at_20"]), "s60": _fmt(k["survival_at_60"]),
                 "hr": (_fmt(sv["cox"]["hazard_ratio"].get(arm)) if sv.get("cox") and arm in sv["cox"]["hazard_ratio"] else "ref")}
                for arm, k in sv["kaplan_meier"].items()]
        out.append(_table(rows, ["arm", "n", "ev", "med", "s20", "s60", "hr"],
                          heads=["arm", "runs", "dislocations", "median steps", "contained at 20", "contained at 60", "hazard ratio"]))
        if sv.get("cox"):
            cx = sv["cox"]
            out.append(html.Div(f"Cox covariates (per standard deviation): dominant share HR {_fmt(cx['hazard_ratio'].get('dominant_share'))}, "
                                f"dominant correlation HR {_fmt(cx['hazard_ratio'].get('dominant_rho'))}; "
                                f"{cx['n']} runs, {cx['events']} events, {'converged' if cx['converged'] else 'not converged'}.",
                                className="gap-note"))
    if ta:
        out.append(html.Div("Truth dependence audit", className="gap-name"))
        rows = []
        for g, pg in ta["per_generator"].items():
            c = ta["comparison"].get(g)
            rows.append({"g": g.replace("_", " "), "r": " › ".join(_lab(x) for x in pg["ranking"]),
                         "tau": _fmt(c["tau_vs_shared_signal"]) if c else "ref",
                         "sh": str(c["max_rank_shift"]) if c else "0"})
        out.append(_table(rows, ["g", "r", "tau", "sh"], heads=["generator", "decision ranking", "tau", "max shift"]))
        r1 = ta.get("rank_one_under_every_generator")
        out.append(html.Div((f"{_lab(r1)} holds rank one under every generator." if r1 else
                             "No sentinel holds rank one under every generator: the certification is "
                             "conditional on the generator."), className="gap-note strong"))
    if dose:
        out.append(html.Div("Concentration dose response (Meng and Chen 2026 convexity test)", className="gap-name"))
        for lv in dose["levels"]:
            out.append(_bar(f"share {lv['share']:.2f}", lv["mean_post_shock_dd"], 0.30, BAD if lv["dislocation_prob"] >= 0.5 else INFO,
                            f"DD {lv['mean_post_shock_dd']:.3f}  x{lv['amplification']:.1f}  P(dislocation) {lv['dislocation_prob']:.2f}"))
        out.append(html.Div(f"Response {'convex' if dose['convex'] else 'not convex'} (curvature {dose['curvature']:.3f}); "
                            f"dislocation threshold share {dose.get('dislocation_threshold_share')}; correlation held at {dose['rho']:.2f}.",
                            className="gap-note"))
    bt = a.get("backtest")
    if bt:
        out.append(html.Div("Backtests: observed episodes and the certification procedure", className="gap-name"))
        wf = bt.get("walk_forward")
        if wf:
            rows = [{"f": str(f["fold"]), "c": _lab(f["certified"]), "ct": _fmt(f["f1_certified_test"]), "b": _lab(f["best_on_test"]),
                     "bt": _fmt(f["f1_best_test"]), "r": _fmt(f["regret"])} for f in wf["folds"]]
            out.append(_table(rows, ["f", "c", "ct", "b", "bt", "r"],
                              heads=["fold", "certified on earlier folds", "its F1 on the test fold", "best on the test fold",
                                     "best F1", "regret"]))
            out.append(html.Div(f"Walk forward: mean regret {wf['mean_regret']:.2f}, worst {wf['max_regret']:.2f}; the certified "
                                f"tool was still the best on {wf['p_still_best']:.0%} of test folds.", className="gap-note strong"))
        for dset in bt.get("datasets", []):
            if not dset["episodes"]:
                out.append(html.Div(f"{dset['name']}: no stress episode found.", className="gap-note"))
                continue
            out.append(html.Div(f"{dset['name']}: " + "; ".join(f"{_nice(e['name'])} drawdown {e['drawdown']:.3f} at step "
                                                              f"{e['event_step']} ({e['source']})" for e in dset["episodes"]),
                                className="gap-note"))
            bs = dset.get("sentinels")
            if bs:
                rows = [{"s": _lab(n), "d": v.get("skipped") or _fmt(v["detection_rate"]),
                         "l": "" if v.get("skipped") else _fmt(v["median_lead"], 0),
                         "q": "" if v.get("skipped") else _fmt(v["quiet_alerts_per_100_steps"]),
                         "r": "" if v.get("skipped") else _fmt(v["mean_recall_on_labelled"])}
                        for n, v in bs["sentinels"].items()]
                out.append(_table(rows, ["s", "d", "l", "q", "r"],
                                  heads=["sentinel", "episodes detected", "median lead", "alerts per 100 quiet steps",
                                         "recall on labelled"]))
            br = dset.get("rules")
            if br and br.get("rules"):
                rows = [{"r": (a.get("rules") or {}).get(n, {}).get("label", n), "m": _fmt(v["mean_containment"]),
                         "w": _fmt(v["worst_containment"])} for n, v in br["rules"].items()]
                out.append(_table(rows, ["r", "m", "w"], heads=["rule", "mean containment over episodes", "worst episode"]))
    gm = a.get("game")
    if gm:
        out.append(html.Div("Sentinel against evader: matrix game", className="gap-name"))
        out.append(html.Div(f"Maximin {_lab(gm['maximin_pure'])} guarantees F1 {gm['maximin_value']:.2f}; the adversary's "
                            f"best counter holds every sentinel to {gm['minimax_value']:.2f}; mixed strategy value "
                            f"{gm['mixed_value']:.2f} ({', '.join(f'{_lab(k)} {v:.2f}' for k, v in gm['mixture'].items())}); "
                            f"value of mixing {gm['value_of_mixing']:.2f} over {gm['n_trials']} dislocating evasions.",
                            className="gap-note"))
    lp = a.get("learned_policy")
    if lp:
        out.append(html.Div("Learned policy and off policy evaluation", className="gap-name"))
        rows = [{"p": (a.get("rules") or {}).get(n, {}).get("label", n.replace("_", " ")), "is": _fmt(v["pdis"], 3),
                 "dr": _fmt(v["dr"], 3), "mb": _fmt(v.get("model"), 3), "on": _fmt(v["on_policy"], 3)}
                for n, v in lp["ope"].items()]
        out.append(_table(rows, ["p", "is", "dr", "mb", "on"],
                          heads=["policy", "importance sampling", "doubly robust", "model based", "simulated"]))
        mae = lp.get("mean_abs_error") or {}
        out.append(html.Div(f"Model coverage {lp['model_coverage']:.2f}; the learned policy halts in "
                            f"{lp['action_share']['halt']:.2f} and throttles in {lp['action_share']['throttle']:.2f} of states. "
                            f"Mean absolute error against the simulated value: importance sampling {_fmt(mae.get('pdis'), 3)}, "
                            f"doubly robust {_fmt(mae.get('dr'), 3)}, model based {_fmt(mae.get('model'), 3)}; closest "
                            f"{lp.get('best_estimator', 'model')}.", className="gap-note"))
    rk = a.get("risk")
    if rk and rk.get("untreated"):
        u = rk["untreated"]
        out.append(html.Div("Tail risk: value at risk, expected shortfall, extreme value tail", className="gap-name"))
        out.append(html.Div(f"Untreated: mean {u['mean']:.3f}, VaR {u['var']:.3f}, ES {u['es']:.3f} at level {rk['alpha']:.2f}"
                            + (f"; GPD shape {u['gpd']['shape']:.2f} on {u['gpd']['n_excess']} excesses, tail probability "
                               f"{u['gpd']['tail_prob']:.3f} beyond {u['gpd']['probe']:.3f}." if u["gpd"].get("shape") is not None
                               else "; too few excesses for an extreme value fit."), className="gap-note"))
        rows = [{"r": (a.get("rules") or {}).get(n, {}).get("label", n), "es": _fmt(v["es_treated"], 3),
                 "red": _fmt(v["es_reduction"]), "ci": f"[{v['es_reduction_ci'][0]:.2f}, {v['es_reduction_ci'][1]:.2f}]",
                 "m": _fmt(v["mean_reduction"])} for n in rk["ranking_by_es_reduction"] for v in [rk["rules"][n]]]
        out.append(_table(rows, ["r", "es", "red", "ci", "m"], heads=["rule", "ES treated", "ES reduction", "95% CI", "mean reduction"]))
    ap = a.get("appraisal")
    if ap:
        out.append(html.Div("Regulatory options appraisal (responsive regulation)", className="gap-name"))
        rows = [{"t": f"{o['tier']} {o['tier_label']}", "r": o["label"], "i": o["instrument"], "c": _fmt(o["containment"]),
                 "f": _fmt(o["false_halt_rate"]), "b": _fmt(o["burden_ratio_others_to_destabilising"]),
                 "p": "all" if o["passes_all"] else ", ".join(k for k, v in o["passes"].items() if not v) + " failed",
                 "l": o["legal_basis"]} for o in ap["options"]]
        out.append(_table(rows, ["t", "r", "i", "c", "f", "b", "p", "l"],
                          heads=["tier", "rule", "instrument", "containment", "false halts", "burden ratio", "tests", "legal basis"]))
        rec = ap.get("recommended")
        out.append(html.Div((f"Recommended: tier {rec['tier']} {rec['tier_label']}, {rec['label']} ({rec['instrument']}). "
                             if rec else "No rule passes all tests: monitor and warn, recalibrate the targeted rules. ")
                            + f"{ap['n_eligible']} eligible; lowest tier that meets containment {ap['containment_target']:.2f}, "
                              f"false halts {ap['false_halt_budget']:.2f} and proportionality {ap['proportionality_limit']:.2f}.",
                            className="gap-note strong"))
    ev, inj = rt.get("evasion"), rt.get("injection")
    if ev or inj:
        out.append(html.Div("Red team", className="gap-name"))
        if ev:
            wc = ev.get("worst_case")
            if wc:
                p = wc["params"]
                out.append(html.Div(f"Worst case for {_lab(ev['certified'])}: F1 {wc['f1_certified']:.2f} against "
                                    f"{_fmt(ev.get('battery_f1_certified'))} on the battery (margin "
                                    f"{_fmt(ev.get('robustness_margin'))}); cohorts {int(p['evader_cohorts'])}, period "
                                    f"{int(p['evader_period'])}, rho {p['rho']:.2f}, share {p['share']:.2f}; "
                                    f"{ev['n_dislocating']} of {ev['budget']} trials dislocated", className="gap-note"))
                rows = [{"s": _lab(k), "f": _fmt(v)} for k, v in wc["f1_all"].items()]
                out.append(_table(rows, ["s", "f"], heads=["sentinel", "F1 on the worst case"]))
            else:
                out.append(html.Div(f"No dislocating evasion found in {ev['budget']} trials.", className="gap-note"))
        if inj:
            chips = [html.Span(c["name"], className="chip " + ("ok" if c["contained"] else "bad"),
                               title=c["detail"]) for c in inj["cases"]]
            out.append(html.Div(chips, className="chip-row"))
            out.append(html.Div(f"{inj['n_contained']} of {inj['n_cases']} injection cases contained across "
                                f"{', '.join(inj['surfaces'])}.", className="gap-note strong"))
    return out

def _csf_body():
    """Native case file: decision F1 by sentinel and family (rows by columns),
    held out F1 and the quiet false alert rate; maximised, the per scenario
    rows follow. Always renders; the Perspective pivot is one click away."""
    rows = S["sent_rows"]
    if not rows:
        return html.Div("Awaiting battery: the per scenario evidence pivots here as sentinels are "
                        "scored, decision F1 by sentinel and family, with the held out and quiet "
                        "columns beside it.", className="await")
    fams = sorted({r["family"] for r in rows if not r["quiet"] and not r["holdout"]})
    names = [S_.name for S_ in ALL_SENTINELS if any(r["sentinel"] == S_.name for r in rows)]
    piv = []
    for n in names:
        rec = {"sentinel": _lab(n)}
        for f in fams:
            v = [r["f1"] for r in rows if r["sentinel"] == n and r["family"] == f and r["f1"] is not None]
            rec[f] = _fmt(float(np.mean(v))) if v else ""
        h = [r["f1"] for r in rows if r["sentinel"] == n and r["holdout"] and r["f1"] is not None]
        q = [float(r["false_alert"]) for r in rows if r["sentinel"] == n and r["quiet"] and not r["holdout"]]
        rec["held out"] = _fmt(float(np.mean(h))) if h else ""
        rec["quiet FA"] = _fmt(float(np.mean(q))) if q else ""
        piv.append(rec)
    cols = ["sentinel"] + fams + ["held out", "quiet FA"]
    heads = ["sentinel"] + [f.replace("_", " ") for f in fams] + ["held out F1", "quiet false alert"]
    done = len({r["scenario"] for r in rows})
    out = [html.Div(f"Decision F1 by sentinel and family, {done:02d}/{S['n_specs']:02d} scenarios scored",
                    className="feed-cap"),
           _table(piv, cols, heads=heads)]
    recent = sorted(rows, key=lambda r: r["scenario"])[-400:]
    rcols = ["scenario", "sentinel", "f1", "precision", "recall", "lead_time", "fidelity", "peak_stress",
             "n_flagged", "false_alert"]
    rrows = [{"scenario": r["scenario"], "sentinel": _lab(r["sentinel"]), "f1": _fmt(r["f1"]),
              "precision": _fmt(r["precision"]), "recall": _fmt(r["recall"]),
              "lead_time": _fmt(r["lead_time"], 0), "fidelity": _fmt(r["fidelity"]),
              "peak_stress": _fmt(r["peak_stress"]), "n_flagged": str(r["n_flagged"]),
              "false_alert": "" if r["false_alert"] is None else ("yes" if r["false_alert"] else "no")}
             for r in recent]
    out.append(html.Div("Per scenario rows", className="feed-cap csf-rows-cap"))
    out.append(html.Div(_table(rrows, rcols, heads=["scenario", "sentinel", "F1", "precision", "recall",
                                                    "lead", "fidelity", "peak stress", "flagged",
                                                    "false alert"]), className="csf-rows"))
    return out

def _dat_list():
    with LOCK:
        dsets = list(S["datasets"])
        art = S["artefacts"]
    out = []
    if dsets:
        rows = [{"n": x["name"], "c": x["classification"], "r": str(x["n_rows"]), "h": x["sha256"][:16],
                 "s": x.get("source", "upload"), "p": "yes" if x["packable"] else "hashes only",
                 "f": "yes" if x["schema"]["participant"] and x["schema"]["flow"] else "no"} for x in dsets]
        out.append(html.Div("Datasets waiting for the next plan", className="gap-name"))
        out.append(_table(rows, ["n", "c", "r", "h", "s", "p", "f"],
                          heads=["dataset", "classification", "rows", "sha256", "source", "in evidence pack",
                                 "per participant flow"]))
    data = (art or {}).get("data")
    cals = [(x["name"], x.get("calibration")) for x in dsets if x.get("calibration")]
    if cals:
        out.append(html.Div("Calibration: what the next plan takes from each dataset", className="gap-name"))
        rows = []
        for name, cal in cals:
            p, g = cal["params"], cal["diagnostics"]
            rows.append({"n": name, "s": _fmt(p["sigma"], 4), "sh": _fmt(p["shock_size"], 3), "k": _fmt(p["kappa"], 4),
                         "w": str(p["momentum_window"]), "ff": _fmt(p["frac_fundamental"]),
                         "v": ", ".join(f"{a:.2f}/{r:.2f}" for a, r in zip(p["vendor_shares"], p["vendor_rhos"])),
                         "vs": g.get("vendor_split_source", ""),
                         "np": str(g["n_participants"]) if g["n_participants"] else "none"})
        out.append(_table(rows, ["n", "s", "sh", "k", "w", "ff", "v", "vs", "np"],
                          heads=["dataset", "volatility", "shock", "impact", "momentum window", "fundamentalists",
                                 "vendor share/rho", "split", "participants"]))
        notes = [n for _, cal in cals for n in (cal["clamped"] + cal["diagnostics"].get("notes", []))]
        out.append(html.Div(("Two families per dataset join the next plan: a calibrated synthetic market with these "
                             "parameters and the generator's ground truth, and a hybrid market where the observed "
                             "return path is the news and the synthetic agents respond to it. "
                             + ("Notes: " + "; ".join(notes) + "." if notes else "")), className="gap-note"))
    if data and data.get("calibration_shift"):
        cs = data["calibration_shift"]
        out.append(html.Div("Calibration shift: does the ranking survive the move to your structure", className="gap-name"))
        out.append(html.Div((f"Rank correlation between the decision ranking on the demonstration herds and on the "
                             f"calibrated families: {_fmt(cs['tau'])}; rank one "
                             f"{'preserved' if cs['rank_one_preserved'] else 'not preserved'} "
                             f"({_lab(cs['ranking_demonstration'][0])} against {_lab(cs['ranking_calibrated'][0])})."
                             if cs.get("positives_present") else
                             "The calibrated structure sits below the destabilising thresholds, so its families carry "
                             "no positives; they test false alerts and containment, not localisation."),
                            className="gap-note strong"))
    if data and data.get("datasets"):
        out.append(html.Div("Anchoring against the battery's quiet family (ratio observed over battery)",
                            className="gap-name"))
        for e in data["datasets"]:
            an = e.get("anchoring")
            if an and an.get("ok"):
                rows = [{"m": k, "o": _fmt(an["observed"][k], 4), "b": _fmt(an["battery_quiet"].get(k), 4),
                         "r": _fmt(an["ratios"].get(k)), "w": "within" if an["within_band"].get(k) else "outside"}
                        for k in an["ratios"]]
                out.append(html.Div(e["summary"]["name"], className="feed-cap"))
                out.append(_table(rows, ["m", "o", "b", "r", "w"],
                                  heads=["statistic", "observed", "battery quiet", "ratio", "band 0.5 to 2"]))
            ow = e.get("observed_window") or {}
            if ow.get("ok"):
                rows = [{"s": _lab(k), "a": "yes" if v["alerted"] else "no", "p": _fmt(v["peak_stress"]),
                         "n": str(v["n_flagged"]), "sh": _fmt(v["share_flagged"])} for k, v in ow["sentinels"].items()]
                out.append(html.Div(f"Observed window: {ow['n_participants']} participants over {ow['n_steps']} steps "
                                    f"(counts only, query set size {ow['k_anon']})", className="feed-cap"))
                out.append(_table(rows, ["s", "a", "p", "n", "sh"],
                                  heads=["sentinel", "alerted", "peak stress", "flagged", "share"]))
            elif ow.get("reason"):
                out.append(html.Div(f"Observed window: {ow['reason']}.", className="gap-note"))
    return out


def _sec_body():
    with LOCK:
        p = S["posture"]
        dsets = list(S["datasets"])
    if p is None:
        p = posture(CFG, datasets=[{"name": x["name"], "classification": x["classification"]} for x in dsets])
        with LOCK:
            S["posture"] = p
    chips = [html.Span(f"{p['n_pass']} pass", className="chip ok"),
             html.Span(f"{p['n_warn']} warn", className="chip warn" if p["n_warn"] else "chip"),
             html.Span(f"{p['n_fail']} fail", className="chip bad" if p["n_fail"] else "chip")]
    _cls = {"pass": "ok", "warn": "warn", "fail": "bad"}
    rows = [{"s": html.Span(i["status"], className="chip " + _cls.get(i["status"], "")),
             "c": i["control"], "d": i["detail"], "ch": "ch. " + i["sev3"]} for i in p["items"]]
    return [html.Div(chips + [html.Button("Re-check", id="sec-recheck", className="act sec-btn")], className="chip-row"),
            html.Div("Each control names the chapter of Security Engineering (Anderson, 3rd edition) whose "
                     "argument it applies; docs/SECURITY_FRAMEWORK.md has the mapping. A failing control blocks "
                     "release; a warning is recorded in the artefacts.", className="gap-note"),
            _table(rows, ["s", "c", "d", "ch"], heads=["status", "control", "detail", "chapter"])]


def _run_status():
    st = S["stage"]
    kids = []
    if S["err"]:
        kids.append(html.Div(f"Error: {S['err']}", className="seal"))
    if S["run_id"]:
        kids.append(html.Div(f"Run {S['run_id']}, prepared by {S['preparer']}, started {S['started']}",
                             className="feed-cap"))
    if st == "idle":
        kids.append(html.Div(
            "A policy officer asks a question; the orchestrator plans a battery of synthetic AI "
            "agent markets. A named supervisor approves the exact battery at Gate 1 before anything "
            "simulates, and the briefing at Gate 2 before it leaves. Either gate can be refused with "
            "reasons. Every step is chained into a signed ledger.", className="await"))
    if st == "planning":
        kids.append(html.Div("Planning: the first plan trains the RL population (~20 s). Watch LDG.",
                             className="seal arming"))
    if S["specs"] and st not in ("planning",):
        fams = {}
        for sp in S["specs"]:
            fams.setdefault(sp.family, []).append(sp)
        rows = [{"family": f, "n": len(v), "agents": v[0].n_agents,
                 "shares": ", ".join(f"{x:.2f}" for x in v[0].vendor_shares),
                 "rhos": ", ".join(f"{x:.2f}" for x in v[0].vendor_rhos),
                 "shock": "none" if v[0].shock_time is None else v[0].shock_time,
                 "note": FAMILY_NOTES.get(f, "")} for f, v in fams.items()]
        kids.append(html.Div(f"Battery: {S['n_specs']} scenarios, hash {S['battery_hash'][:16]}",
                             className="feed-cap"))
        kids.append(_table(rows, ["family", "n", "agents", "shares", "rhos", "shock", "note"], cls="data specs"))
    for gname, key in (("Gate 1", "gate1"), ("Gate 2", "gate2")):
        a = S["approvals"].get(key)
        if a:
            cls = "seal approved" if a["decision"] == "approved" else "seal refused"
            reg = a.get("register") or {}
            kids.append(html.Div(f"{gname} {a['decision']} by {a['actor']}{(' (' + a['role'] + ')') if a.get('role') else ''} at {a['ts']}"
                                 + (f"; on the register as {reg.get('function')} at {reg.get('firm')}, reference {reg.get('irn')}"
                                    if reg.get("irn") else "")
                                 + (f". Reason: {a['reason']}" if a.get("reason") else ""), className=cls))
    if st == "halted":
        kids.append(html.Div(f"Emergency stop by {S['stop_actor']}, partial ledger sealed, "
                             f"evidence pack exportable", className="seal"))
    if S["critic"] is not None:
        ok = S["critic"]["ok"]
        failed = [c["name"] for c in S["critic"]["checks"] if not c["ok"]]
        kids.append(html.Div(
            f"Critic {'passed' if ok else 'failed'}: {S['critic']['n_checks']} checks against the "
            f"artefacts and the ledger" + (f". Failed: {failed}" if failed else ""),
            className="verdict " + ("pass" if ok else "fail")))
        if ok and st == "evaluated":
            kids.append(html.Div("The briefing exists as artefacts only. Gate 2 releases it, or "
                                 "refuses it with a recorded reason.", className="await"))
    if S["run_id"] and st in ("evaluated", "released", "halted", "rejected", "refused"):
        rid = S["run_id"]
        kids.append(html.Div([
            html.A("artefacts.json", href=f"/run/{rid}/artefacts.json", target="_blank"), "  ",
            html.A("ledger.jsonl", href=f"/run/{rid}/ledger.jsonl", target="_blank"), "  ",
            html.A("evidence pack (zip)", href=f"/run/{rid}/evidence_pack.zip"),
            *(["  ", html.A("printable briefing", href=f"/run/{rid}/briefing.html", target="_blank"),
               "  ", html.A("transparency record (ATRS)", href=f"/run/{rid}/atrs_record.md", target="_blank"),
               "  ", html.A("exchange record", href=f"/run/{rid}/exchange_record.json", target="_blank")]
              if st == "released" else [])], className="links"))
    if st == "released" and S["briefing"]:
        kids.append(html.Div(dcc.Markdown(S["briefing"]), className="paper"))
    return kids


def _reg_body():
    runs = STORE.index()
    if not runs:
        return html.Div("No runs yet. Every planned run gets a directory under "
                        f"{STORE.root} with its own signed ledger.", className="await")
    rows = []
    for m in runs:
        rid = m.get("run_id", "")
        links = html.Span([
            html.A("artefacts", href=f"/run/{rid}/artefacts.json", target="_blank"), "  ",
            html.A("ledger", href=f"/run/{rid}/ledger.jsonl", target="_blank"), "  ",
            html.A("pack", href=f"/run/{rid}/evidence_pack.zip"),
            *(["  ", html.A("briefing", href=f"/run/{rid}/briefing.html", target="_blank")]
              if m.get("stage") == "released" else [])])
        rows.append({"run": rid, "created": str(m.get("created", ""))[:19], "stage": m.get("stage"),
                     "preparer": m.get("preparer"), "approver": m.get("approver") or "",
                     "gap": _fmt(m.get("decision_gap")), "pinv": _fmt(m.get("p_inversion")),
                     "question": str(m.get("question", ""))[:70], "links": links})
    return [html.Div(f"{len(rows)} runs in {STORE.root}", className="feed-cap"),
            _table(rows, ["run", "created", "stage", "preparer", "approver", "gap", "pinv", "question", "links"],
                   heads=["run", "created (UTC)", "stage", "preparer", "approver", "gap", "P(inv)", "question", "files"])]


def _ldg_verify():
    rep = S["ledger_report"]
    log = S["log"]
    if log is None:
        return "No run open"
    if rep is None:
        return f"Chain {log.seq} entries, signed, head {log.head[:12]}, replay at evaluation"
    return (f"Chain {rep['entries']} entries, {rep['signed']} signed, head {str(rep['head'])[:12]}, "
            f"{'VERIFIED' if rep['ok'] else 'BROKEN: ' + '; '.join(rep['errors'][:2])}")


_LAST_RENDER = {"t": 0.0}


@app.callback(Output("run-status", "children"), Output("plan", "disabled"),
              Output("stop", "disabled"), Output("g1a", "disabled"), Output("g1r", "disabled"),
              Output("g2a", "disabled"), Output("g2r", "disabled"),
              Output("gap-body", "children"), Output("sen-summary", "children"),
              Output("int-body", "children"), Output("aut-body", "children"),
              Output("rsk-body", "children"), Output("dat-list", "children"), Output("sec-body", "children"),
              Output("reg-body", "children"), Output("ldg-verify", "children"),
              Output("csf-body", "children"), Output("csf-frame", "href"), Output("net-frame", "src"),
              Output("mkt-3w-btn", "disabled"), Output("run-chip", "children"),
              Output("rail", "children"),
              Output("rev-store", "data"),
              Input("iv-slow", "n_intervals"), State("rev-store", "data"))
def _render(_, last_rev):
    with LOCK:
        rev, st, busy = S["rev"], S["stage"], S["busy"]
        critic, three, rid = S["critic"], S["three"], S["run_id"]
    if rev == last_rev:
        raise PreventUpdate
    # while a run is in progress the revision moves many times a second; the
    # live tape and the phase line come through the fast stream, so the full
    # panel render (every table on every page) is throttled to keep the
    # server thread from competing with the worker for the interpreter
    now = time.time()
    if busy and now - _LAST_RENDER["t"] < 3.0:
        raise PreventUpdate
    _LAST_RENDER["t"] = now
    plan_off = st in ("planning", "running") or busy
    stop_off = st not in ("planning", "running")
    g1_off = st != "planned"
    g2_off = not (st == "evaluated" and critic and critic["ok"])
    g2r_off = st != "evaluated"
    csf = f"/assets/casefile.html?run={rid or ''}&v={S['rows_rev']}"
    net = f"/assets/network.html?run={rid or ''}&v={S['net_rev']}"
    chip = f"run {rid}" if rid else ""
    return (_run_status(), plan_off, stop_off, g1_off, g1_off, g2_off, g2r_off,
            _sectioned(_gap_body(), merge_from=1, merged_label="Sentinels"), _sectioned(_sen_summary()),
            _sectioned(_int_body()), _aut_body(), _sectioned(_rsk_body()), _dat_list(), _sec_body(),
            _reg_body(), _ldg_verify(),
            _csf_body(), csf, net, three is None, chip, _rail(), rev)


@app.callback(Output("sink2", "data"), Input("plan", "n_clicks"),
              State("q", "value"), State("who", "value"), State("who-role", "value"), prevent_initial_call=True)
def _plan(n, q, who, who_role):
    if not n:
        raise PreventUpdate
    preparer = identity(who)
    if not preparer:
        _alert("alert", "A named preparer is required before planning"
               if CFG.auth_mode == "open" else "No identity header: sign in through the proxy")
        _bump()
        return no_update
    if CFG.auth_mode == "open" and not (who_role or "").strip():
        _alert("alert", "The preparer's function is required before planning (for example certified function"
               + (", or Developer1 in dev mode)" if CFG.dev_mode else ")"))
        _bump()
        return no_update
    with LOCK:
        if S["busy"] or S["stage"] in ("planning", "running"):
            raise PreventUpdate
        S["busy"] = True
    _bump()
    q = (q or DEFAULT_Q).strip()[:600]
    with LOCK:
        S["preparer_role"] = (who_role or "").strip()[:80]
    threading.Thread(target=_worker_plan, args=(q, preparer), daemon=True).start()
    return no_update


def _record_gate(key, gate_name, actor, decision, reason=None, extra=None, role=None):
    ts = utc_now()
    rec = {"actor": actor, "ts": ts, "decision": decision, "role": (role or "").strip()[:80]}
    if reason:
        rec["reason"] = reason
    verdict = REGISTER.check(actor, role) if REGISTER.configured else None
    if verdict and verdict.get("match"):
        rec["register"] = verdict["match"]
        if not rec["role"]:
            rec["role"] = verdict["match"]["function"][:80]
        extra = dict(extra or {}, register=verdict["match"])
    with LOCK:
        S["approvals"][key] = rec
        rid = S["run_id"]
    S["log"]("gate", actor=actor, gate=gate_name, decision=decision, approver=actor,
             approver_role=(role or "").strip(), reason=reason, **(extra or {}))
    STORE.write_json(rid, "approvals.json", dict(S["approvals"], preparer=S["preparer"],
                                                 preparer_role=S.get("preparer_role", "")))
    return rec


@app.callback(Output("sink4", "data"), Input("newrun", "n_clicks"), prevent_initial_call=True)
def _newrun(n):
    """Clear the terminal for a fresh run. A run in progress is stopped first; the quarantined
    datasets wait for the next plan; the last run stays in the registry on disk."""
    if not n:
        raise PreventUpdate

    def work():
        with LOCK:
            running = S["busy"] or S["stage"] in ("planning", "running")
        if running:
            STOP.set()
            for _ in range(60):
                time.sleep(0.25)
                with LOCK:
                    if not (S["busy"] or S["stage"] in ("planning", "running")):
                        break
        with LOCK:
            keep = {"datasets": list(S.get("datasets", [])), "rev": S["rev"] + 1}
            S.update(_fresh_state())
            S.update(keep)
        STOP.clear()
        _alert("info", "New run: the terminal is clear. Name a preparer and an approver and plan the battery.")
        _bump()
    threading.Thread(target=work, daemon=True).start()
    return no_update


@app.callback(Output("sink3", "data"), Input("g1a", "n_clicks"), Input("g1r", "n_clicks"),
              Input("g2a", "n_clicks"), Input("g2r", "n_clicks"), Input("stop", "n_clicks"),
              State("approver", "value"), State("reason", "value"),
              State("approver-role", "value"), State("who-role", "value"), prevent_initial_call=True)
def _gates(n1, n2, n3, n4, n5, approver_field, reason, approver_role, who_role):
    trig = ctx.triggered_id
    needed = {"plan": "plan", "stop": "stop", "g1a": "gate", "g1r": "gate", "g2a": "gate", "g2r": "gate"}.get(trig)
    if needed and not _may(needed):
        _alert("alert", f"Role {_role()} may not {needed}; refused")
        return no_update
    with LOCK:
        S["preparer_role"] = (who_role or "").strip()[:80]
    actor = identity(approver_field)
    reason = (reason or "").strip()[:400]
    rid = S["run_id"]
    if trig == "stop":
        with LOCK:
            if S["stage"] not in ("planning", "running"):
                raise PreventUpdate
            S["stop_actor"] = actor or "unnamed"
        STOP.set()
        S["log"]("emergency_stop_requested", actor=actor or "unnamed")
        _alert("alert", f"Emergency stop requested by {actor or 'unnamed'}, halting at the next check")
        _bump(phase="Emergency stop requested, halting")
        return no_update
    ok, why = authorised_approver(actor, approver_role)
    if trig in ("g1a", "g2a") and not ok:
        _alert("alert", f"Gate refused: {why}")
        if S["log"] is not None:
            S["log"]("gate_refused", actor=actor or "unnamed",
                     gate="scenario_battery_signoff" if trig == "g1a" else "briefing_release",
                     reason=why)
        _bump()
        return no_update
    if trig in ("g1r", "g2r") and (not actor or not reason):
        _alert("alert", "Refusing a gate needs a named approver and a reason")
        _bump()
        return no_update

    if trig == "g1a":
        with LOCK:
            if S["stage"] != "planned" or S["busy"]:
                raise PreventUpdate
            S["busy"] = True
        _record_gate("gate1", "scenario_battery_signoff", actor, "approved",
                     extra={"battery_hash": S["battery_hash"], "n_scenarios": S["n_specs"]}, role=approver_role)
        STORE.update_meta(rid, stage="running", approver=actor)
        _bump(stage="running", step="battery", phase="Gate 1 approved, battery streaming")
        _alert("ok", f"Gate 1 approved by {actor}, battery {S['battery_hash'][:12]} streaming")
        threading.Thread(target=_worker_run, daemon=True).start()
    elif trig == "g1r":
        with LOCK:
            if S["stage"] != "planned":
                raise PreventUpdate
        _record_gate("gate1", "scenario_battery_signoff", actor, "refused", reason,
                     extra={"battery_hash": S["battery_hash"]}, role=approver_role)
        _bump(stage="rejected", step="gate1", phase="Gate 1 refused, battery not run, plan again")
        STORE.update_meta(rid, stage="rejected", approver=actor, reason=reason)
        STORE.pack(rid)
        _alert("alert", f"Gate 1 refused by {actor}: {reason}")
    elif trig == "g2a":
        with LOCK:
            good = S["stage"] == "evaluated" and S["critic"] and S["critic"]["ok"]
            art, rows_ = S["artefacts"], S["sent_rows"]
        if not good:
            raise PreventUpdate
        approvals = {"preparer": S["preparer"], "gate1": S["approvals"].get("gate1"),
                     "gate2": {"actor": actor, "role": (approver_role or "").strip(), "ts": utc_now()}}
        text = draft_briefing(art, S["critic"], approvals, rid)
        used_llm = False
        if CFG.llm_enabled:
            text, used_llm = draft_briefing_llm(art, CLIENT, text, S["log"])
        approvals_now = dict(S["approvals"], preparer=S["preparer"], preparer_role=S.get("preparer_role", ""),
                             approver_role=(approver_role or "").strip())
        record_md = render_markdown(atrs_record(art, approvals_now, rid))
        critic = critic_check(art, rows=rows_, approved_battery_hash=S["battery_hash"],
                              ledger_path=S["log"].path, secret=CFG.secret,
                              briefing_text=text, log=S["log"], atrs_text=record_md)
        if not critic["ok"]:
            _bump(critic=critic, step="critic", phase="Critic rejected the briefing, release refused")
            _alert("alert", "Critic rejected the briefing text; release refused")
            STORE.write_json(rid, "critic.json", critic)
            return no_update
        _record_gate("gate2", "briefing_release", actor, "approved",
                     extra={"critic_checks": critic["n_checks"], "llm_drafted": used_llm}, role=approver_role)
        STORE.write_text(rid, "briefing.md", text)
        STORE.write_text(rid, "briefing.html", to_html(text))
        STORE.write_json(rid, "critic.json", critic)
        approvals_now = dict(S["approvals"], preparer=S["preparer"], preparer_role=S.get("preparer_role", ""),
                             approver_role=(approver_role or "").strip())
        record = atrs_record(art, approvals_now, rid)
        STORE.write_json(rid, "atrs_record.json", record)
        STORE.write_text(rid, "atrs_record.md", render_markdown(record))
        STORE.write_json(rid, "exchange_record.json", exchange_record(art, rid))
        _fw = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "SECURITY_FRAMEWORK.md")
        if os.path.isfile(_fw):
            with open(_fw) as f:
                STORE.write_text(rid, "security_framework.md", f.read())
        import hashlib
        S["log"]("briefing_released", actor=actor, approver=actor,
                 sha256=hashlib.sha256(text.encode()).hexdigest(), llm_drafted=used_llm)
        STORE.update_meta(rid, stage="released", approver=actor)
        pack, manifest = STORE.pack(rid)
        S["log"]("evidence_pack_built", files=list(manifest["files"]))
        rep = ledger_verify(S["log"].path, CFG.secret)
        _bump(stage="released", step="released", briefing=text, critic=critic, ledger_report=rep, llm_used=used_llm,
              phase="Briefing released, evidence pack built")
        _alert("ok", f"Briefing released, approved by {actor}, evidence pack built")
    elif trig == "g2r":
        with LOCK:
            if S["stage"] != "evaluated":
                raise PreventUpdate
        _record_gate("gate2", "briefing_release", actor, "refused", reason, role=approver_role)
        STORE.update_meta(rid, stage="refused", approver=actor, reason=reason)
        STORE.pack(rid)
        rep = ledger_verify(S["log"].path, CFG.secret)
        _bump(stage="refused", step="gate2", ledger_report=rep, phase="Gate 2 refused, briefing withheld, reasons recorded")
        _alert("alert", f"Gate 2 refused by {actor}: {reason}")
    return no_update


@app.callback(Output("dat-result", "children"), Input("dat-upload", "contents"), Input("dat-fetch", "n_clicks"),
              State("dat-upload", "filename"), State("dat-class", "value"), State("dat-source", "value"),
              State("dat-symbol", "value"), State("dat-start", "value"), State("dat-end", "value"),
              State("who", "value"), prevent_initial_call=True)
def _dat_intake(contents, n_fetch, filename, cls, source, symbol, start, end, who):
    trig = ctx.triggered_id
    who = (who or "").strip()
    if trig == "dat-upload":
        if not _may("upload"):
            return html.Div("Your role may not upload data.", className="seal refused")
        if not contents:
            raise PreventUpdate
        import base64
        try:
            header, b64 = contents.split(",", 1)
            raw = base64.b64decode(b64)
        except Exception:  # noqa: BLE001
            return html.Div("Could not decode the upload.", className="seal refused")
        ds = quarantine(filename or "upload.csv", raw, uploader=who, classification=cls or "public",
                        max_bytes=CFG.upload_max_mb * 1024 * 1024)
    else:
        if not _may("fetch"):
            return html.Div("Your role may not fetch data.", className="seal refused")
        if not symbol:
            return html.Div("Name a symbol, series or replay path.", className="seal refused")
        try:
            ds, rec = fetch_dataset(source or "replay", symbol.strip(), (start or "1900-01-01").strip(),
                                    (end or "2100-01-01").strip(), CFG, uploader=who,
                                    replay_path=None)
        except ConnectorError as e:
            return html.Div(f"Connector refused: {e}", className="seal refused")
        except Exception as e:  # noqa: BLE001
            return html.Div(f"Connector failed: {str(e)[:160]}", className="seal refused")
    if not ds.get("ok"):
        return html.Div(f"Refused: {ds.get('reason')}", className="seal refused")
    with LOCK:
        S["datasets"] = keep_recent([x for x in S["datasets"] if x["sha256"] != ds["sha256"]] + [ds])
        S["posture"] = None
        S["rev"] += 1
    return html.Div(f"Accepted {ds['name']}: {ds['n_rows']} rows, classification {ds['classification']}, sha256 "
                    f"{ds['sha256'][:16]}. It joins the next plan as a held out empirical family"
                    + (" and an observed window." if ds["schema"]["participant"] and ds["schema"]["flow"] else "."),
                    className="seal approved")


@app.callback(Output("sec-body", "children", allow_duplicate=True), Input("sec-recheck", "n_clicks"),
              prevent_initial_call=True)
def _sec_recheck(n):
    with LOCK:
        S["posture"] = None
    return _sec_body()



@app.callback(Output("fam-json", "value"), Input("fam-template", "n_clicks"), prevent_initial_call=True)
def _fam_reset(n):
    return json.dumps(family_template(), indent=1)


@app.callback(Output("fam-result", "children"), Output("fam-list", "children"), Output("fam-pick", "options"),
              Input("fam-add", "n_clicks"), Input("fam-enable", "n_clicks"), Input("fam-disable", "n_clicks"),
              Input("fam-remove", "n_clicks"), Input("rev-store", "data"),
              State("fam-json", "value"), State("fam-pick", "value"), State("who", "value"),
              prevent_initial_call=True)
def _fam_actions(n_add, n_on, n_off, n_rm, rev, text, pick, who):
    trig = ctx.triggered_id
    opts = lambda: [{"label": x["family"]["name"], "value": x["family"]["name"]} for x in FAMILIES.list()]
    if trig == "rev-store":
        return no_update, _fam_list(), opts()
    if not _may("plan"):
        return html.Div("Your role may not define families.", className="seal refused"), _fam_list(), opts()
    actor = identity(who) or "unnamed"
    if trig == "fam-add":
        try:
            doc = json.loads(text or "")
        except json.JSONDecodeError as e:
            return html.Div(f"Not valid JSON: {str(e)[:120]}", className="seal refused"), _fam_list(), opts()
        res = FAMILIES.add(doc, author=actor)
        if not res["ok"]:
            return html.Div("Refused: " + "; ".join(res["errors"]), className="seal refused"), _fam_list(), opts()
        with LOCK:
            if S["log"] is not None:
                S["log"]("family_defined", actor=actor, name=res["record"]["family"]["name"],
                         sha256=res["record"]["sha256"], clamped=res["notes"])
        msg = f"Stored {res['record']['family']['name']} ({res['record']['family']['seeds']} scenarios), sha256 " \
              f"{res['record']['sha256'][:16]}; it joins the next plan."
        if res["notes"]:
            msg += " Clamped: " + "; ".join(res["notes"]) + "."
        return html.Div(msg, className="seal approved"), _fam_list(), opts()
    if not pick:
        return html.Div("Choose a stored family first.", className="seal refused"), _fam_list(), opts()
    if trig == "fam-enable":
        FAMILIES.set_enabled(pick, True); msg = f"{pick} will join the next plan."
    elif trig == "fam-disable":
        FAMILIES.set_enabled(pick, False); msg = f"{pick} is disabled; stored, not planned."
    else:
        FAMILIES.remove(pick); msg = f"{pick} removed from the library."
    with LOCK:
        if S["log"] is not None:
            S["log"]("family_changed", actor=actor, name=pick, action=str(trig))
    return html.Div(msg, className="seal approved"), _fam_list(), opts()


@app.callback(Output("agt-json", "value"), Input("agt-template", "n_clicks"), prevent_initial_call=True)
def _agt_reset(n):
    return json.dumps(agent_template(), indent=1)


@app.callback(Output("agt-result", "children"), Output("agt-list", "children"), Output("agt-pick", "options"),
              Input("agt-add", "n_clicks"), Input("agt-probe", "n_clicks"), Input("agt-remove", "n_clicks"),
              Input("rev-store", "data"), State("agt-json", "value"), State("agt-pick", "value"),
              State("who", "value"), prevent_initial_call=True)
def _agt_actions(n_add, n_probe, n_rm, rev, text, pick, who):
    trig = ctx.triggered_id
    opts = lambda: [{"label": x["agent"]["name"], "value": x["agent"]["name"]} for x in AGENTS.list()]
    if trig == "rev-store":
        return no_update, _agt_list(), opts()
    if not _may("plan"):
        return html.Div("Your role may not define agents.", className="seal refused"), _agt_list(), opts()
    actor = identity(who) or "unnamed"
    if trig in ("agt-add", "agt-probe"):
        try:
            doc = json.loads(text or "")
        except json.JSONDecodeError as e:
            return html.Div(f"Not valid JSON: {str(e)[:120]}", className="seal refused"), _agt_list(), opts()
        ok, ag, errors, notes = validate_agent(doc)
        if not ok:
            return html.Div("Refused: " + "; ".join(errors), className="seal refused"), _agt_list(), opts()
        if trig == "agt-probe":
            p = probe_agent(ag)
            rows = [{"k": k.replace("_", " "), "v": (f"{v:.3f}" if isinstance(v, float) else str(v))}
                    for k, v in p.items()]
            return [html.Div(f"Probe of {ag['name']} at 20% of a herd market (not stored)"
                             + (". Clamped: " + "; ".join(notes) if notes else ""), className="seal arming"),
                    _table(rows, ["k", "v"], heads=["signature", "value"])], _agt_list(), opts()
        res = AGENTS.add(doc, author=actor)
        if not res["ok"]:
            return html.Div("Refused: " + "; ".join(res["errors"]), className="seal refused"), _agt_list(), opts()
        with LOCK:
            if S["log"] is not None:
                S["log"]("agent_defined", actor=actor, name=res["record"]["agent"]["name"],
                         sha256=res["record"]["sha256"], clamped=res["notes"])
        msg = f"Stored {res['record']['agent']['name']}, sha256 {res['record']['sha256'][:16]}. Reference it in a " \
              f"family as custom_agents." + (" Clamped: " + "; ".join(res["notes"]) + "." if res["notes"] else "")
        return html.Div(msg, className="seal approved"), _agt_list(), opts()
    if not pick:
        return html.Div("Choose a stored template first.", className="seal refused"), _agt_list(), opts()
    AGENTS.remove(pick)
    with LOCK:
        if S["log"] is not None:
            S["log"]("agent_removed", actor=actor, name=pick)
    return html.Div(f"{pick} removed from the workshop.", className="seal approved"), _agt_list(), opts()


if __name__ == "__main__":
    print(f"HSL TERMINAL {BUILD} · http://{CFG.host}:{CFG.port} · auth {CFG.auth_mode} · "
          f"runs in {STORE.root}" + (" · WARNING: ephemeral ledger key" if CFG.ephemeral_secret else ""))
    app.run(debug=False, host=CFG.host, port=CFG.port, threaded=True)
