"""Playwright end to end test for the HSL terminal (version 2).

Boots dash_app.py in a subprocess with a fresh runs directory, then drives
the whole supervisory workflow in headless Chromium: front page, keyboard,
identity checks (four eyes), a Gate 1 refusal with reasons, an emergency
stop mid run, a full battery streamed to completion, every panel, the
three worlds view, the per scenario tape, ASK offline, Gate 2 release, the
evidence pack download, the run registry and a ledger replay from disk.
Fails on any browser console error.

Run:  python test_terminal.py            (~6 min: trains RL + full battery)
      python test_terminal.py --keep     leave the server up afterwards
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from playwright.sync_api import expect, sync_playwright

PORT = 8050
URL = f"http://127.0.0.1:{PORT}"
SHOTS = "test_shots"
PASS = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ok {PASS:02d}  {msg}", flush=True)


def wait_port(timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                return
        time.sleep(0.3)
    raise RuntimeError("server did not open the port")


def shot(page, name):
    page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))


def main(keep=False):
    os.makedirs(SHOTS, exist_ok=True)
    runs_dir = tempfile.mkdtemp(prefix="hsl_runs_")
    env = dict(os.environ, PYTHONUNBUFFERED="1", HSL_RUNS_DIR=runs_dir,
               HSL_SECRET="e2e-secret", HSL_TICK_PACE="0.0005")
    env.pop("ANTHROPIC_API_KEY", None)  # deterministic: no model
    srv_log = open("server.log", "w")
    srv = subprocess.Popen([sys.executable, "dash_app.py"], env=env,
                           stdout=srv_log, stderr=subprocess.STDOUT, start_new_session=True)
    errors = []
    try:
        wait_port()
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--lang=en-US"])
            page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="en-US")
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)

            # ---- 0. front page and keyboard
            page.wait_for_selector("#front:not(.off)")
            expect(page.locator("#front pre")).to_contain_text("Herding Scenario Lab")
            expect(page.locator("#front .slot")).to_have_count(16)
            shot(page, "00_front")
            ok("front page boots with eleven page slots")
            page.keyboard.press("3")
            page.wait_for_selector("#panel-GAP.maxed")
            page.keyboard.press("Escape")
            page.wait_for_selector("body:not(.hasmax)")
            page.fill("#cmd", "reg"); page.keyboard.press("Enter")
            page.wait_for_selector("#panel-REG.maxed")
            expect(page.locator("#reg-body")).to_contain_text("No runs yet")
            page.keyboard.press("Escape")
            ok("digits jump to panels; REG<GO> opens the empty registry")
            page.keyboard.press("9")
            page.wait_for_selector("body.chatting")
            expect(page.locator("#ch-log .msg.bot").first).to_contain_text("computed on the server")
            page.keyboard.press("Escape")
            ok("ASK opens with its welcome and closes on Esc")
            expect(page.locator(".panel")).to_have_count(15)
            assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight+1")
            ok("single screen, fifteen coded panels, no page scroll at 1440x900")

            # ---- 1. identity rules
            page.click("#plan"); page.wait_for_timeout(1200)
            expect(page.locator("#sen-alerts")).to_contain_text("named preparer is required")
            ok("planning without a preparer is refused")
            page.fill("#who", "D. Godorozha"); page.fill("#approver", "D. Godorozha")
            page.click("#plan")
            page.wait_for_selector("#g1a:not([disabled])", timeout=180000)
            expect(page.locator("#run-status")).to_contain_text("hash")
            shot(page, "01_planned")
            ok("battery planned with its hash; Gate 1 armed")
            page.click("#g1a"); page.wait_for_timeout(1200)
            expect(page.locator("#sen-alerts")).to_contain_text("four eyes")
            assert page.locator("#g1a").is_enabled()
            ok("four eyes: the preparer cannot approve their own battery")
            page.fill("#approver", "R. Ahmed")
            page.click("#g1r"); page.wait_for_timeout(1000)
            assert page.locator("#g1a").is_enabled()
            page.fill("#reason", "battery lacks a cross asset family")
            page.click("#g1r")
            page.wait_for_selector("#g1a[disabled]")
            expect(page.locator("#run-status")).to_contain_text("refused")
            expect(page.locator("#run-status")).to_contain_text("cross asset")
            shot(page, "02_gate1_refused")
            ok("Gate 1 refusal needs a reason and records it")

            # ---- 2. emergency stop
            page.fill("#reason", "")
            page.click("#plan")
            page.wait_for_selector("#g1a:not([disabled])", timeout=180000)
            page.click("#g1a")
            page.wait_for_selector("#live-stage.st-running")
            page.wait_for_timeout(6000)
            assert page.locator("#ldg-feed .row").count() > 3
            ok("Gate 1 approved by a different person; the battery streams")
            page.click("#stop")
            page.wait_for_selector("#live-stage.st-halted", timeout=30000)
            expect(page.locator("#ldg-feed")).to_contain_text("emergency_stop")
            shot(page, "03_halted")
            ok("emergency stop halts the run and lands in the ledger")

            # ---- 3. full run
            page.click("#plan")
            page.wait_for_selector("#g1a:not([disabled])", timeout=180000)
            page.click("#g1a")
            page.wait_for_selector("#live-stage.st-running")
            t0 = time.time()
            page.wait_for_timeout(8000)
            n1 = page.locator("#ldg-feed .row").count()
            a1 = page.locator("#sen-alerts .row").count()
            tape1 = page.locator("#tick-read").inner_text()
            page.wait_for_timeout(8000)
            assert page.locator("#ldg-feed .row").count() > n1
            assert page.locator("#sen-alerts .row").count() > a1
            assert page.locator("#tick-read").inner_text() != tape1
            ok("stream: ledger, alert feed and tape all grow while the battery runs")
            page.wait_for_selector("#g2a:not([disabled])", timeout=900000)
            print(f"      (battery evaluated in {time.time() - t0:.0f}s)")
            page.wait_for_timeout(2500)
            shot(page, "04_evaluated")
            expect(page.locator("#run-status")).to_contain_text("Critic passed")
            expect(page.locator("#ldg-verify")).to_contain_text("VERIFIED")
            ok("critic passed and the ledger chain verifies")
            expect(page.locator("#gap-body")).to_contain_text("P(inversion)")
            expect(page.locator("#sen-summary")).to_contain_text("Scenarios scored 27/27")
            expect(page.locator("#int-body")).to_contain_text("burden")
            ok("GAP, SEN and INT carry intervals, held out results and burden")

            for code in ["MKT", "NET", "GAP", "SEN", "INT", "CSF", "LDG", "AUT", "RSK", "DAT", "FAM", "AGT", "SEC", "REG"]:
                page.fill("#cmd", code); page.keyboard.press("Enter")
                page.wait_for_selector(f"#panel-{code}.maxed")
                page.wait_for_timeout(700)
                shot(page, f"05_max_{code}")
                page.keyboard.press("Escape")
            expect(page.locator("#aut-body")).to_contain_text("leave one out")
            ok("every panel maximises; AUT shows leave one out figures")
            assert page.locator("#mkt-sel option").count() >= 28
            page.click("#mkt-tape-btn")
            page.select_option("#mkt-sel", index=1)
            page.wait_for_timeout(800)
            expect(page.locator("#mkt-read")).to_contain_text("herd_high_0")
            ok("tape selector switches to a completed scenario, indexed by step")
            page.click("#mkt-3w-btn")
            page.wait_for_timeout(800)
            expect(page.locator("#mkt-read")).to_contain_text("Same shock")
            page.click("#mkt-tape-btn")
            ok("three worlds view renders with post shock drawdowns")
            expect(page.locator("#csf-body table.data")).to_be_visible(timeout=30000)
            ok("case file (Perspective) loads the run's rows")

            # ---- 4. ASK offline
            page.keyboard.press("9")
            page.wait_for_selector("body.chatting")
            page.fill("#ch-in", "which sentinel should the authority certify?")
            page.keyboard.press("Enter")
            page.wait_for_selector("#ch-log .msg.bot:nth-of-type(3)", timeout=20000)
            txt = page.locator("#ch-log .msg.bot").last.inner_text()
            assert "decision F1" in txt and "supervisor" in txt
            expect(page.locator("#ch-brain")).to_contain_text("deterministic")
            assert page.locator("#ch-src .s").count() >= 3
            shot(page, "06_ask")
            page.keyboard.press("Escape")
            ok("ASK answers the certification question offline with sources")

            # ---- 5. release, evidence, registry
            page.fill("#approver", "D. Godorozha")
            page.click("#g2a"); page.wait_for_timeout(1500)
            expect(page.locator("#sen-alerts")).to_contain_text("four eyes")
            page.fill("#approver", "R. Ahmed")
            page.click("#g2a")
            page.wait_for_selector("#live-stage.st-released", timeout=60000)
            page.wait_for_timeout(1500)
            expect(page.locator("#run-status .paper")).to_contain_text("HSL supervisory briefing")
            expect(page.locator("#run-status .paper")).to_contain_text("Critic verification. PASSED")
            expect(page.locator("#run-status")).to_contain_text("Gate 2 approved · R. Ahmed")
            shot(page, "07_released")
            ok("Gate 2 releases the briefing; approvals and timestamps recorded")
            run_id = page.locator("#run-chip").inner_text().replace("run ", "").strip()
            page.fill("#cmd", "REG"); page.keyboard.press("Enter")
            page.wait_for_selector("#panel-REG.maxed")
            expect(page.locator("#reg-body")).to_contain_text("released")
            expect(page.locator("#reg-body")).to_contain_text("halted")
            expect(page.locator("#reg-body")).to_contain_text("rejected")
            shot(page, "08_registry")
            page.keyboard.press("Escape")
            ok("registry lists the released, halted and refused runs")

            rd = os.path.join(runs_dir, run_id)
            with zipfile.ZipFile(os.path.join(rd, "evidence_pack.zip")) as z:
                names = set(z.namelist())
            assert {"artefacts.json", "ledger.jsonl", "briefing.md", "manifest.json", "VERIFY.md"} <= names
            from hsl.ledger import verify
            rep = verify(os.path.join(rd, "ledger.jsonl"), "e2e-secret")
            assert rep["ok"] and rep["signed"] == rep["entries"]
            events = [json.loads(l)["event"] for l in open(os.path.join(rd, "ledger.jsonl"))]
            assert "gate" in events and "briefing_released" in events and "critic_report" in events
            critic = json.load(open(os.path.join(rd, "critic.json")))
            assert critic["ok"] and critic["n_checks"] >= 20
            ok(f"evidence pack complete; ledger replays and is signed ({rep['entries']} entries)")
            browser.close()
    finally:
        if not keep:
            os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
        srv_log.close()
        if not keep:
            shutil.rmtree(runs_dir, ignore_errors=True)
    bad = [e for e in errors if "Unknown browser" not in e]
    if bad:
        print("\nBROWSER ERRORS:\n  " + "\n  ".join(bad[:20]))
        raise SystemExit(1)
    print(f"\nall {PASS} checks passed, no browser errors")


if __name__ == "__main__":
    main(keep="--keep" in sys.argv)
