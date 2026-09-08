"""Assemble the demonstration video from timed frames and cues.

Outputs (in OUT):
  hsl_demo_narrated.mp4   frames + burned captions + synthetic narration (mbrola voice)
  hsl_demo_captions.mp4   frames + burned captions, no audio (for a human voice over)
  hsl_demo.srt            the captions
  hsl_demo_script.md      the narration script with timestamps
"""

import json
import os
import subprocess
import sys
import textwrap
import wave

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_frames"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/demo_out"
os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(SRC, "cues.json")))
frames, cues = d["frames"], d["cues"]
TEXT = {
 "scene": "Meet the Herding Scenario Lab.",
  "a": "Trading agents built on the same models can herd. A small shock becomes a crash.",
 "b": "Today a surveillance tool is judged on how well its signal mimics the market. That is not the question a supervisor has to answer.",
 "c": "The tool that looks best can be the worst at spotting the agents that cause the crash. Nobody measures that gap today.",
 "d": "The Lab builds markets where it knows the right answer, because it built them. It runs every surveillance tool and intervention rule against those markets, and scores each one on the question that matters: did it find the agents that caused the crash, and how early?",
 "d2": "It promises how often a tool will cry wolf on a calm market: at most one alert in four, guaranteed. It checks the winner still wins when scenarios are reshuffled or an adversary hides. And nothing leaves without two named approvers and an independent check of every number.",
 "lab": "This is the Lab, on a supervisor's own machine.",
 "question": "Every run begins with the supervisor's real question: would a targeted throttle have contained a flash crash with forty per cent of the market on one vendor's model, and which surveillance tool deserves certification?",
 "input": "Next, the data: a file standing in for a venue's order flow, one row per participant per minute. It is a synthetic sample; nothing here is confidential.",
 "input_ok": "Accepted, fingerprinted, classified, and used to calibrate the simulated markets, so the tests reflect your market, not ours.",
 "input_refused": "And the first guardrail: a file containing an email address is refused outright. Personal data never enters the sandbox.",
 "plan": "Plan. The Lab builds a battery of markets: strong herds, an evader, colluding agents, a faulty vendor model, and the exact case asked about, all hashed so what is approved is what runs.",
 "gate1_refused": "Now the human in the loop. Nothing runs without a named approver on the regulator's register. This name is not on it: refused, and recorded.",
 "gate1_ok": "A named approver on the register signs off. The battery is approved by its hash, the approval is sealed into the ledger, and the run begins.",
 "agents": "Watch the markets trade: ordinary traders, liquidity providers, agents on shared models, and a cluster trying to ignite momentum. Eight surveillance tools watch every market; then every rule is tried.",
 "tape": "",
 "network": "The market as a network. Squares are the agents that really caused the crash; amber rings are what the tool flagged; red rings, the ones it missed.",
 "critic": "Before anyone can release a result, an independent critic recomputes every figure from the raw data and replays the audit trail. Twenty eight checks passed.",
 "ledger": "Every step, approval and refusal is a signed, hash chained ledger entry. A third party can replay the run and get the same answer.",
 "security": "Seventeen security controls are checked live, from key management to the egress allowlist. If one fails, release is blocked.",
 "gap": "The finding that matters: by how well it mimics market statistics, the volatility trigger comes first; by whether it catches the agents that cause the crash, it comes last. That is the decision gap.",
 "gate2": "Gate two. The same registered approver releases the briefing.",
 "output": "The briefing answers the question asked, names the certified tool and its guarantee, scores every rule on containment and false halts, and ships as an evidence pack with a transparency record.",
 "ask": "And a supervisor can simply ask the run. Herding Scenario Lab, from No Human Intelligence.",
}
for c in cues:
    if c["label"] in TEXT:
        c["text"] = TEXT[c["label"]]
END = cues[-1]["t"] + 1.0


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"failed: {' '.join(cmd[:4])}")


