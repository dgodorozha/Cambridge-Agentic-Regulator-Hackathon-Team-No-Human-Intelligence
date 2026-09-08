"""Figures from a run directory, for a paper or poster.

  python figures.py runs/<run_id> [outdir]

Produces:
  fig_market.png     same shock, three worlds (quiet, herd, sentinel informed throttle)
  fig_inversion.png  aggregate fidelity against decision F1 with 95% intervals, per sentinel
  fig_gap_matrix.png decision gap and P(inversion) under both fidelity constructs
  fig_dose.png       concentration dose response: post shock drawdown against the
                     dominant vendor's share (Meng and Chen 2026 convexity test)
  fig_frontier.png   supervisory cost frontier: sentinel loss against the declared
                     weight on false alerts
  fig_attribution.png Shapley attribution of post shock drawdown to agent groups

Style: no grey fills or borders, sentence case labels, colour used only as
an accent, precise metric names.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ACCENT = "#b8860b"
INK = "#1a1a1a"
BLUE = "#2a5a8a"


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9)


def fig_market(three, out):
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.plot(three["quiet"], color="#5c6b7a", lw=1.2, label="quiet market (low correlation)")
    ax.plot(three["herd"], color=ACCENT, lw=1.6, label="herding market (rho 0.90, 40% one vendor)")
    ax.plot(three["treated"], color=BLUE, lw=1.6, label="herding with sentinel informed dynamic throttle")
    ax.axvline(three["shock"], color=INK, ls=":", lw=1, label="fundamental shock")
    ax.set_xlabel("simulation step"); ax.set_ylabel("price")
    d = three.get("post_shock_dd", {})
    ax.set_title(f"Same shock, three worlds. Post shock drawdown: quiet {d.get('quiet', 0):.3f}, "
                 f"herd {d.get('herd', 0):.3f}, throttle {d.get('treated', 0):.3f}", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    _style(ax); fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_market.png"), dpi=200); plt.close(fig)


def fig_inversion(art, out):
    s = art["sentinels"]
    names = list(s)
    labels = [n.replace("_", " ") for n in names]
    fid = [s[n]["aggregate_fidelity"] for n in names]
    dec = [s[n]["decision_f1"] for n in names]
    ci = np.array([s[n]["ci"]["decision_f1"] for n in names])
    x = np.arange(len(names)); w = 0.36
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.bar(x - w / 2, fid, w, color=BLUE, label="aggregate fidelity (rolling volatility construct)")
    ax.bar(x + w / 2, dec, w, color=ACCENT, label="decision accuracy (F1 on destabilising agents)")
    ax.errorbar(x + w / 2, dec, yerr=[np.array(dec) - ci[:, 0], ci[:, 1] - np.array(dec)],
                fmt="none", ecolor=INK, capsize=3, lw=1)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 1.05); ax.set_ylabel("score")
    g, gb = art["decision_gap"], art["decision_gap_bootstrap"]
    ax.set_title(f"Decision gap {g['decision_gap']:.2f} (Kendall tau {g['kendall_tau']:+.2f}); "
                 f"probability of inversion {gb['p_inversion']:.2f} over {gb['B']} scenario resamples",
                 fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    _style(ax); fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_inversion.png"), dpi=200); plt.close(fig)


def fig_gap_matrix(art, out):
    rows = [("conventional (volatility)", art["decision_gap"], art["decision_gap_bootstrap"]),
            ("multi moment", art["decision_gap_moments"], art["decision_gap_bootstrap_moments"])]
    gh = art.get("decision_gap_holdout")
    fig, ax = plt.subplots(figsize=(6.5, 2.6))
    ax.axis("off")
    cells = [[r[0], f"{r[1]['decision_gap']:.2f}", f"{r[1]['kendall_tau']:+.2f}",
              f"{r[2]['p_inversion']:.2f}", f"[{r[2]['gap_ci'][0]:.2f}, {r[2]['gap_ci'][1]:.2f}]"]
             for r in rows]
    if gh:
        cells.append(["held out family (conventional)", f"{gh['decision_gap']:.2f}",
                      f"{gh['kendall_tau']:+.2f}", "", ""])
    tb = ax.table(cellText=cells, colLabels=["fidelity construct", "gap", "tau", "P(inversion)",
                                             "gap 95% interval"], loc="center", cellLoc="center")
    tb.auto_set_font_size(False); tb.set_fontsize(9); tb.scale(1, 1.4)
    for (r, _c), cell in tb.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if r == 0:
            cell.set_text_props(weight="bold")
    ax.set_title("The decision gap under each declared fidelity construct", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_gap_matrix.png"), dpi=200); plt.close(fig)


def fig_dose(art, out):
    d = art.get("concentration")
    if not d:
        return
    x = [l["share"] for l in d["levels"]]
    y = [l["mean_post_shock_dd"] for l in d["levels"]]
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    ax.plot(x, y, "o-", color=ACCENT, lw=1.6, ms=5, label="mean post shock drawdown")
    xx = np.linspace(min(x), max(x), 100)
    coef = np.polyfit(x, y, 2)
    ax.plot(xx, np.polyval(coef, xx), color=BLUE, lw=1.2, ls="--",
            label=f"quadratic fit (curvature {d['curvature']:.2f})")
    ax.axhline(d["dislocation_dd"], color=INK, ls=":", lw=1, label="dislocation threshold")
    ax.axhline(d["quiet_baseline_dd"], color="#5c6b7a", ls=":", lw=1, label="quiet baseline")
    ax.set_xlabel("share of agents on the dominant vendor (correlation held at %.2f)" % d["rho"], fontsize=9)
    ax.set_ylabel("post shock drawdown", fontsize=9)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_dose.png"), dpi=200); plt.close(fig)


def fig_frontier(art, out):
    s = art["sentinels"]
    fr = art.get("frontier", {}).get("sentinels")
    if not fr:
        return
    grid = np.linspace(0, 1, 101)
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for n, v in s.items():
        fa = v.get("false_alert_rate") or 0.0
        miss = 1.0 - (v.get("recall") or 0.0)
        ax.plot(grid, grid * fa + (1 - grid) * miss, lw=1.3, label=n.replace("_", " "))
    ax.axvline(fr["c_declared"], color=INK, ls=":", lw=1)
    ax.set_xlabel("declared weight c on a false alert relative to a miss", fontsize=9)
    ax.set_ylabel("supervisory loss", fontsize=9)
    ax.legend(fontsize=7.5, frameon=False, ncol=2)
    _style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_frontier.png"), dpi=200); plt.close(fig)


def fig_attribution(art, out):
    at = art.get("attribution")
    if not at or not at["scenarios"]:
        return
    scen = at["scenarios"]
    groups = sorted({g for e in scen for g in e["groups"]})
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    width = 0.8 / max(1, len(groups))
    xs = np.arange(len(scen))
    palette = [ACCENT, BLUE, "#5c6b7a", "#8a2a2a", "#2a8a5a"]
    for k, g in enumerate(groups):
        vals = [e["shapley"].get(g, 0.0) for e in scen]
        ax.bar(xs + k * width, vals, width=width, color=palette[k % len(palette)], label=g.replace("_", " "))
    ax.set_xticks(xs + 0.4 - width / 2)
    ax.set_xticklabels([e["scenario"] for e in scen], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Shapley value of post shock drawdown", fontsize=9)
    ax.axhline(0, color=INK, lw=0.8)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig_attribution.png"), dpi=200); plt.close(fig)


def main(run_dir, out=None):
    out = out or run_dir
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(run_dir, "artefacts.json")) as f:
        art = json.load(f)
    with open(os.path.join(run_dir, "three.json")) as f:
        three = json.load(f)
    fig_market(three, out)
    fig_inversion(art, out)
    fig_gap_matrix(art, out)
    fig_dose(art, out)
    fig_frontier(art, out)
    fig_attribution(art, out)
    print(f"figures written to {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
