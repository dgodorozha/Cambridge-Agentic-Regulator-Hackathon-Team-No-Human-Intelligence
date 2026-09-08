"""The Problem card, animated frame by frame in the terminal's design language.

About fifteen seconds: the heading types in; the person and the task appear;
the manual workflow builds box by box and is stamped with what it lacks; the
cost of getting it wrong counts up; a scanline sweep hands over to the next
frame. Usage: make_problem.py OUT_DIR NEXT_FRAME SECONDS"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/problem_frames"
NEXT = sys.argv[2] if len(sys.argv) > 2 else None
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
W, H, FPS = 1280, 800, 25
os.makedirs(OUT, exist_ok=True)
GROUND, INK, LINE, AMBER, AMBER2 = (5, 7, 11), (11, 15, 22), (25, 33, 45), (246, 181, 42), (181, 130, 26)
TEXT, MUTED, BLUE, BAD, SURF = (228, 233, 242), (151, 163, 184), (108, 181, 255), (255, 95, 95), (16, 22, 31)


def font(name, size):
    """The terminal's faces, converted from the vendored woff2 files when fontTools and brotli are present."""
    ttf = os.path.join("/tmp", name + ".ttf")
    if not os.path.exists(ttf):
        try:
            from fontTools.ttLib import TTFont
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            f = TTFont(os.path.join(root, "assets", "fonts", name + ".woff2")); f.flavor = None; f.save(ttf)
        except Exception:  # noqa: BLE001
            pass
    if os.path.exists(ttf):
        return ImageFont.truetype(ttf, size)
    fb = "DejaVuSansMono-Bold.ttf" if "Mono" in name and "Bold" in name else "DejaVuSansMono.ttf" if "Mono" in name \
        else "DejaVuSans-Bold.ttf" if "SemiBold" in name else "DejaVuSans.ttf"
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + fb, size)


MONO_B = font("JetBrainsMono-Bold", 40)
MONO = font("JetBrainsMono-Regular", 16)
MONO_S = font("JetBrainsMono-Regular", 13)
MONO_N = font("JetBrainsMono-Bold", 42)
SANS = font("IBMPlexSans-Regular", 21)
SANS_B = font("IBMPlexSans-SemiBold", 24)
SANS_S = font("IBMPlexSans-Regular", 16)
next_img = Image.open(NEXT).convert("RGB").resize((W, H)) if NEXT else None


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


HEAD = "The problem"
PERSON = ("A head of market surveillance at a securities regulator.",
          "Task: certify a new AI herding detector before the next shock.")
STEPS = ["pull three months\nof tape", "build scenarios\nin a spreadsheet", "run the tool", "compare with\nvolatility", "sign off"]
STAMPS = [("no ground truth", 1), ("no false alert guarantee", 3), ("no audit trail", 4)]
COSTS = [("$1 trillion", "erased in twenty minutes, 6 May 2010"), ("€300 billion", "wiped from European stocks in minutes, 2 May 2022"),
         ("weeks per tool", "and still no answer to the only question that matters")]

