"""Four explainer scenes, animated from the platform's own visuals.

A. The herd: the ring by class network slides in; the three worlds tape follows, the herd line crashing.
B. How a tool is judged today: the tool's signal drawn against the market's volatility, a fidelity score.
C. The gap: the eight sentinels ranked by fidelity and by the decision, the volatility trigger sliding
   from first to last, the decision gap figure.
D. What the Lab does: the workflow rail lighting up, then a sweep into the next frame.

Usage: make_scenes.py OUT_DIR NEXT_FRAME  (writes s0000.jpg ... and scenes.json with cue times)"""

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/scene_frames"
NEXT = sys.argv[2] if len(sys.argv) > 2 else None
SHOTS = os.environ.get("HSL_DEMO_SHOTS", "/tmp/shots")
W, H, FPS = 1280, 800, 25
os.makedirs(OUT, exist_ok=True)
GROUND, INK, LINE, AMBER, AMBER2 = (5, 7, 11), (11, 15, 22), (25, 33, 45), (246, 181, 42), (181, 130, 26)
TEXT, MUTED, BLUE, BAD, OK, SURF = (228, 233, 242), (151, 163, 184), (108, 181, 255), (255, 95, 95), (71, 214, 163), (16, 22, 31)


def font(name, size):
    ttf = os.path.join("/tmp", name + ".ttf")
    if not os.path.exists(ttf):
        try:
            from fontTools.ttLib import TTFont
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            f = TTFont(os.path.join(root, "assets", "fonts", name + ".woff2")); f.flavor = None; f.save(ttf)
        except Exception:  # noqa: BLE001
            fb = "DejaVuSansMono-Bold.ttf" if "Mono" in name and "Bold" in name else "DejaVuSansMono.ttf" if "Mono" in name \
                else "DejaVuSans-Bold.ttf" if "SemiBold" in name else "DejaVuSans.ttf"
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + fb, size)
    return ImageFont.truetype(ttf, size)


BIG = font("IBMPlexSans-SemiBold", 28)
MID = font("IBMPlexSans-Regular", 22)
SMALL = font("IBMPlexSans-Regular", 16)
MONO = font("JetBrainsMono-Regular", 15)
MONO_B = font("JetBrainsMono-Bold", 15)
MONO_N = font("JetBrainsMono-Bold", 44)

ring = Image.open(os.path.join(SHOTS, "new_ring.png")).convert("RGB").crop((300, 120, 1140, 860))
tape = Image.open(os.path.join(SHOTS, "new_three_worlds.png")).convert("RGB").crop((0, 80, 1440, 600))
next_img = Image.open(NEXT).convert("RGB").resize((W, H)) if NEXT else None

# the eight sentinels of the sample run: fidelity and decision F1
SENT = [("Volatility trigger", 1.00, 0.25), ("Absorption ratio", 0.22, 0.57), ("Endogeneity (Hawkes)", 0.21, 0.30),
        ("Correlation clustering", 0.21, 0.34), ("Buy sell imbalance", 0.20, 0.42), ("Tail dependence", 0.19, 0.68),
        ("Network community", 0.15, 0.41), ("Lead lag ignition", 0.10, 0.41)]
BY_FID = sorted(SENT, key=lambda s: -s[1])
BY_DEC = sorted(SENT, key=lambda s: -s[2])
RAIL = ["PLAN", "GATE 1", "BATTERY", "RULES", "ASSURANCE", "CRITIC", "GATE 2", "RELEASED"]

A, B, C, D = 7.0, 6.5, 6.5, 15.0
T_B, T_C, T_D, T_END = A, A + B, A + B + C, A + B + C + D


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def base():
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=lerp(GROUND, LINE, 0.5), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=lerp(GROUND, LINE, 0.5), width=1)
    d.rectangle([0, 0, W, 3], fill=AMBER)
    return img, d


def caption(d, lines, y0=640, alpha=1.0, big_first=True):
    """One or two lines of the same size and colour: a wrapped sentence, never a lowercase continuation."""
    y = y0
    for line in lines:
        d.text((80, y), line, font=BIG, fill=lerp(GROUND, TEXT, alpha), anchor="lm")
        y += 42