# ---- 1. narration first, at a natural pace ----
VOICE = os.environ.get("HSL_DEMO_VOICE", os.path.expanduser("~/piper-voices/en-us-libritts-high.onnx"))
SPEAKER = os.environ.get("HSL_DEMO_SPEAKER", "5")
LENGTH = os.environ.get("HSL_DEMO_LENGTH", "0.97")


PACE = {"a": 0.82, "b": 0.8, "c": 0.8, "d": 0.78, "d2": 0.76, "scene": 0.85, "lab": 0.85}   # the explainer is read calmly


def synth(text, path, speed=None, label=None):
    """Neural narration with piper's high quality multi speaker model: a
    measured pace, natural timing variation, a breath between sentences,
    then a light broadcast chain (high pass, presence, compression, a touch
    of room) so it sits like a recorded voice rather than a raw synthesiser."""
    import hashlib
    key = hashlib.sha1(f"{VOICE}|{SPEAKER}|{PACE.get(label, LENGTH)}|{text}".encode()).hexdigest()[:16]
    cache = os.path.join("/tmp/narr_cache", key + ".wav")
    os.makedirs("/tmp/narr_cache", exist_ok=True)
    if os.path.exists(cache):
        import shutil
        shutil.copy(cache, path)
        with wave.open(path) as w:
            return w.getnframes() / w.getframerate()
    raw_path = path.replace(".wav", "_raw.wav")
    subprocess.run(["piper", "--model", VOICE, "--speaker", SPEAKER, "--length-scale", str(PACE.get(label, LENGTH)), "--noise-scale", "0.6",
                    "--noise-w-scale", "0.9", "--sentence-silence", "0.22", "--output_file", raw_path],
                   input=text, text=True, check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw_path, "-af",
                    "highpass=f=90,equalizer=f=3200:t=q:w=1.2:g=2.5,equalizer=f=180:t=q:w=1.0:g=1.5,"
                    "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=3,"
                    "aecho=0.85:0.55:18:0.10,alimiter=limit=0.9", "-ar", "48000", path], check=True, capture_output=True)
    import shutil
    shutil.copy(path, cache)
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


SPEED = 186
narr = {}

# ---- 1a. the user's own recordings carry the walkthrough: the full run (F) and the page tour (T) ----
import numpy as np
SRC = {"F": (np.load("/tmp/fclip/activity.npy"), "/tmp/fclip/frames/r"),
       "T": (np.load("/tmp/tclip/activity.npy"), "/tmp/tclip/frames/t")}


def condense_part(act, t0, t1, target):
    """Frames between t0 and t1 of one recording, motion at real speed and stillness compressed
    until the length lands near the target; returns 1 based frame numbers."""
    lo, hi = int(t0 * 25), min(len(act), int(t1 * 25))
    active = act[lo:hi] > 0.1
    best = None
    for step_a in (1, 2, 3, 4, 6, 8, 12):
        for step_s in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64):
            keep, i = [], 0
            while i < hi - lo:
                keep.append(lo + i + 1); i += step_a if active[i] else step_s
            length = len(keep) / 25.0
            if best is None or abs(length - target) < abs(best[0] - target):
                best = (length, keep)
    return best[1]


def condense(parts, target):
    """parts: list of (source, t0, t1, share); the target is split by share. Returns (prefix, frame) pairs."""
    total = sum(p[3] for p in parts)
    out = []
    for src, t0, t1, share in parts:
        act, prefix = SRC[src]
        out += [(prefix, k) for k in condense_part(act, t0, t1, target * share / total)]
    return out


def splice(frames, cues, label_from, label_to, keep):
    """Replace the capture between two cues with recorded frames; later cues shift with the new length."""
    t0 = next(c["t"] for c in cues if c["label"] == label_from)
    t1 = next(c["t"] for c in cues if c["label"] == label_to)
    new = [{"t": t0 + i / 25.0, "path": f"{prefix}{k:05d}.jpg"} for i, (prefix, k) in enumerate(keep)]
    shift = (t0 + len(keep) / 25.0) - t1
    frames = [f for f in frames if f["t"] < t0] + new + [dict(f, t=f["t"] + shift) for f in frames if f["t"] >= t1]
    for c in cues:
        if c["t"] >= t1 and c["label"] != label_from:
            c["t"] = round(c["t"] + shift, 2)
    return frames, cues


