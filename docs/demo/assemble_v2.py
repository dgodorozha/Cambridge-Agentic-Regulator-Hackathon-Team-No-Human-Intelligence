"""The regulator cut of the HSL demonstration.

Timeline
  title card (5 s) -> the sped up run from the user's first recording (about 18 s, the opening line over it)
  -> the problem in three scenes (about 19 s) -> the method card (22 s) -> the walkthrough on the user's
  recordings, each step once, with a step chip in the corner -> an end card.
Narration is synthesised with piper (speaker 0), the bed with make_ambient.py, and every segment is at least
as long as its line, so no two lines ever overlap.

Usage: assemble_v2.py OUT
"""

import json
import os
import subprocess
import sys
import textwrap
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_v2"
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 25
VOICE = os.environ.get("HSL_DEMO_VOICE", os.path.expanduser("~/piper-voices/en-us-libritts-high.onnx"))
SPEAKER = os.environ.get("HSL_DEMO_SPEAKER", "0")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:]); raise SystemExit("failed: " + " ".join(cmd[:3]))


# ------------------------------------------------------------------ recordings
def load_src(name, act_path, prefix, crop_h=None):
    return {"act": np.load(act_path), "prefix": prefix}


SRC = {
    "FIRST": {"act": np.load("/tmp/clip/activity.npy"), "prefix": "/tmp/clip/frames/c"},            # first recording: the sped up run
    "F": {"act": np.load("/tmp/fclip/activity.npy"), "prefix": "/tmp/fclip/frames/r"},              # full run
    "T": {"act": np.load("/tmp/tclip/activity.npy"), "prefix": "/tmp/tclip/frames/t"},              # page tour
}
DPLAN = json.load(open("/tmp/dclip/plan.json"))
CAP = json.load(open("/tmp/demo_frames/cues.json"))                                                # the capture, for the gates


def condense_part(act, t0, t1, target, scroll_steps=True):
    lo, hi = int(t0 * FPS), min(len(act), int(t1 * FPS))
    active = act[lo:hi] > 0.1
    best = None
    for step_a in (1, 2, 3, 4, 6, 8, 12):
        for step_s in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64):
            keep, i = [], 0
            while i < hi - lo:
                keep.append(lo + i + 1); i += step_a if active[i] else step_s
            length = len(keep) / FPS
            if best is None or abs(length - target) < abs(best[0] - target):
                best = (length, keep)
    return best[1]


def rec(parts, target):
    """A list of (source, t0, t1, share) -> list of frame paths, about target seconds long."""
    total = sum(p[3] for p in parts)
    out = []
    for src, t0, t1, share in parts:
        s = SRC[src]
        out += [f"{s['prefix']}{k:05d}.jpg" for k in condense_part(s["act"], t0, t1, target * share / total)]
    return out


def capture_frames(t0, t1):
    return [f["path"] for f in CAP["frames"] if t0 <= f["t"] < t1]


# ------------------------------------------------------------------ chips on recordings
GROUND, INK, LINE, AMBER = (5, 7, 11), (11, 15, 22), (25, 33, 45), (246, 181, 42)
CHIP_FONT = ImageFont.truetype("/tmp/JetBrainsMono-Bold.ttf", 15) if os.path.exists("/tmp/JetBrainsMono-Bold.ttf") \
    else ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 15)
ANNOT = os.path.join(OUT, "annot"); os.makedirs(ANNOT, exist_ok=True)
_cache = {}


def chip(path, key, label):
    """The frame with a step chip in the lower left corner: amber key, mono label on a dark box."""
    ck = (path, key, label)
    if ck in _cache:
        return _cache[ck]
    im = Image.open(path).convert("RGB")
    if im.size != (1280, 800):
        im = im.resize((1280, 800))
    d = ImageDraw.Draw(im, "RGBA")
    tw = d.textlength(label, font=CHIP_FONT)
    x, y = 24, 800 - 92
    d.rectangle([x, y, x + 34 + tw + 26, y + 34], fill=INK + (235,))
    d.rectangle([x, y, x + 34, y + 34], fill=AMBER + (255,))
    d.text((x + 17, y + 17), key, font=CHIP_FONT, fill=INK, anchor="mm")
    d.text((x + 34 + 13, y + 17), label, font=CHIP_FONT, fill=AMBER, anchor="lm")
    out = os.path.join(ANNOT, f"{len(_cache):06d}.jpg")
    im.save(out, quality=88)
    _cache[ck] = out
    return out


