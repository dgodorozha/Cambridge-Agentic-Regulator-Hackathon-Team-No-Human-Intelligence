"""A light, uplifting ambient bed, synthesised: a soft plucked arpeggio over a
bright four chord progression in D major, warm pads with a quick bloom, a
gentle sub, and a short reverb. Royalty free by construction.
Usage: python make_ambient.py out.wav seconds"""

import sys
import wave

import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ambient.wav"
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 200.0
SR = 48000
rng = np.random.default_rng(11)
BPM = 100.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT


def note(name):
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    n, octv = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names.index(n) - 9) / 12 + (octv - 4))


# D, A, Bm, G (I, V, vi, IV): pad voicings and arpeggio notes, bright register
CHORDS = [
    (["D3", "A3", "F#4", "A4"], ["D4", "F#4", "A4", "D5", "F#5", "A5", "D5", "A4"]),
    (["A2", "E3", "C#4", "A4"], ["A3", "C#4", "E4", "A4", "C#5", "E5", "A4", "E4"]),
    (["B2", "F#3", "D4", "B4"], ["B3", "D4", "F#4", "B4", "D5", "F#5", "B4", "F#4"]),
    (["G2", "D3", "B3", "G4"], ["G3", "B3", "D4", "G4", "B4", "D5", "G4", "D4"]),
]
t_total = SECONDS + 4.0
n = int(t_total * SR)
mix = np.zeros((n, 2), dtype=np.float64)


def add(sig, start, pan=0.5):
    i0 = int(start * SR); i1 = min(n, i0 + len(sig))
    if i1 <= i0:
        return
    s = sig[:i1 - i0]
    mix[i0:i1, 0] += s * (1 - pan)
    mix[i0:i1, 1] += s * pan


def pluck(freq, dur=0.55, amp=0.16):
    tt = np.arange(int(dur * SR)) / SR
    env = np.exp(-tt * 6.5) * (1 - np.exp(-tt * 400))
    tone = (np.sin(2 * np.pi * freq * tt) + 0.45 * np.sin(2 * np.pi * 2 * freq * tt + 0.3)
            + 0.18 * np.sin(2 * np.pi * 3 * freq * tt + 0.7) + 0.08 * np.sin(2 * np.pi * 4 * freq * tt))
    return tone * env * amp


def pad(freq, dur, amp=0.035, detune=0.004):
    tt = np.arange(int(dur * SR)) / SR
    env = np.minimum(1.0, tt / 0.8) * np.minimum(1.0, (dur - tt) / 1.2)
    env = np.clip(env, 0, 1)
    out = np.zeros_like(tt)
    for dt in (0.0, detune, -detune):
        f = freq * (1 + dt)
        out += np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)
    lfo = 1 + 0.05 * np.sin(2 * np.pi * 0.25 * tt)
    return out / 3 * env * lfo * amp


start = 0.0
bar = 0
while start < t_total:
    padnotes, arp = CHORDS[bar % 4]
    for nm in padnotes:
        add(pad(note(nm), BAR + 0.4), start, pan=0.5)
    # arpeggio in eighth notes, alternating left and right
    for k, nm in enumerate(arp):
        add(pluck(note(nm)), start + k * BEAT / 2, pan=0.35 if k % 2 == 0 else 0.65)
    # a light sub on beats one and three
    root = note(padnotes[0]) / 2
    for b in (0, 2):
        tt = np.arange(int(0.9 * SR)) / SR
        add(0.09 * np.sin(2 * np.pi * root * tt) * np.exp(-tt * 3.0), start + b * BEAT, pan=0.5)
    start += BAR
    bar += 1

# short reverb: two combs and a light all pass feel, mixed in
def comb(x, delay_ms, fb):
    d = int(SR * delay_ms / 1000)
    y = np.copy(x)
    for i in range(d, len(x)):
        y[i] += fb * y[i - d]
    return y

wet = np.zeros_like(mix)
for ch in range(2):
    x = mix[:, ch]
    wet[:, ch] = (comb(x, 29 + 4 * ch, 0.55) + comb(x, 47 - 3 * ch, 0.5)) / 2
mix = 0.8 * mix + 0.2 * wet

fade = int(2 * SR)
mix[:fade] *= np.linspace(0, 1, fade)[:, None]
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = mix / np.abs(mix).max() * 0.5
pcm = (mix * 32767).astype(np.int16)
with wave.open(OUT, "w") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
print("wrote", OUT, round(t_total, 1), "s")