# every walkthrough section from the user's recordings, and every page of the terminal shown somewhere:
# F = the full run recording, T = the page tour. The refusal and the approval stay on the capture (the only
# recording with the register names).
frames, cues = splice(frames, cues, "question", "input", condense([("F", 0.0, 57.0, 1)], 9.0))
frames, cues = splice(frames, cues, "plan", "gate1_refused", condense([("F", 58.0, 66.5, 1)], 8.0))
frames, cues = splice(frames, cues, "agents", "network", condense([("F", 68.0, 92.0, 1)], 8.5))
frames, cues = splice(frames, cues, "network", "critic", condense([("T", 6.0, 43.0, 1)], 9.0))
frames, cues = splice(frames, cues, "critic", "ledger", condense([("F", 92.0, 100.0, 2), ("T", 120.0, 125.5, 1)], 8.5))
frames, cues = splice(frames, cues, "ledger", "security", condense([("T", 68.0, 75.5, 2), ("T", 162.0, 172.0, 1)], 7.0))
frames, cues = splice(frames, cues, "security", "gap", condense([("T", 154.0, 161.0, 1)], 6.0))
frames, cues = splice(frames, cues, "gap", "gate2", condense([("T", 44.0, 48.5, 3), ("T", 49.0, 53.5, 2), ("T", 54.0, 62.0, 2), ("T", 63.0, 67.5, 2)], 12.5))
frames, cues = splice(frames, cues, "gate2", "output", condense([("F", 100.0, 112.0, 1)], 3.5))
frames, cues = splice(frames, cues, "output", "ask", condense([("T", 76.0, 111.0, 4), ("T", 126.0, 140.5, 3), ("T", 149.0, 152.5, 1), ("T", 153.0, 154.0, 1)], 10.0))
frames, cues = splice(frames, cues, "ask", "end", condense([("T", 112.0, 119.5, 1)], 5.0))
# ---- 1b. the data desk section comes from the user's own recordings: the file accepted, then the file refused ----
DPLAN = json.load(open(os.environ.get("HSL_DEMO_DATA_PLAN", "/tmp/dclip/plan.json")))
t_in = next(c["t"] for c in cues if c["label"] == "input")
t_plan = next(c["t"] for c in cues if c["label"] == "plan")
A = [{"t": t_in + i / 25.0, "path": f"/tmp/dclip/a/d{k:05d}.jpg"} for i, k in enumerate(DPLAN["a"]["keep"])]
tA = t_in + len(A) / 25.0
B = [{"t": tA + i / 25.0, "path": f"/tmp/dclip/b/d{k:05d}.jpg"} for i, k in enumerate(DPLAN["b"]["keep"])]
tB = tA + len(B) / 25.0
shift_d = tB - t_plan
frames = [f for f in frames if f["t"] < t_in] + A + B + [dict(f, t=f["t"] + shift_d) for f in frames if f["t"] >= t_plan]
for c in cues:
    if c["label"] == "input_ok":
        c["t"] = round(t_in + (DPLAN["a"]["hit_idx"] or 0) / 25.0, 2)
    elif c["label"] == "input_refused":
        c["t"] = round(tA, 2)
    elif c["t"] >= t_plan and c["label"] not in ("input", "input_ok", "input_refused"):
        c["t"] = round(c["t"] + shift_d, 2)
print("data section", round(tB - t_in, 1), "s from the user's recordings")

# ---- 2. the intro card, then the user's own screen recording condensed, then the capture from the question ----
INTRO = float(os.environ.get("HSL_DEMO_INTRO", "6.0"))
q_t = next(c["t"] for c in cues if c["label"] == "question")
keep = json.load(open(os.environ.get("HSL_DEMO_CLIP_KEEP", "/tmp/clip/keep.json")))
first_frame = f"/tmp/clip/frames/c{keep[0] + 1:05d}.jpg"
intro_dir = os.path.join(OUT, "intro")
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_intro.py"), intro_dir, first_frame, f"{INTRO:.2f}"], check=True, capture_output=True)
from PIL import Image
intro_frames = []
for k in range(int(INTRO * 25)):
    png = os.path.join(intro_dir, f"i{k:04d}.png")
    jpg = os.path.join(intro_dir, f"i{k:04d}.jpg")
    Image.open(png).convert("RGB").save(jpg, quality=92)
    intro_frames.append({"t": k / 25.0, "path": jpg})