CAP_FONT = ImageFont.truetype("/tmp/IBMPlexSans-Regular.ttf", 17) if os.path.exists("/tmp/IBMPlexSans-Regular.ttf") \
    else ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
_ccache = {}


def captioned(path, text):
    """The frame with a small caption in a translucent box, bottom centre right, clear of the chip and the footer."""
    if not text:
        return path
    ck = (path, text)
    if ck in _ccache:
        return _ccache[ck]
    im = Image.open(path).convert("RGB")
    if im.size != (1280, 800):
        im = im.resize((1280, 800))
    d = ImageDraw.Draw(im, "RGBA")
    lines = textwrap.wrap(text, 76)[:3]
    lh = 23
    wmax = max(d.textlength(l, font=CAP_FONT) for l in lines)
    x0 = 440 + (800 - wmax) / 2
    y1 = 800 - 60
    y0 = y1 - lh * len(lines) - 14
    d.rectangle([x0 - 14, y0, x0 + wmax + 14, y1], fill=(5, 7, 11, 205))
    for j, l in enumerate(lines):
        d.text((x0, y0 + 8 + j * lh), l, font=CAP_FONT, fill=(228, 233, 242, 255))
    out = os.path.join(ANNOT, f"c{len(_ccache):06d}.jpg")
    im.save(out, quality=88)
    _ccache[ck] = out
    return out


# ------------------------------------------------------------------ narration
PACE = {"walk": "0.66", "explain": "0.74", "method": "0.68"}
NARR = {}


def synth(label, text, pace):
    raw_path = os.path.join(OUT, f"n_{label}_raw.wav"); path = os.path.join(OUT, f"n_{label}.wav")
    subprocess.run(["piper", "--model", VOICE, "--speaker", SPEAKER, "--length-scale", pace, "--noise-scale", "0.6",
                    "--noise-w-scale", "0.9", "--sentence-silence", "0.22", "--output_file", raw_path],
                   input=text, text=True, check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw_path, "-af",
                    "highpass=f=90,equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=180:t=q:w=1.0:g=1.5,"
                    "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=3,"
                    "aecho=0.85:0.55:18:0.10,alimiter=limit=0.9", "-ar", "48000", path], check=True, capture_output=True)
    with wave.open(path) as w:
        dur = w.getnframes() / w.getframerate()
    NARR[label] = (path, dur)
    return dur


# ------------------------------------------------------------------ the timeline
timeline = []          # list of dicts: label, frames (paths), narration text or None, chip (key, label) or None, min_len
def seg(label, frames, text=None, chip_=None, pace="walk", hold=None):
    timeline.append({"label": label, "frames": frames, "text": text, "chip": chip_, "pace": pace, "hold": hold})


# 1. title card (rendered after we know the first montage frame)
first_keep = condense_part(SRC["FIRST"]["act"], 0.12, 110.0, 12.0)
first_frames = [f"{SRC['FIRST']['prefix']}{k:05d}.jpg" for k in first_keep]
intro_dir = os.path.join(OUT, "intro")
subprocess.run([sys.executable, os.path.join(HERE, "make_intro.py"), intro_dir, first_frames[0], "5.0"], check=True, capture_output=True)
title_frames = []
for k in range(int(5.0 * FPS)):
    png = os.path.join(intro_dir, f"i{k:04d}.png"); jpg = os.path.join(intro_dir, f"i{k:04d}.jpg")
    Image.open(png).convert("RGB").save(jpg, quality=92); title_frames.append(jpg)
seg("title", title_frames, "Meet the Herding Scenario Lab.", pace="explain")

# 2. the sped up run from the first recording, the opening line over it
seg("opening", first_frames,
    "Where a regulator finds out, before the next crash, whether its surveillance tools and circuit breakers actually work.",
    pace="explain")