n = int(SECONDS * FPS)
for i in range(n):
    t = i / FPS
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    g = ease(t / 1.0)
    col = lerp(GROUND, LINE, 0.55 * g)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=col, width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=col, width=1)
    d.rectangle([0, 0, W, 3], fill=AMBER)

    # chip and typed heading
    d.rectangle([80, 70, 124, 114], fill=AMBER)
    d.text((102, 92), "P", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
    d.rectangle([124, 70, 262, 114], fill=INK, outline=LINE)
    d.text((193, 92), "PROBLEM", font=font("JetBrainsMono-Bold", 20), fill=AMBER, anchor="mm")
    k = min(len(HEAD), int(t / 1.1 * len(HEAD)) + 1) if t > 0 else 0
    d.text((290, 92), HEAD[:k], font=MONO_B, fill=TEXT, anchor="lm")
    if t < 2.0 and int(t * 3) % 2 == 0:
        tw = d.textlength(HEAD[:k], font=MONO_B)
        d.rectangle([290 + tw + 6, 74, 290 + tw + 22, 110], fill=AMBER)

    # the person and the task
    for j, line in enumerate(PERSON):
        a = ease((t - 1.3 - 0.6 * j) / 0.7)
        if a > 0:
            d.text((80, 160 + 34 * j), line, font=SANS_B if j == 0 else SANS, fill=lerp(GROUND, TEXT if j == 0 else MUTED, a), anchor="lm")

    # the manual workflow: boxes appear one by one with amber arrows, then the stamps
    bx0, by, bw, bh, gap = 80, 260, 200, 92, 30
    for j, step in enumerate(STEPS):
        a = ease((t - 3.0 - 0.55 * j) / 0.5)
        if a <= 0:
            continue
        x = bx0 + j * (bw + gap)
        fill = lerp(GROUND, SURF, a)
        d.rectangle([x, by, x + bw, by + bh], fill=fill, outline=lerp(GROUND, LINE, a))
        d.text((x + bw / 2, by + bh / 2), step, font=MONO, fill=lerp(GROUND, TEXT, a), anchor="mm", align="center")
        if j < len(STEPS) - 1:
            ax = x + bw + gap / 2
            d.polygon([(ax - 7, by + bh / 2 - 7), (ax + 7, by + bh / 2), (ax - 7, by + bh / 2 + 7)], fill=lerp(GROUND, AMBER, a))
    for j, (stamp, idx) in enumerate(STAMPS):
        a = ease((t - 6.2 - 0.6 * j) / 0.35)
        if a <= 0:
            continue
        x = bx0 + idx * (bw + gap) + bw / 2
        y = by + bh + 34
        scale = 1.4 - 0.4 * a
        f = font("JetBrainsMono-Bold", int(15 * scale))
        tw = d.textlength(stamp, font=f)
        stamp_img = Image.new("RGBA", (int(tw + 24), 34), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp_img)
        sd.rectangle([0, 0, stamp_img.width - 1, 33], outline=BAD + (int(255 * a),), width=2)
        sd.text((stamp_img.width / 2, 17), stamp, font=f, fill=BAD + (int(255 * a),), anchor="mm")
        stamp_img = stamp_img.rotate(-6 + 3 * j, expand=True, resample=Image.BICUBIC)
        img.paste(stamp_img, (int(x - stamp_img.width / 2), int(y - 6)), stamp_img)
        d = ImageDraw.Draw(img)
    a_note = ease((t - 8.0) / 0.6)
    if a_note > 0:
        d.text((80, by + bh + 90), "Judged on whether its stress index tracks volatility. Nobody knows which agents were really herding, so nobody knows whether it works.",
               font=SANS_S, fill=lerp(GROUND, MUTED, a_note), anchor="lm")

    # the cost, counting up
    for j, (big, small) in enumerate(COSTS):
        a = ease((t - 9.2 - 1.1 * j) / 0.9)
        if a <= 0:
            continue
        x = 80 + j * 395
        y = 560
        if j == 0:
            val = int(1000 * a)
            shown = f"${val:,} billion" if a < 1 else "$1 trillion"
        elif j == 1:
            shown = f"€{int(300 * a)} billion"
        else:
            shown = big
        d.text((x, y), shown, font=MONO_N, fill=lerp(GROUND, AMBER if j < 2 else BAD, min(1, a * 1.3)), anchor="lm")
        d.text((x, y + 50), small, font=SANS_S, fill=lerp(GROUND, MUTED, a), anchor="lm")
    a_line = ease((t - 12.6) / 0.6)
    if a_line > 0:
        d.text((80, 690), "The only question that matters: would the tool have caught the herd before the crash? Today, nobody measures it.",
               font=SANS, fill=lerp(GROUND, BLUE, a_line), anchor="lm")

    # footer keys and the sweep into the next frame
    x = 20
    for key, code in [("1", "MKT"), ("2", "NET"), ("3", "GAP"), ("4", "SEN"), ("5", "INT"), ("8", "RUN"), ("K", "RSK"), ("S", "SEC")]:
        d.rectangle([x, H - 40, x + 22, H - 18], fill=AMBER)
        d.text((x + 11, H - 29), key, font=MONO_S, fill=INK, anchor="mm")
        d.rectangle([x + 22, H - 40, x + 64, H - 18], fill=INK, outline=LINE)
        d.text((x + 43, H - 29), code, font=MONO_S, fill=AMBER, anchor="mm")
        x += 76
    if next_img is not None and t >= SECONDS - 0.8:
        p = ease((t - (SECONDS - 0.8)) / 0.8)
        cut = int(H * p)
        img.paste(next_img.crop((0, 0, W, cut)), (0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, cut - 2, W, cut + 2], fill=AMBER)
    img.save(os.path.join(OUT, f"p{i:04d}.jpg"), quality=92)
print("frames", n)