scene_dir = os.path.join(OUT, "scenes")
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_scenes.py"), scene_dir, first_frame], check=True, capture_output=True)
SC = json.load(open(os.path.join(scene_dir, "scenes.json")))
PROBLEM = SC["end"]
problem_frames = [{"t": INTRO + k / 25.0, "path": os.path.join(scene_dir, f"s{k:04d}.jpg")} for k in range(int(PROBLEM * 25))]
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_intro.py"), intro_dir, problem_frames[0]["path"], f"{INTRO:.2f}"], check=True, capture_output=True)
for k in range(int(INTRO * 25)):
    Image.open(os.path.join(intro_dir, f"i{k:04d}.png")).convert("RGB").save(os.path.join(intro_dir, f"i{k:04d}.jpg"), quality=92)
CLIP_START = INTRO + PROBLEM
clip_frames = []                                   # the first recording now appears through the walkthrough splices
CLIP = 0.0
LEAD = CLIP_START + CLIP
frames = [dict(f, t=f["t"] - q_t + LEAD) for f in frames if f["t"] >= q_t]
cues = ([dict(cues[0], t=0.0)] + [{"t": INTRO + SC[k], "label": k.lower(), "text": TEXT[k.lower()]} for k in ("A", "B", "C", "D")]
        + [{"t": INTRO + SC["D"] + 7.5, "label": "d2", "text": TEXT["d2"]}]   # moved after synthesis to follow the d line
        + [dict(c, t=c["t"] - q_t + LEAD) for c in cues[1:]])
frames = intro_frames + problem_frames + clip_frames + frames
print("intro", INTRO, "clip", round(CLIP, 1), "lead", round(LEAD, 1))

for i, c in enumerate(cues[:-1]):
    if c["text"]:
        path = os.path.join(OUT, f"cue_{i:02d}.wav")
        narr[i] = (path, synth(c["text"], path, SPEED, c["label"]))
# the second line of the closing scene starts when the first has finished
i_d = next(i for i, c in enumerate(cues) if c["label"] == "d"); i_d2 = next(i for i, c in enumerate(cues) if c["label"] == "d2")
cues[i_d2]["t"] = round(cues[i_d]["t"] + narr[i_d][1] + 0.5, 2)

# ---- 3. stretch each segment so its narration fits, then rebuild the timeline ----
new_cues, new_frames = [], []
shift = 0.0
seg_scale = []
for i, c in enumerate(cues[:-1]):
    t_start, t_stop = c["t"], cues[i + 1]["t"]
    actual = t_stop - t_start
    need = max(actual, (narr[i][1] + 0.5) if i in narr else 0.0)
    if c["label"] in ("output", "agents") and i in narr:
        need = max(min(actual, narr[i][1] + 0.8), narr[i][1] + 0.5)   # never shorter than the line spoken over it
    if c["label"] == "tape" and i not in narr:
        need = actual
    if i in narr:
        need = max(need, narr[i][1] + 0.4)
    scale = need / actual if actual > 0 else 1.0
    seg_scale.append((t_start, t_stop, scale, shift))
    new_cues.append(dict(c, t=round(t_start + shift, 2)))
    shift += need - actual
new_cues.append(dict(cues[-1], t=round(cues[-1]["t"] + shift, 2)))


def remap(t):
    for t_start, t_stop, scale, sh in seg_scale:
        if t_start <= t < t_stop:
            return t_start + sh + (t - t_start) * scale
    return t + shift


for fr in frames:
    new_frames.append(dict(fr, t=remap(fr["t"])))
