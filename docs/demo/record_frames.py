"""Record the three minute demonstration as timed screenshots (four frames a
second) that are assembled into a video afterwards. On a small machine this
keeps the browser responsive, so every frame shows the terminal's true
state, and the wall clock time of each cue is logged for the captions and
the narration."""

import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("HSL_DEMO_URL", "http://127.0.0.1:8060")
HSL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_frames"
FPS = 4
os.makedirs(OUT, exist_ok=True)
QUESTION = ("Would a sentinel informed throttle have contained a flash dislocation with 40 per cent of agents on "
            "one vendor, and which surveillance tool should be certified?")

cues, frames = [], []
T0 = None
PG = None


def now():
    return time.time() - T0


def frame():
    path = os.path.join(OUT, f"f{len(frames):05d}.jpg")
    PG.screenshot(path=path, type="jpeg", quality=80)
    frames.append({"t": round(now(), 3), "path": path})


def hold(seconds):
    """Wait while capturing frames at FPS."""
    end = now() + seconds
    while now() < end:
        t = time.time()
        frame()
        rest = max(0.0, 1.0 / FPS - (time.time() - t))
        time.sleep(rest)


def cue(label, text):
    cues.append({"t": round(now(), 2), "label": label, "text": text})
    print(f"{now():6.1f}  {label}", flush=True)


def health():
    try:
        return json.loads(urllib.request.urlopen(BASE + "/healthz", timeout=5).read())["stage"]
    except Exception:
        return ""


def wait_stage(stages, timeout=240):
    """Wait for the server to reach a stage and for the page to show it, capturing frames meanwhile."""
    t = now()
    while now() - t < timeout:
        frame()
        dom = PG.locator("#live-stage").text_content().strip().lower()
        if health() in stages and dom in stages:
            return True
        time.sleep(1.0 / FPS)
    return False


def go(code, settle=0.8):
    PG.fill("#cmd", code)
    PG.keyboard.press("Enter")
    hold(settle)