# 3. the problem: scenes A, B, C
scene_dir = os.path.join(OUT, "scenes")
subprocess.run([sys.executable, os.path.join(HERE, "make_scenes.py"), scene_dir, first_frames[0]], check=True, capture_output=True)
SC = json.load(open(os.path.join(scene_dir, "scenes.json")))
def scene(a, b): return [os.path.join(scene_dir, f"s{k:04d}.jpg") for k in range(int(a * FPS), int(b * FPS))]
seg("a", scene(SC["A"], SC["B"]), "Trading agents built on the same models can herd. A small shock becomes a crash.", pace="explain")
seg("b", scene(SC["B"], SC["C"]), "Today a surveillance tool is judged on how well its signal mimics the market. That is not the question a supervisor has to answer.", pace="explain")
seg("c", scene(SC["C"], SC["D"]), "The tool that looks best can be the worst at spotting the agents that cause the crash. Nobody measures that gap today.", pace="explain")

# 4. the method card
walk_first = rec([("F", 0.0, 57.0, 1)], 8.0)
method_dir = os.path.join(OUT, "method")
subprocess.run([sys.executable, os.path.join(HERE, "make_method.py"), method_dir, walk_first[0], "22.0"], check=True, capture_output=True)
method_frames = [os.path.join(method_dir, f"m{k:04d}.jpg") for k in range(int(22.0 * FPS))]
seg("method", method_frames,
    "Here is how the Lab gets an answer a regulator can rely on. It builds markets where the destabilising agents are known "
    "by construction, and checks that against which agents actually moved prices. It scores every tool on whether it found "
    "those agents, and every rule on how much of the crash it prevented. False alerts carry a finite sample guarantee. And it "
    "attacks its own answer: reshuffled scenarios, unseen ones, an adversary hiding, and a critic recomputing every figure "
    "before a named human releases it.", pace="method")

# 5. the walkthrough, each step once, on the user's recordings
seg("question", [chip(p, "1", "THE QUESTION") for p in walk_first],
    "Every run begins with the supervisor's question: would a targeted throttle have contained a flash crash with forty per cent of the market on one vendor's model, and which tool deserves certification?")
A = [f"/tmp/dclip/a/d{k:05d}.jpg" for k in DPLAN["a"]["keep"]]
B = [f"/tmp/dclip/b/d{k:05d}.jpg" for k in DPLAN["b"]["keep"]]
hit = DPLAN["a"]["hit_idx"] or int(len(A) * 0.45)
seg("input", [chip(p, "2", "YOUR DATA, THROUGH QUARANTINE") for p in A[:hit]],
    "Your own data next: a synthetic sample of a venue's order flow, through a quarantine before it is stored.")
seg("input_ok", [chip(p, "2", "YOUR DATA, THROUGH QUARANTINE") for p in A[hit:]],
    "Accepted, fingerprinted, classified, and used to calibrate the markets to yours.")
seg("input_refused", [chip(p, "2", "YOUR DATA, THROUGH QUARANTINE") for p in B],
    "A file carrying an email address is refused outright. Personal data never enters the sandbox.")
seg("plan", [chip(p, "3", "PLAN: THE BATTERY, HASHED") for p in rec([("F", 58.0, 65.5, 1)], 7.0)],
    "Plan. The Lab builds a battery of markets: strong herds, an evader, colluding agents, a faulty vendor model, and the exact case asked about, all hashed.")
t_plan, t_ref, t_ok, t_ag = (next(c["t"] for c in CAP["cues"] if c["label"] == k) for k in ("plan", "gate1_refused", "gate1_ok", "agents"))
seg("gate1_refused", [chip(p, "4", "GATE 1: A NAMED HUMAN, ON THE REGISTER") for p in capture_frames(t_ref, t_ok)],
    "Human in the loop: nothing runs without a named approver on the regulator's register. This name is not on it: refused, and recorded.")
seg("gate1_ok", [chip(p, "4", "GATE 1: A NAMED HUMAN, ON THE REGISTER") for p in capture_frames(t_ok, t_ag)],
    "R. Ahmed is on the register as an SMF24. He approves the battery, the approval is sealed into the ledger, and the run begins.")