END = new_cues[-1]["t"] + 0.2
print("stretched length", round(END, 1), "s")
cues, frames = new_cues, new_frames

concat = os.path.join(OUT, "frames.txt")
with open(concat, "w") as f:
    for i, fr in enumerate(frames):
        nxt = frames[i + 1]["t"] if i + 1 < len(frames) else END
        f.write(f"file '{fr['path']}'\nduration {max(0.04, nxt - fr['t']):.3f}\n")
    f.write(f"file '{frames[-1]['path']}'\n")
raw = os.path.join(OUT, "raw.mp4")
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat, "-vf", "scale=1280:800,format=yuv420p",
     "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", raw])

# ---- 3. captions ----
def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


srt = os.path.join(OUT, "hsl_demo.srt")
with open(srt, "w") as f:
    n = 1
    for i, c in enumerate(cues[:-1]):
        if not c["text"]:
            continue
        stop = min(cues[i + 1]['t'] - 0.15, c['t'] + narr[i][1] + 0.4) if i in narr else cues[i + 1]['t'] - 0.15
        f.write(f"{n}\n{srt_time(c['t'])} --> {srt_time(stop)}\n{textwrap.fill(c['text'], 92)}\n\n")
        n += 1
captioned = raw                                   # captions are written to the .srt only, not burned in

# ---- narration track placed at the new cue times ----
inputs, filters, labels = [], [], []
k = 0
for i, c in enumerate(cues[:-1]):
    if i not in narr:
        continue
    path, dur = narr[i]
    inputs += ["-i", path]
    ms = int(c["t"] * 1000)
    filters.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms}[a{k}]")
    labels.append(f"[a{k}]")
    k += 1
graph = ";".join(filters) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0:dropout_transition=0,apad=whole_dur={END:.2f}[aout]"
mix = os.path.join(OUT, "narration_mix.wav")
run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", graph, "-map", "[aout]", "-t", f"{END:.2f}", mix])
norm = os.path.join(OUT, "narration.wav")
run(["ffmpeg", "-y", "-v", "error", "-i", mix, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.95", norm])
music_src = os.path.join(OUT, "ambient.wav")
if not os.path.exists(music_src):
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "make_ambient.py"), music_src, f"{END + 2:.0f}"], check=True, capture_output=True)
bed = os.path.join(OUT, "bed.wav")
# the bed sits well under the voice and ducks a little more while the voice speaks
run(["ffmpeg", "-y", "-v", "error", "-i", music_src, "-i", norm, "-filter_complex",
     f"[0:a]atrim=0:{END:.2f},volume=-15dB[m];[1:a]aformat=channel_layouts=stereo[v];"
     "[m][v]sidechaincompress=threshold=0.05:ratio=4:attack=60:release=700:makeup=1[bed]",
     "-map", "[bed]", bed])
narrated = os.path.join(OUT, "hsl_demo_narrated.mp4")
run(["ffmpeg", "-y", "-v", "error", "-i", captioned, "-i", norm, "-i", bed, "-filter_complex",
     "[1:a]aformat=channel_layouts=stereo[v];[v][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[a]",
     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", narrated])
# the captions version carries the music alone, for a human voice over
music_only = os.path.join(OUT, "hsl_demo_captions.mp4")
run(["ffmpeg", "-y", "-v", "error", "-i", captioned, "-i", music_src, "-filter_complex",
     f"[1:a]atrim=0:{END:.2f},volume=-12dB[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
     "-b:a", "160k", "-shortest", music_only])

# ---- 4. the script ----
with open(os.path.join(OUT, "hsl_demo_script.md"), "w") as f:
    f.write("# HSL three minute demo: narration script\n\n")
    f.write("Timestamps are where each line starts in the video. Record the voice over against `hsl_demo_captions.mp4`.\n\n")
    for c in cues[:-1]:
        if c["text"]:
            m, s = divmod(int(c["t"]), 60)
            f.write(f"**{m}:{s:02d}**  {c['text']}\n\n")
    m, s = divmod(int(END), 60)
    f.write(f"Total length {m}:{s:02d}.\n")
print("done", END)