def type_slow(sel, text, chunk=6, pause=0.12):
    PG.click(sel)
    PG.fill(sel, "")
    for i in range(0, len(text), chunk):
        PG.type(sel, text[i:i + chunk], delay=0)
        frame()
        time.sleep(pause)


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    PG = ctx.new_page()
    PG.goto(BASE, wait_until="load")
    T0 = time.time()
    hold(2.0)
    cue("scene", "This is the Herding Scenario Lab, a decision first sandbox in which a supervisor stress tests AI market "
                 "surveillance tools and intervention rules against synthetic AI agent markets. Everything on screen is "
                 "synthetic unless we say otherwise.")
    PG.keyboard.press("Enter")
    hold(1.5)
    go("RUN")
    cue("question", "The run starts with a policy question. Would a sentinel informed throttle have contained a flash "
                    "dislocation with forty per cent of agents on one vendor, and which surveillance tool should be "
                    "certified? The question is read deterministically into a scenario family of its own.")
    type_slow("#q", QUESTION, chunk=8, pause=0.1)
    hold(0.4)
    type_slow("#who", "D. Godorozha", chunk=3, pause=0.08)
    type_slow("#who-role", "certified function", chunk=4, pause=0.06)
    type_slow("#approver", "Nobody Here", chunk=3, pause=0.08)
    hold(0.6)

    # the input
    PG.keyboard.press("Escape"); hold(0.3)
    go("DAT")
    cue("input", "The input. This is a synthetic sample standing in for a venue's order flow file: a price, a flow per "
                 "participant, an episode marker and a label column. It is not real market data. It passes a quarantine "
                 "before it is stored.")
    PG.set_input_files("#dat-upload input[type=file]", os.path.join(HSL_ROOT, "sample_data", "labelled_flows.csv"))
    hold(3.0)
    cue("input_ok", "Accepted, hashed, classified, and calibrated: the simulator's volatility, shock, impact and vendor "
                    "split are now taken from the data.")
    hold(2.0)
    PG.set_input_files("#dat-upload input[type=file]", os.path.join(HSL_ROOT, "sample_data", "refused_pii_example.csv"))
    hold(2.5)
    cue("input_refused", "Cyber guardrail: a file carrying a personal identifier is refused, not redacted, and the "
                         "refusal says why.")
    hold(2.0)

    # plan
    PG.keyboard.press("Escape"); hold(0.3)
    go("RUN", 0.6)
    PG.click("#plan")
    cue("plan", "Plan. The battery is built and hashed: the demonstration families, the question family, and families "
                "calibrated from the data. The rail under the command bar tracks the workflow.")
    wait_stage(["planned"], timeout=120)
    hold(1.5)

    # human in the loop: the register refuses an unregistered approver, then the registered one signs off
    PG.click("#g1a")
    hold(2.0)
    cue("gate1_refused", "Human in the loop. Gate one needs a named approver who is on the authority's register of "
                         "regulated persons. Nobody Here is not, so the approval is refused and the refusal is written "
                         "to the ledger.")
    hold(1.5)
    type_slow("#approver", "R. Ahmed", chunk=2, pause=0.1)
    type_slow("#approver-role", "SMF24", chunk=2, pause=0.1)
    hold(0.6)
    PG.click("#g1a")
    hold(1.5)
    cue("gate1_ok", "R. Ahmed holds an active SMF24 on the register. Gate one approves the battery by its hash; the "
                    "match is sealed onto the gate entry. The run begins.")
    hold(2.0)

    # agents at work
    PG.keyboard.press("Escape"); hold(0.5)
    cue("agents", "Agents at work. Every market streams on the tape as it is simulated: noise traders, fundamentalists, "
                  "agents on shared vendor models, a colluding cluster, an LLM persona monoculture and a faulty vendor "
                  "model. Eight sentinels score each market as it runs, and the rules and assurance stages follow.")
    hold(6.0)
    go("MKT", 0.7)
    cue("tape", "The tape marks the shock and each sentinel's first alert. Then the intervention rules are applied to "
                "every herd and the assurance stages run: the conformal guarantee, the red team, survival and tail "
                "risk, the appraisal and the backtests.")
    hold(5.0)
    PG.keyboard.press("Escape"); hold(0.3)
    wait_stage(["evaluated", "error"], timeout=240)
    hold(1.0)
    go("NET", 0.7)
    cue("network", "The correlation network of the first herd: squares are the agents that were destabilising in "
                   "truth, amber rings the sentinel's flags, red rings the ones it missed.")
    hold(5.0)
    PG.keyboard.press("Escape"); hold(0.3)

    # guardrails firing
    go("RUN", 0.7)
    cue("critic", "Safety control: before a human can release anything, the critic recomputes every headline number "
                  "from the raw rows and replays the ledger. Twenty eight checks passed, so Gate two is armed.")
    hold(4.0)
    PG.keyboard.press("Escape"); hold(0.3)
    go("LDG", 0.7)
    cue("ledger", "Auditability. Every step, gate and refusal is a signed, hash chained ledger entry that a third party "
                  "can replay. The register match sits on the gate entry.")
    hold(4.5)
    PG.keyboard.press("Escape"); hold(0.3)
    go("SEC", 0.7)
    cue("security", "Cyber risk management. Seventeen controls checked live, each naming its chapter of Anderson's "
                    "Security Engineering; a failing control blocks release.")
    hold(4.5)
    PG.keyboard.press("Escape"); hold(0.3)
    go("GAP", 0.7)
    cue("gap", "The finding. Ranked by conventional fidelity, the volatility trigger is first. Ranked by whether it "
               "catches the destabilising agents, it is last. That is the decision gap, and the certified tool is the "
               "most accurate one whose false alert probability is bounded by a conformal guarantee.")
    hold(6.5)
    PG.keyboard.press("Escape"); hold(0.3)

    # release
    go("RUN", 0.7)
    PG.click("#g2a")
    hold(2.0)
    cue("gate2", "Gate two. The same registered approver releases the briefing. Every number in it was vetted by the "
                 "critic; a model, when one is used, only phrases text it cannot change.")
    wait_stage(["released"], timeout=120)
    hold(1.5)
    cue("output", "The output. The briefing opens with the direct answer to the question, followed by the certified "
                  "sentinel with its guarantee, the rules scored on containment and false halts, the backtests, and "
                  "the transparency record, all in an evidence pack a supervisor can replay.")
    for _ in range(3):
        PG.mouse.wheel(0, 900); hold(2.0)
    PG.keyboard.press("Escape"); hold(0.3)
    go("ASK", 0.8)
    type_slow("#ch-in", "what does the run say about my question?", chunk=4, pause=0.08)
    PG.keyboard.press("Enter")
    hold(3.0)
    cue("ask", "And a supervisor can ask the run directly. The answer is computed from the artefacts, with its sources "
               "shown. Herding Scenario Lab, by No Human Intelligence.")
    hold(4.0)
    cue("end", "")
    browser.close()

json.dump({"cues": cues, "frames": frames, "fps": FPS}, open(os.path.join(OUT, "cues.json"), "w"), indent=1)
print("total", cues[-1]["t"], "frames", len(frames))
