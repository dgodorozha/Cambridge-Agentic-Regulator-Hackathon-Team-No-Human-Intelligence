"""The intro card, rendered frame by frame in the terminal's design language.

Eight seconds at 25 frames a second: the ground lights up with a faint grid,
the amber function key chip slides in, "Herding Scenario Lab" is typed in
the mono face with a cursor, the team name and a one line description fade
in, the hackathon line appears, and a scanline sweep hands over to the first
frame of the capture.
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/intro_frames"
FIRST = sys.argv[2] if len(sys.argv) > 2 else None        # first frame of the capture, for the hand over
W, H, FPS = 1280, 800, 25
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
os.makedirs(OUT, exist_ok=True)

GROUND, INK, LINE, AMBER, AMBER2, TEXT, MUTED, BLUE = (5, 7, 11), (11, 15, 22), (25, 33, 45), (246, 181, 42), (181, 130, 26), (228, 233, 242), (151, 163, 184), (108, 181, 255)

def _font(name, size):
    """The terminal's own faces, converted from the vendored woff2 files
    (needs fontTools and brotli); DejaVu as the fallback."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ttf = os.path.join("/tmp", name + ".ttf")
    if not os.path.exists(ttf):
        try:
            from fontTools.ttLib import TTFont
            f = TTFont(os.path.join(root, "assets", "fonts", name + ".woff2")); f.flavor = None; f.save(ttf)
        except Exception:  # noqa: BLE001
            fallback = "DejaVuSansMono-Bold.ttf" if "Mono" in name and "Bold" in name else \
                "DejaVuSansMono.ttf" if "Mono" in name else "DejaVuSans-Bold.ttf" if "SemiBold" in name else "DejaVuSans.ttf"
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + fallback, size)
    return ImageFont.truetype(ttf, size)


MONO_B = _font("JetBrainsMono-Bold", 46)
MONO = _font("JetBrainsMono-Regular", 20)
MONO_S = _font("JetBrainsMono-Regular", 15)
SANS = _font("IBMPlexSans-Regular", 22)
SANS_B = _font("IBMPlexSans-SemiBold", 34)
TITLE = "Herding Scenario Lab"
TEAM = "No Human Intelligence"
LINE1 = "A decision first sandbox for financial stability supervisors"
LINE2 = "C:\\>DIR Global 'Agentic Regulator' Hackathon  ·  final round"
first_img = Image.open(FIRST).convert("RGB").resize((W, H)) if FIRST else None


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


n = int(SECONDS * FPS)
for i in range(n):
    t = i / FPS
    u = t * 8.0 / SECONDS          # the choreography was written for eight seconds; scale it to the card's length
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    # faint grid that brightens over the first second
    g = ease(u / 1.2)
    col = lerp(GROUND, LINE, 0.55 * g)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=col, width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=col, width=1)
    # a thin amber rail across the top, like the workflow rail
    rail = ease((u - 0.3) / 1.0)
    d.rectangle([0, 0, int(W * rail), 3], fill=AMBER)

    # key chip sliding in from the left (0.6 to 1.4 s)
    s = ease((u - 0.6) / 0.8)
    cx = int(-160 + (210 + 160) * s)
    cy = 330
    d.rectangle([cx, cy, cx + 44, cy + 44], fill=AMBER)
    d.text((cx + 22, cy + 22), "H", font=MONO_B, fill=INK, anchor="mm")
    d.rectangle([cx + 44, cy, cx + 150, cy + 44], fill=INK, outline=LINE)
    d.text((cx + 97, cy + 22), "HSL", font=_font("JetBrainsMono-Bold", 26), fill=AMBER, anchor="mm")

    # typed title (1.4 to 3.2 s) with a cursor
    if u >= 1.4:
        k = min(len(TITLE), int((u - 1.4) / 1.8 * len(TITLE)) + 1)
        shown = TITLE[:k]
        d.text((cx + 175, cy + 22), shown, font=MONO_B, fill=TEXT, anchor="lm")
        if u < 4.0 and int(t * 3) % 2 == 0:
            tw = d.textlength(shown, font=MONO_B)
            d.rectangle([cx + 175 + tw + 6, cy + 2, cx + 175 + tw + 22, cy + 42], fill=AMBER)

    # team, description, hackathon line fading in
    a1 = ease((u - 3.3) / 0.8)
    if a1 > 0:
        d.text((210, 420), TEAM, font=SANS_B, fill=lerp(GROUND, AMBER, a1), anchor="lm")
    a2 = ease((u - 3.9) / 0.8)
    if a2 > 0:
        d.text((210, 470), LINE1, font=SANS, fill=lerp(GROUND, TEXT, a2), anchor="lm")
    a3 = ease((u - 4.5) / 0.8)
    if a3 > 0:
        d.text((210, 520), LINE2, font=MONO_S, fill=lerp(GROUND, MUTED, a3), anchor="lm")
    a4 = ease((u - 5.0) / 0.8)
    if a4 > 0:
        d.text((210, 600), "Certify the tool. Contain the crash. Keep the human in charge.", font=MONO_S, fill=lerp(GROUND, BLUE, a4), anchor="lm")
    # footer key row, like the terminal's
    if u > 2.0:
        x = 20
        for key, code in [("1", "MKT"), ("2", "NET"), ("3", "GAP"), ("4", "SEN"), ("5", "INT"), ("8", "RUN"), ("K", "RSK"), ("S", "SEC")]:
            d.rectangle([x, H - 40, x + 22, H - 18], fill=AMBER)
            d.text((x + 11, H - 29), key, font=MONO_S, fill=INK, anchor="mm")
            d.rectangle([x + 22, H - 40, x + 64, H - 18], fill=INK, outline=LINE)
            d.text((x + 43, H - 29), code, font=MONO_S, fill=AMBER, anchor="mm")
            x += 76

    # scanline sweep into the first captured frame over the last 0.8 s
    if first_img is not None and t >= SECONDS - 0.8:
        p = ease((t - (SECONDS - 0.8)) / 0.8)
        cut = int(H * p)
        img.paste(first_img.crop((0, 0, W, cut)), (0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, cut - 2, W, cut + 2], fill=AMBER)
    img.save(os.path.join(OUT, f"i{i:04d}.png"))
print("frames", n)