seg("agents", [chip(p, "5", "MARKETS TRADE, SENTINELS WATCH") for p in rec([("F", 68.0, 92.0, 1)], 8.5)],
    "Watch the markets trade: ordinary traders, liquidity providers, agents on shared AI models, and one cluster trying to ignite momentum. Eight surveillance tools score every market.")
seg("network", [chip(p, "6", "THE NETWORK: TRUTH, FLAGS, MISSES") for p in rec([("T", 6.0, 43.0, 1)], 9.0)],
    "The market as a network. Squares are the agents that really caused the crash; amber rings are what the tool flagged; red rings, the ones it missed.")
seg("critic", [chip(p, "7", "THE CRITIC RECOMPUTES EVERY FIGURE") for p in rec([("F", 92.0, 100.0, 1)], 7.0)],
    "Before anyone can release a result, an independent critic recomputes every figure from the raw data and replays the audit trail.")
seg("ledger", [chip(p, "8", "SIGNED LEDGER, SECURITY POSTURE") for p in rec([("T", 68.0, 75.5, 3), ("T", 154.0, 161.0, 2)], 10.0)],
    "Every step, approval and refusal is a signed, hash chained ledger entry a third party can replay; seventeen security controls are checked live, and a failure blocks release.")
seg("gap", [chip(p, "9", "THE DECISION GAP") for p in rec([("T", 44.0, 48.5, 2), ("T", 49.0, 53.5, 1)], 10.0)],
    "The finding: by how well it mimics market statistics, the volatility trigger comes first; by whether it catches the agents who cause the crash, it comes last. That is the decision gap.")
seg("release", [chip(p, "10", "GATE 2 AND THE BRIEFING") for p in rec([("F", 100.0, 112.0, 1), ("T", 76.0, 111.0, 2)], 10.0)],
    "Gate two: the registered approver releases the briefing: the answer to the question asked, the certified tool and its guarantee, every rule scored, and an evidence pack with a transparency record.")
seg("pages", [chip(p, "16", "SIXTEEN PAGES, ONE SIGNED RUN") for p in rec([("T", 54.0, 62.0, 1), ("T", 63.0, 67.5, 1), ("T", 120.0, 125.5, 1), ("T", 126.0, 140.5, 2), ("T", 141.0, 148.0, 1), ("T", 149.0, 154.0, 1), ("T", 162.0, 172.0, 1)], 6.0)],
    "And every other page of the same signed run.")

# 6. end card
end_dir = os.path.join(OUT, "end")
subprocess.run([sys.executable, os.path.join(HERE, "make_intro.py"), end_dir, "", "5.0"], check=True, capture_output=True)
end_frames = []
for k in range(int(5.0 * FPS)):
    png = os.path.join(end_dir, f"i{k:04d}.png"); jpg = os.path.join(end_dir, f"i{k:04d}.jpg")
    Image.open(png).convert("RGB").save(jpg, quality=92); end_frames.append(jpg)
seg("end", end_frames, "Herding Scenario Lab, from No Human Intelligence. Certify the tool. Contain the crash. Keep the human in charge.", pace="explain")

# ------------------------------------------------------------------ narration, then lengths
for s in timeline:
    if s["text"]:
        synth(s["label"], s["text"], PACE[s["pace"]])