def framed(img, pic, x, y, w, h, alpha):
    pic = pic.resize((w, h))
    if alpha < 1:
        pic = Image.blend(Image.new("RGB", pic.size, GROUND), pic, alpha)
    img.paste(pic, (x, y))
    ImageDraw.Draw(img).rectangle([x - 1, y - 1, x + w, y + h], outline=lerp(GROUND, LINE, alpha))


def tag(d, x, y, text, alpha=1.0, colr=AMBER):
    d.rectangle([x, y, x + 12 + d.textlength(text, font=MONO_B), y + 24], fill=lerp(GROUND, INK, alpha), outline=lerp(GROUND, LINE, alpha))
    d.text((x + 6, y + 12), text, font=MONO_B, fill=lerp(GROUND, colr, alpha), anchor="lm")


n = int(T_END * FPS)
for i in range(n):
    t = i / FPS
    img, d = base()

    if t < T_B:                                                     # ---- A. the herd
        u = t
        a1 = ease(u / 0.8)
        # the ring slides in from the right and slowly grows
        z = 1.0 + 0.06 * u / A
        w = int(560 * z); h = int(560 * z * ring.height / ring.width)
        x = int(W - 60 - w + (1 - a1) * 300); y = 70
        framed(img, ring, x, y, w, h, a1)
        d = ImageDraw.Draw(img)
        tag(d, x + 12, y + 12, "NET  Ring by class", a1)
        a2 = ease((u - 3.4) / 0.8)
        if a2 > 0:
            # the tape rises from below, the herd line in red
            tw = 560; th = int(560 * tape.height / tape.width)
            ty = int(H - 40 - th + (1 - a2) * 200)
            framed(img, tape, 80, ty - 0, tw, th, a2)
            d = ImageDraw.Draw(img)
            tag(d, 92, ty + 12, "MKT  Three worlds", a2)
        caption(d, ["Trading agents built on the same models can herd."], 300, ease(u / 0.8))
        if u > 3.4:
            caption(d, ["A small shock becomes a crash."], 350, ease((u - 3.4) / 0.8))
        # hero mark
        d.rectangle([80, 70, 124, 114], fill=AMBER); d.text((102, 92), "H", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
        d.text((140, 92), "THE HERD", font=font("JetBrainsMono-Bold", 20), fill=AMBER, anchor="lm")

    elif t < T_C:                                                   # ---- B. how a tool is judged today
        u = t - T_B
        a = ease(u / 0.8)
        d.rectangle([80, 70, 124, 114], fill=AMBER); d.text((102, 92), "?", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
        d.text((140, 92), "HOW A TOOL IS JUDGED TODAY", font=font("JetBrainsMono-Bold", 20), fill=AMBER, anchor="lm")
        # a market volatility line and a tool signal that mimics it
        x0, y0, w, h = 80, 150, 1120, 330
        d.rectangle([x0, y0, x0 + w, y0 + h], fill=lerp(GROUND, SURF, a), outline=lerp(GROUND, LINE, a))
        pts_m, pts_s = [], []
        for k in range(0, w, 4):
            xx = x0 + k
            phase = k / w * 6 * math.pi
            m = 0.5 + 0.28 * math.sin(phase) + 0.12 * math.sin(3.1 * phase + 1) + (0.25 if 0.42 < k / w < 0.5 else 0)
            s = m + 0.04 * math.sin(11 * phase)
            reveal = min(1.0, max(0.0, (u - 0.6) / 3.0))
            if k / w <= reveal:
                pts_m.append((xx, y0 + h - 30 - m * (h - 60)))
                pts_s.append((xx, y0 + h - 30 - s * (h - 60) - 6))
        if len(pts_m) > 1:
            d.line(pts_m, fill=lerp(GROUND, MUTED, a), width=2)
            d.line(pts_s, fill=lerp(GROUND, AMBER, a), width=3)
        d.text((x0 + 16, y0 + 18), "Market volatility", font=MONO, fill=lerp(GROUND, MUTED, a), anchor="lm")
        d.text((x0 + 16, y0 + 40), "The tool's stress signal", font=MONO, fill=lerp(GROUND, AMBER, a), anchor="lm")
        a3 = ease((u - 3.8) / 0.7)
        if a3 > 0:
            d.text((x0 + w - 20, y0 + 30), "Fidelity 1.00", font=MONO_N, fill=lerp(GROUND, OK, a3), anchor="rm")
            d.text((x0 + w - 20, y0 + 70), "It looks like the market, so it passes.", font=MONO, fill=lerp(GROUND, MUTED, a3), anchor="rm")
        caption(d, ["Today a surveillance tool is judged on how well its signal mimics",
                    "the market: volatility, spreads and correlation."], 545, a)
        if u > 4.6:
            caption(d, ["That is not the question a supervisor has to answer."], 660, ease((u - 4.6) / 0.7))

    elif t < T_D:                                                   # ---- C. the gap
        u = t - T_C
        a = ease(u / 0.7)
        d.rectangle([80, 70, 124, 114], fill=AMBER); d.text((102, 92), "G", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
        d.text((140, 92), "GAP  THE DECISION GAP", font=font("JetBrainsMono-Bold", 20), fill=AMBER, anchor="lm")
        colx = (80, 680); heads = ("Ranked by how well it mimics the market", "Ranked by whether it catches the agents that cause the crash")
        rowh = 40; y0 = 190
        swap = ease((u - 2.2) / 1.6)
        for c, (lst, head) in enumerate(((BY_FID, heads[0]), (BY_DEC, heads[1]))):
            x = colx[c]
            d.text((x, 150), head, font=SMALL, fill=lerp(GROUND, MUTED, a), anchor="lm")
            for r, (name, fid, dec) in enumerate(lst):
                show = ease((u - 0.3 - 0.12 * r) / 0.4)
                if show <= 0:
                    continue
                hot = name == "Volatility trigger"
                yy = y0 + r * rowh
                if hot and c == 0:
                    pass
                val = fid if c == 0 else dec
                colr = AMBER if hot else TEXT
                d.text((x, yy), f"{r + 1}", font=MONO, fill=lerp(GROUND, MUTED, show), anchor="lm")
                d.text((x + 34, yy), name, font=MID if hot else SMALL, fill=lerp(GROUND, colr, show), anchor="lm")
                d.text((x + 500, yy), f"{val:.2f}", font=MONO_B, fill=lerp(GROUND, colr, show), anchor="rm")
        # the connecting line for the volatility trigger: first on the left, last on the right
        if swap > 0:
            y_l = y0 + 0 * rowh; y_r = y0 + 7 * rowh
            xa, xb = colx[0] + 520, colx[1] - 20
            pts = []
            for k in range(0, 41):
                f = k / 40
                if f > swap:
                    break
                xx = xa + (xb - xa) * f
                yy = y_l + (y_r - y_l) * (0.5 - 0.5 * math.cos(math.pi * f))
                pts.append((xx, yy))
            if len(pts) > 1:
                d.line(pts, fill=AMBER, width=3)
        a4 = ease((u - 3.8) / 0.7)
        if a4 > 0:
            d.text((80, 540), "Decision gap 0.68", font=MONO_N, fill=lerp(GROUND, BAD, a4), anchor="lm")
            d.text((80, 580), "Zero would be the same order, one the exact reverse.", font=SMALL, fill=lerp(GROUND, MUTED, a4), anchor="lm")
        caption(d, ["The tool that looks best can be the worst at spotting the agents",
                    "that cause the crash. Nobody measures that gap today."], 640, a)

    else:                                                           # ---- D. what the Lab does, and why it is new
        u = t - T_D
        a = ease(u / 0.6)
        d.rectangle([80, 70, 124, 114], fill=AMBER); d.text((102, 92), "H", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
        d.text((140, 92), "HSL  WHAT THE LAB DOES", font=font("JetBrainsMono-Bold", 20), fill=AMBER, anchor="lm")
        if u < 7.5:
            # the architecture, box by box, in the order a run follows it
            boxes = [("Policy question", "In plain words", 0.3, False), ("Planner", "Battery hashed", 0.8, False),
                     ("Gate 1", "Named human, on the register", 1.3, True),
                     ("Synthetic markets", "Truth known: 8 agent types, learned herding", 1.8, False),
                     ("8 sentinels, 8 rules", "EU, UK and US instruments", 2.4, False),
                     ("Decision evaluator", "Decision F1, decision gap, conformal guarantee", 3.0, False),
                     ("Critic", "Recomputes every figure", 3.6, False), ("Gate 2", "Named human release", 4.1, True),
                     ("Briefing and evidence pack", "Signed ledger, transparency record", 4.6, False)]
            cols, bw, bh, gx, gy = 3, 355, 96, 28, 26
            for j, (title, sub, at, gate) in enumerate(boxes):
                ab = ease((u - at) / 0.45)
                if ab <= 0:
                    continue
                x = 80 + (j % cols) * (bw + gx); y = 160 + (j // cols) * (bh + gy)
                d.rectangle([x, y, x + bw, y + bh], fill=lerp(GROUND, INK if gate else SURF, ab), outline=lerp(GROUND, AMBER2 if gate else LINE, ab))
                d.rectangle([x + 14, y + 16, x + 22, y + 24], fill=lerp(GROUND, AMBER, ab))
                d.text((x + 32, y + 20), title, font=font("IBMPlexSans-SemiBold", 18), fill=lerp(GROUND, AMBER if gate else TEXT, ab), anchor="lm")
                d.text((x + 14, y + 52), sub, font=SMALL, fill=lerp(GROUND, MUTED, ab), anchor="lm")
                if j < len(boxes) - 1:
                    nx = x + bw + gx / 2 if (j % cols) < cols - 1 else None
                    if nx is not None:
                        d.polygon([(nx - 6, y + bh / 2 - 6), (nx + 6, y + bh / 2), (nx - 6, y + bh / 2 + 6)], fill=lerp(GROUND, AMBER, ab))
            caption(d, ["The Lab builds markets where the truth is known, runs every surveillance tool",
                        "and intervention rule against them, and scores each on the decision."], 560, a)
            an = ease((u - 5.2) / 0.6)
            if an > 0:
                d.text((80, 655), "Which agents were destabilising, and when to act. Two named human gates and a critic sit around every number.",
                       font=MID, fill=lerp(GROUND, MUTED, an), anchor="lm")
        else:
            v = u - 7.5
            av = ease(v / 0.6)
            d.text((80, 150), "What is new", font=font("IBMPlexSans-SemiBold", 24), fill=lerp(GROUND, TEXT, av), anchor="lm")
            claims = [("It scores each tool on the question that matters", "Did it find the agents that caused the crash, and how early?", 0.2),
                      ("It promises how often a tool will cry wolf", "On a calm market, at most one alert in four. That bound is a guarantee, not an estimate.", 1.1),
                      ("It knows the right answer, because it built the market", "And it checks that answer by measuring which agents actually moved prices.", 2.0),
                      ("It tests the certificate itself", "Does the winner still win when the scenarios are reshuffled, or when an adversary hides? Here it did, 98 times in 100.", 2.9),
                      ("It runs on your data, under your names", "Markets rebuilt to look like yours; two named approvers on the regulator's register; every number recomputed by an independent critic.", 3.8)]
            for j, (head, sub, at) in enumerate(claims):
                ac = ease((v - at) / 0.5)
                if ac <= 0:
                    continue
                y = 200 + j * 78
                d.rectangle([80, y - 6, 92, y + 6], fill=lerp(GROUND, AMBER, ac))
                d.text((108, y), head, font=font("IBMPlexSans-SemiBold", 21), fill=lerp(GROUND, TEXT, ac), anchor="lm")
                d.text((108, y + 30), sub, font=SMALL, fill=lerp(GROUND, MUTED, ac), anchor="lm")
            ap = ease((v - 5.0) / 0.6)
            if ap > 0:
                d.text((80, 610), "The research behind it is ours: the tools that look most accurate on aggregate statistics are close to the",
                       font=SMALL, fill=lerp(GROUND, BLUE, ap), anchor="lm")
                d.text((80, 634), "worst at the supervisory decision (ICAIF 2026 submission). No supervisory tool measures this today.",
                       font=SMALL, fill=lerp(GROUND, BLUE, ap), anchor="lm")
        if next_img is not None and u >= D - 0.8:
            p = ease((u - (D - 0.8)) / 0.8)
            cut = int(H * p)
            img.paste(next_img.crop((0, 0, W, cut)), (0, 0))
            d = ImageDraw.Draw(img)
            d.rectangle([0, cut - 2, W, cut + 2], fill=AMBER)

    img.save(os.path.join(OUT, f"s{i:04d}.jpg"), quality=92)

json.dump({"A": 0.0, "B": T_B, "C": T_C, "D": T_D, "end": T_END}, open(os.path.join(OUT, "scenes.json"), "w"))
print("frames", n, "length", T_END)
