"""The method card: how the Lab gets an answer a regulator can rely on.

Four steps, each a heading, one plain sentence and the rigorous element beneath it, appearing in turn;
the terminal's own ring and three worlds tape as small illustrations. Usage: make_method.py OUT NEXT SECONDS"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/method_frames"
NEXT = sys.argv[2] if len(sys.argv) > 2 else None
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 22.0
SHOTS = os.environ.get("HSL_DEMO_SHOTS", "/tmp/shots")
W, H, FPS = 1280, 800, 25
os.makedirs(OUT, exist_ok=True)
GROUND, INK, LINE, AMBER, AMBER2 = (5, 7, 11), (11, 15, 22), (25, 33, 45), (246, 181, 42), (181, 130, 26)
TEXT, MUTED, BLUE, OK, SURF = (228, 233, 242), (151, 163, 184), (108, 181, 255), (71, 214, 163), (16, 22, 31)


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


HEAD = font("IBMPlexSans-SemiBold", 30)
STEP = font("IBMPlexSans-SemiBold", 22)
BODY = font("IBMPlexSans-Regular", 17)
RIG = font("JetBrainsMono-Regular", 14)
MONO_B = font("JetBrainsMono-Bold", 20)
NUM = font("JetBrainsMono-Bold", 24)
ring = Image.open(os.path.join(SHOTS, "new_ring.png")).convert("RGB").crop((300, 120, 1140, 860))
tape = Image.open(os.path.join(SHOTS, "new_three_worlds.png")).convert("RGB").crop((0, 80, 1440, 600))
next_img = Image.open(NEXT).convert("RGB").resize((W, H)) if NEXT else None

STEPS = [
    ("1", "Build markets where the truth is known",
     "Synthetic markets of many agent types trade through a shock. Which agents are destabilising is fixed by how the market was built.",
     "Cross checked: Shapley attribution measures which agents actually moved prices, and must agree."),
    ("2", "Score every tool on the decision, not on the look of its signal",
     "Each surveillance tool is scored on whether it flagged those agents, and how early. Each intervention rule on how much of the crash it prevented.",
     "No hindsight: a rule sees only the flags as they stood at that moment."),
    ("3", "Guarantee the cost side",
     "How often will a tool cry wolf? A conformal threshold set on held out calm markets bounds that probability. Certification goes to the most accurate tool inside the bound.",
     "A finite sample guarantee, not an estimate: at most one false alert in four on a new calm market."),
    ("4", "Attack the answer before anyone acts on it",
     "The scenarios are reshuffled, the certification is repeated on unseen ones, and an adversary searches for a way to hide from the certified tool.",
     "Every figure is recomputed by an independent critic; two named humans sign, on the register, before release."),
]
AT = [0.4, 5.2, 10.0, 14.8]         # when each step appears


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


n = int(SECONDS * FPS)
for i in range(n):
    t = i / FPS
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=lerp(GROUND, LINE, 0.5), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=lerp(GROUND, LINE, 0.5), width=1)
    d.rectangle([0, 0, W, 3], fill=AMBER)
    d.rectangle([80, 70, 124, 114], fill=AMBER); d.text((102, 92), "M", font=font("JetBrainsMono-Bold", 26), fill=INK, anchor="mm")
    d.text((140, 92), "METHOD  HOW THE LAB GETS AN ANSWER A REGULATOR CAN RELY ON", font=MONO_B, fill=AMBER, anchor="lm")

    # illustrations on the right, fading with the steps they belong to
    a_ring = ease((t - AT[0]) / 0.8) * (1 - ease((t - AT[2]) / 0.8))
    if a_ring > 0:
        pic = ring.resize((300, int(300 * ring.height / ring.width)))
        pic = Image.blend(Image.new("RGB", pic.size, GROUND), pic, a_ring)
        img.paste(pic, (W - 80 - 300, 150)); d = ImageDraw.Draw(img)
        d.text((W - 80 - 300, 150 + pic.height + 10), "Squares: destabilising by construction. Rings: flagged.", font=RIG, fill=lerp(GROUND, MUTED, a_ring), anchor="lm")
    a_tape = ease((t - AT[2]) / 0.8)
    if a_tape > 0:
        pic = tape.resize((300, int(300 * tape.height / tape.width)))
        pic = Image.blend(Image.new("RGB", pic.size, GROUND), pic, a_tape)
        img.paste(pic, (W - 80 - 300, 150)); d = ImageDraw.Draw(img)
        d.text((W - 80 - 300, 150 + pic.height + 10), "One shock: calm, the herd, the herd under a rule.", font=RIG, fill=lerp(GROUND, MUTED, a_tape), anchor="lm")

    y = 150
    for j, (num, head, body, rig) in enumerate(STEPS):
        a = ease((t - AT[j]) / 0.6)
        if a <= 0:
            continue
        d.rectangle([80, y, 116, y + 36], fill=lerp(GROUND, AMBER, a))
        d.text((98, y + 18), num, font=NUM, fill=INK if a > 0.5 else GROUND, anchor="mm")
        d.text((130, y + 18), head, font=STEP, fill=lerp(GROUND, TEXT, a), anchor="lm")
        # wrap the body to the left column
        words, lines, cur = body.split(), [], ""
        for w_ in words:
            trial = (cur + " " + w_).strip()
            if d.textlength(trial, font=BODY) > 720:
                lines.append(cur); cur = w_
            else:
                cur = trial
        lines.append(cur)
        yy = y + 48
        for line in lines:
            d.text((130, yy), line, font=BODY, fill=lerp(GROUND, MUTED, a), anchor="lm"); yy += 24
        d.rectangle([130, yy - 2, 136, yy + 12], fill=lerp(GROUND, BLUE, a))
        d.text((146, yy + 5), rig, font=RIG, fill=lerp(GROUND, BLUE, a), anchor="lm")
        y = yy + 40

    if next_img is not None and t >= SECONDS - 0.8:
        p = ease((t - (SECONDS - 0.8)) / 0.8)
        cut = int(H * p)
        img.paste(next_img.crop((0, 0, W, cut)), (0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, cut - 2, W, cut + 2], fill=AMBER)
    img.save(os.path.join(OUT, f"m{i:04d}.jpg"), quality=92)
print("frames", n)