# every segment is at least its line plus a beat; the recordings are time stretched or compressed to fit
concat = os.path.join(OUT, "frames.txt")
cues, t = [], 0.0
with open(concat, "w") as f:
    for s in timeline:
        n = len(s["frames"]); actual = n / FPS
        need = actual
        if s["label"] in NARR:
            need = max(need, NARR[s["label"]][1] + 0.35)
        if s["label"] in ("question", "plan", "agents", "network", "critic", "ledger", "gap", "release", "pages"):
            need = max(NARR[s["label"]][1] + 0.35, min(actual, NARR[s["label"]][1] + 1.0))   # recordings may run faster than real time
        dur = need / n
        cues.append({"label": s["label"], "t": round(t, 2), "len": round(need, 2)})
        ndur = NARR[s["label"]][1] if s["label"] in NARR else 0.0
        chunks = []                                   # (start, end, text): long lines are shown sentence by sentence
        if s["text"]:
            import re as _re
            parts = [x.strip() for x in _re.split(r"(?<=[.?!])\s+", s["text"]) if x.strip()]
            groups, cur = [], ""
            for part in parts:
                if cur and len(cur) + len(part) > 150:
                    groups.append(cur); cur = part
                else:
                    cur = (cur + " " + part).strip()
            groups.append(cur)
            total = sum(len(g) for g in groups); pos = 0.0
            for g in groups:
                share = len(g) / total * ndur
                chunks.append((pos, pos + share, g)); pos += share
        for j, p in enumerate(s["frames"]):
            within = j * dur
            text = next((g for (x0, x1, g) in chunks if x0 <= within < x1 + 0.3), None)
            f.write(f"file '{captioned(p, text)}'\nduration {dur:.4f}\n")
        t += need
    f.write(f"file '{timeline[-1]['frames'][-1]}'\n")
END = t + 0.3
print("length", round(END, 1), "s")
for c in cues:
    print(f"  {c['t']:6.1f}  {c['len']:5.1f}  {c['label']}")
json.dump(cues, open(os.path.join(OUT, "cues.json"), "w"), indent=1)

raw0 = os.path.join(OUT, "raw0.mp4")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat, "-vf", "scale=1280:800,format=yuv420p",
     "-r", "25", "-c:v", "libx264", "-preset", "medium", "-crf", "20", raw0])

# captions file (not burned) and the script
def srt_time(x):
    ms = int(round(x * 1000)); return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"
with open(os.path.join(OUT, "hsl_demo.srt"), "w") as f, open(os.path.join(OUT, "hsl_demo_script.md"), "w") as g:
    g.write("# HSL demonstration: narration with timestamps\n\n")
    n = 1
    for s, c in zip(timeline, cues):
        if s["label"] in NARR:
            f.write(f"{n}\n{srt_time(c['t'])} --> {srt_time(c['t'] + NARR[s['label']][1])}\n{textwrap.fill(s['text'], 80)}\n\n"); n += 1
            m, sec = divmod(int(c["t"]), 60); g.write(f"**{m}:{sec:02d}**  {s['text']}\n\n")

raw = raw0

# audio: narration at cue times, bed under it with ducking
inputs, filters, labels = [], [], []
for k, (s, c) in enumerate([(s, c) for s, c in zip(timeline, cues) if s["label"] in NARR]):
    inputs += ["-i", NARR[s["label"]][0]]
    ms = int(c["t"] * 1000)
    filters.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms}[a{k}]"); labels.append(f"[a{k}]")
graph = ";".join(filters) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0:dropout_transition=0,apad=whole_dur={END:.2f}[aout]"
mix = os.path.join(OUT, "narration_mix.wav")
run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", graph, "-map", "[aout]", "-t", f"{END:.2f}", mix])
norm = os.path.join(OUT, "narration.wav")
run(["ffmpeg", "-y", "-v", "error", "-i", mix, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95", norm])
music = os.path.join(OUT, "ambient.wav")
subprocess.run([sys.executable, os.path.join(HERE, "make_ambient.py"), music, f"{END + 2:.0f}"], check=True, capture_output=True)
bed = os.path.join(OUT, "bed.wav")
run(["ffmpeg", "-y", "-v", "error", "-i", music, "-i", norm, "-filter_complex",
     f"[0:a]atrim=0:{END:.2f},volume=-15dB[m];[1:a]aformat=channel_layouts=stereo[v];"
     "[m][v]sidechaincompress=threshold=0.05:ratio=4:attack=60:release=700:makeup=1[bed]", "-map", "[bed]", bed])
run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-i", norm, "-i", bed, "-filter_complex",
     "[1:a]aformat=channel_layouts=stereo[v];[v][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[a]",
     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", os.path.join(OUT, "hsl_demo_narrated.mp4")])
run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-i", music, "-filter_complex", f"[1:a]atrim=0:{END:.2f},volume=-12dB[a]",
     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", os.path.join(OUT, "hsl_demo_captions.mp4")])
print("done", round(END, 1))
