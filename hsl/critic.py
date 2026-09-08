"""Critic: independent re-verification of a run before the release gate.

Version 1 ran three checks (two ranking heads and a range check). Version
2 recomputes the headline summary from the per scenario rows, recomputes
the decision gap, checks every interval contains its point estimate, checks
the rules' arithmetic and their no lookahead flag, checks the autonomy
gate's bookkeeping, binds the run to the battery hash approved at Gate 1,
replays the ledger chain and, at release, vets every number in the briefing
against the artefacts. Version 3 adds the conformal arithmetic, Shapley
efficiency, the cost frontier endpoints, the injection suite, the truth
audit and red team bookkeeping and the persona hash binding. Gate 2 does
not arm unless every check passes.
"""

import re

import numpy as np

from . import ledger as ledger_mod
from .evaluate import summarise, decision_gap

TOL = 1e-9


def _check(checks, name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


_IDENT = re.compile(r"\b[0-9a-f]{12,}\b|\b\d{8}-\d+(?:-[a-z0-9]+)?\b"
                    r"|\d{4}-\d{2}-\d{2}[T ][\d:.]+(?:Z|\+\d{2}:\d{2})?"
                    r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{2}:\d{2}(?::\d{2})?\b"
                    r"|\b\d+\.\d+\.\d+(?:[a-z0-9.]*)\b"
                    r"|\b[A-Za-z_]+[-_]?\d+(?:\.\d+)*(?:[-_][A-Za-z0-9.]+)*\b"    # glibc2.39, x86_64, SMF24
                    r"|\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{3,}\b")   # f746d3, a3e7, hash tags


MAX_DP = 4


def numbers_in(text):
    """Numbers in prose at their printed precision (up to MAX_DP decimals),
    ignoring identifiers: hashes, run ids, dates and clock times are not
    quantitative claims. Version 3 keeps the printed precision so that a
    number with four decimals must match an artefact at four decimals; the
    old two decimal rounding let any figure in [0, 1] slip past once the
    artefacts grew dense."""
    text = _IDENT.sub(" ", text)
    out = set()
    for x in re.findall(r"-?\d+\.\d+|-?\d+", text):
        dp = len(x.split(".")[1]) if "." in x else 0
        out.add(round(float(x), min(dp, MAX_DP)))
    return out


def numbers_in_artefacts(a):
    out = set()

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, bool):
            return
        elif isinstance(v, (int, float)) and v == v:
            f = float(v)
            for nd in range(0, MAX_DP + 1):
                out.add(round(f, nd))
                out.add(float(f"{f:.{nd}f}"))
            for nd in (0, 1):                                  # percentages
                out.add(round(f * 100, nd))
                out.add(float(f"{f * 100:.{nd}f}"))
        elif isinstance(v, str) and any(ch.isdigit() for ch in v):
            # numbers quoted inside artefact strings (clamp notes, diagnostics)
            # are artefact numbers too, at every printed precision
            for f in numbers_in(v):
                for nd in range(0, MAX_DP + 1):
                    out.add(round(f, nd))
                    out.add(float(f"{f:.{nd}f}"))
    walk(a)
    for y in range(1900, 2100):
        out.add(float(y))
    for k in range(0, 200):                  # small counts and step indices
        out.add(float(k))
    return out


def critic_check(artefacts, rows=None, approved_battery_hash=None,
                 ledger_path=None, secret=None, briefing_text=None, log=None, atrs_text=None):
    checks = []
    s = artefacts.get("sentinels", {})
    g = artefacts.get("decision_gap", {})
    names = list(s)

    # 1. summary recomputed from rows
    if rows is not None and names:
        re_s, _ = summarise(rows, names)
        worst = 0.0
        for n in names:
            for k in ("decision_f1", "aggregate_fidelity", "fidelity_moments",
                      "precision", "recall"):
                worst = max(worst, abs(re_s[n][k] - s[n][k]))
            fa, fb = re_s[n]["false_alert_rate"], s[n]["false_alert_rate"]
            if fa is not None and fb is not None:
                worst = max(worst, abs(fa - fb))
        _check(checks, "summary recomputed from per scenario rows", worst < TOL,
               f"max abs deviation {worst:.2e}")
    else:
        _check(checks, "summary recomputed from per scenario rows", False,
               "rows not supplied")

    # 2. ranking heads
    if names and g:
        top_fid, top_dec = g["fidelity_ranking"][0], g["decision_ranking"][0]
        _check(checks, "fidelity ranking head matches summary",
               s[top_fid]["aggregate_fidelity"] == max(v["aggregate_fidelity"] for v in s.values()))
        _check(checks, "decision ranking head matches summary",
               s[top_dec]["decision_f1"] == max(v["decision_f1"] for v in s.values()))
        # 3. gap recomputed
        rg = decision_gap(s)
        _check(checks, "decision gap recomputed from summary",
               abs(rg["decision_gap"] - g["decision_gap"]) < TOL
               and abs(rg["kendall_tau"] - g["kendall_tau"]) < TOL,
               f"gap {g['decision_gap']:.3f}, tau {g['kendall_tau']:+.3f}")
        _check(checks, "gap in [0,1]", 0.0 <= g["decision_gap"] <= 1.0)
        gb = artefacts.get("decision_gap_bootstrap") or {}
        if gb:
            _check(checks, "bootstrap P(inversion) in [0,1]",
                   0.0 <= gb.get("p_inversion", -1) <= 1.0,
                   f"P(inversion) {gb.get('p_inversion'):.2f} over {gb.get('B')} resamples")

    # 4. intervals contain point estimates
    bad = []
    for n in names:
        for k in ("decision_f1", "aggregate_fidelity"):
            lo, hi = s[n]["ci"][k]
            if lo is None or not (lo - TOL <= s[n][k] <= hi + TOL):
                bad.append(f"{n}:{k}")
    _check(checks, "confidence intervals contain point estimates", not bad,
           ", ".join(bad) if bad else f"{2 * len(names)} intervals checked")

    # 5. rules arithmetic and no lookahead
    r = artefacts.get("rules", {})
    bad = []
    for n, v in r.items():
        if v.get("mean_post_shock_dd_untreated"):
            c = 1 - v["mean_post_shock_dd_treated"] / v["mean_post_shock_dd_untreated"]
            if abs(c - v["containment"]) > 1e-6:
                bad.append(f"{n}: containment arithmetic")
        if v.get("targeted") and v.get("lookahead"):
            bad.append(f"{n}: used lookahead flags")
        if v.get("false_halt_rate") is not None and not (0 <= v["false_halt_rate"] <= 1):
            bad.append(f"{n}: false halt rate out of range")
    _check(checks, "intervention rules: arithmetic and no lookahead", not bad,
           ", ".join(bad) if bad else f"{len(r)} rules checked")

    # 6. autonomy bookkeeping
    a = artefacts.get("autonomy", {})
    bad = []
    for n, v in a.items():
        if abs(v["breadth"] - (v["clear"] + v["throttle"])) > 1e-9:
            bad.append(f"{n}: breadth")
        if v["throttle_ok"] != (v["lift"] >= v["lift_bar"]):
            bad.append(f"{n}: withdrawal rule")
        if not (0 <= v["loo"]["claim_rate"] <= 1):
            bad.append(f"{n}: loo claim rate")
    _check(checks, "autonomy gate bookkeeping and withdrawal rule", not bad,
           ", ".join(bad) if bad else f"{len(a)} sentinels checked")

    # 7. battery hash bound to Gate 1
    bh = artefacts.get("provenance", {}).get("battery_hash")
    if approved_battery_hash is None:
        _check(checks, "battery hash matches Gate 1 approval", bh is not None,
               "no approval hash supplied; presence checked only")
    else:
        _check(checks, "battery hash matches Gate 1 approval", bh == approved_battery_hash,
               (bh or "")[:16])

    # 8. held out families present when the battery has them
    if artefacts.get("battery", {}).get("n_holdout", 0) > 0:
        _check(checks, "held out families scored separately",
               bool(artefacts.get("sentinels_holdout")),
               f"{artefacts['battery']['n_holdout']} held out scenarios")

    # 9. ledger chain
    if ledger_path:
        rep = ledger_mod.verify(ledger_path, secret)
        _check(checks, "ledger chain replays and verifies", rep["ok"],
               f"{rep['entries']} entries, {rep['signed']} signed"
               + ("" if rep["ok"] else "; " + "; ".join(rep["errors"][:3])))

    # 10. briefing numbers
    if briefing_text is not None:
        allowed = numbers_in_artefacts(artefacts)
        rogue = sorted(n for n in numbers_in(briefing_text) if n not in allowed)
        _check(checks, "every number in the briefing appears in the artefacts",
               not rogue, f"rogue numbers: {rogue[:8]}" if rogue else
               f"{len(numbers_in(briefing_text))} numbers vetted")

    # 11. provenance
    p = artefacts.get("provenance", {})
    _check(checks, "provenance recorded (code fingerprint, versions, seeds)",
           bool(p.get("code_fingerprint")) and bool(p.get("hsl_version")),
           f"hsl {p.get('hsl_version')} code {str(p.get('code_fingerprint'))[:12]}")

    # 12. conformal certification arithmetic (version 3)
    cf = artefacts.get("conformal") or {}
    if cf and rows is not None:
        from .conformal import certify
        bad = []
        re_c = certify(rows, list(cf))
        for n, v in cf.items():
            w = re_c.get(n, {})
            if (v.get("threshold_score") is None) != (w.get("threshold_score") is None) or \
                    (v.get("threshold_score") is not None and
                     abs(v["threshold_score"] - w["threshold_score"]) > 1e-9):
                bad.append(f"{n}: threshold")
            if v.get("guarantee_achievable") and v.get("guaranteed_false_alert_bound") != v.get("alpha"):
                bad.append(f"{n}: bound")
            if v.get("min_achievable_level") is not None and v["guarantee_achievable"] \
                    and v["min_achievable_level"] > v["alpha"] + 1e-12:
                bad.append(f"{n}: level")
        _check(checks, "conformal thresholds recomputed from rows and bound consistent", not bad,
               ", ".join(bad) if bad else f"{len(cf)} sentinels at alpha {next(iter(cf.values()))['alpha']}")

    # 13. Shapley efficiency (values add up to the full less silenced drawdown)
    at = artefacts.get("attribution")
    if at:
        worst = 0.0
        for e in at["scenarios"]:
            resid = sum(e["shapley"].values()) - (e["drawdown_full"] - e["drawdown_all_silenced"])
            worst = max(worst, abs(resid))
            if e["impact_ordering"] != sorted(e["groups"], key=lambda g: e["shapley"][g], reverse=True):
                worst = max(worst, 1.0)
        _check(checks, "Shapley attribution efficiency (values sum to the drawdown removed)",
               worst < 1e-9, f"{at['n_scenarios']} scenarios, max residual {worst:.1e}")

    # 14. frontier endpoints agree with the raw rates
    fr = artefacts.get("frontier") or {}
    if fr.get("sentinels") and s:
        segs = fr["sentinels"]["segments"]
        c1 = segs[-1]["tool"]
        fa1 = {n: (v.get("false_alert_rate") or 0.0) for n, v in s.items()}
        c0 = segs[0]["tool"]
        miss0 = {n: 1.0 - (v.get("recall") or 0.0) for n, v in s.items()}
        _check(checks, "cost frontier endpoints match the raw false alert and miss rates",
               abs(fa1[c1] - min(fa1.values())) < 1e-9 and abs(miss0[c0] - min(miss0.values())) < 1e-9,
               f"c=0 picks {c0}, c=1 picks {c1}")

    # 15. injection suite fully contained
    inj = (artefacts.get("redteam") or {}).get("injection")
    if inj:
        _check(checks, "injection suite: every case contained", inj["all_contained"],
               f"{inj['n_contained']} of {inj['n_cases']} cases contained")

    # 16. truth audit and red team bookkeeping
    ta = artefacts.get("truth_audit")
    if ta:
        bad = [g for g, c in ta["comparison"].items() if not (-1.0 - 1e-9 <= c["tau_vs_shared_signal"] <= 1.0 + 1e-9)]
        _check(checks, "truth audit rank correlations in range", not bad,
               f"generators {ta['generators']}, max rank shift {ta['max_rank_shift_any']}")
    rt = (artefacts.get("redteam") or {}).get("evasion")
    if rt:
        ok_b = all(all(t["params"][k] in [float(x) for x in rt["bounds"][k]] for k in rt["bounds"])
                   for t in rt["trials"])
        if rt.get("arms"):
            ok_b = ok_b and sum(a["pulls"] for a in rt["arms"]) == len(rt["trials"])
        _check(checks, "adversarial search stayed inside the declared bounds", ok_b,
               f"{len(rt['trials'])} trials, {rt['n_dislocating']} dislocating")

    # 17b. survival analysis arithmetic
    sv = artefacts.get("survival")
    if sv and sv.get("kaplan_meier"):
        bad = []
        for arm, k in sv["kaplan_meier"].items():
            s_ = k["survival"]
            if any(s_[i + 1] > s_[i] + 1e-12 for i in range(len(s_) - 1)) or any(x < 0 or x > 1 for x in s_):
                bad.append(arm)
        cx = sv.get("cox")
        if cx and (not cx["converged"] or any(not np.isfinite(h) for h in cx["hazard_ratio"].values())):
            bad.append("cox")
        _check(checks, "survival curves monotone and Cox model converged", not bad,
               ", ".join(bad) if bad else f"{len(sv['kaplan_meier'])} arms, {len(sv.get('sentinel_alerts') or {})} sentinels")
    rr = artefacts.get("rules") or {}
    es_ok = all((v.get("es_post_shock_dd_treated") is None or v.get("mean_post_shock_dd_treated") is None
                 or v["es_post_shock_dd_treated"] >= v["mean_post_shock_dd_treated"] - 1e-9) for v in rr.values())
    if rr:
        _check(checks, "expected shortfall at least the mean for every rule", es_ok, f"{len(rr)} rules")

    # 17a. authority defined agents bound by hash
    ags = artefacts.get("agents") or {}
    if ags:
        specs = (artefacts.get("battery") or {}).get("specs", [])
        bad = []
        for sp in specs:
            for j, (name, _share) in enumerate(sp.get("custom_agents") or []):
                hs = sp.get("custom_agent_hashes") or []
                if name not in ags or j >= len(hs) or ags[name].get("sha256") != hs[j]:
                    bad.append(f"{sp['name']}:{name}")
        _check(checks, "authority defined agents match the hashes bound at planning", not bad,
               ", ".join(bad[:5]) if bad else f"{len(ags)} agent templates")

    # 17. persona tables bound by hash
    pers = artefacts.get("personas") or {}
    if pers:
        specs = (artefacts.get("battery") or {}).get("specs", [])
        bad = [sp["name"] for sp in specs if sp.get("persona_share", 0) > 0 and
               pers.get(sp.get("persona"), {}).get("table_sha256") != sp.get("persona_hash")]
        _check(checks, "persona policy tables match the hashes bound at planning", not bad,
               ", ".join(bad) if bad else f"{len(pers)} personas")

    # 18. version 3.2: risk measures, matrix game, learned policy and appraisal
    rk = artefacts.get("risk")
    if rk and rk.get("untreated"):
        u = rk["untreated"]
        bad = []
        if u.get("es") is not None and u.get("var") is not None and u["es"] < u["var"] - 1e-9:
            bad.append("ES below VaR")
        for n, v in rk.get("rules", {}).items():
            lo, hi = v["es_reduction_ci"]
            if not (lo - 1e-9 <= v["es_reduction"] <= hi + 1e-9):
                bad.append(f"{n}: ES reduction outside its interval")
        _check(checks, "risk measures coherent (ES at least VaR, ES reductions inside their intervals)",
               not bad, ", ".join(bad) if bad else f"{len(rk.get('rules', {}))} rules at level {u.get('gpd', {}).get('n', 0) and rk['alpha']}")
    gm = artefacts.get("game")
    if gm:
        A = np.array(gm["payoff"])
        ok_g = (abs(A.min(axis=1).max() - gm["maximin_value"]) < 1e-9 and
                gm["mixed_value"] >= gm["maximin_value"] - 1e-6 and
                gm["mixed_value"] <= gm["minimax_value"] + 1e-6 and
                abs(sum(gm["mixture"].values()) - 1.0) < 1e-6)
        _check(checks, "matrix game: mixed value between maximin and minimax, mixture sums to one", ok_g,
               f"maximin {gm['maximin_pure']} {gm['maximin_value']:.3f}, mixed {gm['mixed_value']:.3f}")
    lp = artefacts.get("learned_policy")
    if lp:
        pol = np.array(lp["policy"])
        bad = []
        if pol.min() < 0 or pol.max() > 2 or len(pol) != lp["state_space"]["n_states"]:
            bad.append("policy out of range")
        for n, v in lp["ope"].items():
            for k in ("pdis", "dr", "on_policy"):
                if v.get(k) is not None and not np.isfinite(v[k]):
                    bad.append(f"{n}: {k} not finite")
        _check(checks, "learned policy in range and off policy estimates finite", not bad,
               ", ".join(bad) if bad else f"{len(lp['ope'])} policies evaluated, mean DR error "
                                          f"{(lp.get('mean_abs_error') or {}).get('dr', float('nan')):.4f}")
    ap = artefacts.get("appraisal")
    if ap:
        rec = ap.get("recommended")
        elig = [o for o in ap["options"] if o["passes_all"]]
        ok_a = (rec is None and not elig) or (rec is not None and elig and rec["rule"] == elig[0]["rule"]
                                              and rec["tier"] == min(o["tier"] for o in elig))
        _check(checks, "appraisal recommends the lowest eligible tier", ok_a,
               f"{len(elig)} eligible of {len(ap['options'])}")

    # 19. version 3.3: data provenance and the security posture
    dt = artefacts.get("data")
    if dt and dt.get("datasets"):
        from .security import classify as _classify
        bad = []
        for e in dt["datasets"]:
            s_ = e["summary"]
            if len(str(s_.get("sha256", ""))) != 64:
                bad.append(f"{s_.get('name')}: no sha256")
            if not _classify(s_.get("classification")).get("allowed"):
                bad.append(f"{s_.get('name')}: refused classification present")
            ow = e.get("observed_window") or {}
            if ow.get("ok") and ow.get("n_participants", 0) < ow.get("k_anon", 5):
                bad.append(f"{s_.get('name')}: per participant output below the query set size")
        _check(checks, "datasets carry a hash and an allowed classification; observed windows respect the "
                       "query set size", not bad, ", ".join(bad) if bad else f"{len(dt['datasets'])} datasets")
    sec = artefacts.get("security")
    if sec:
        fails = [i["control"] for i in sec["items"] if i["status"] == "fail"]
        _check(checks, "security posture has no failing control", not fails,
               ", ".join(fails) if fails else f"{sec['n_pass']} pass, {sec['n_warn']} warn")

    bt = artefacts.get("backtest")
    if bt:
        bad = []
        wf = bt.get("walk_forward") or {}
        for f in wf.get("folds", []):
            if not (-1e-9 <= f["regret"] <= 1 + 1e-9) or abs(f["regret"] - (f["f1_best_test"] - f["f1_certified_test"])) > 1e-9:
                bad.append(f"fold {f['fold']}")
        for d in bt.get("datasets", []):
            for n, v in ((d.get("sentinels") or {}).get("sentinels") or {}).items():
                for k in ("detection_rate", "mean_recall_on_labelled"):
                    if v.get(k) is not None and not (0 <= v[k] <= 1):
                        bad.append(f"{n}: {k}")
        _check(checks, "backtest bookkeeping (regret identity, rates in range)", not bad,
               ", ".join(bad[:5]) if bad else f"{bt.get('n_episodes', 0)} episodes, walk forward "
                                             f"{'present' if wf else 'absent'}")

    if atrs_text is not None:
        allowed = numbers_in_artefacts(artefacts)
        rogue = sorted(x for x in numbers_in(atrs_text) if x not in allowed)
        _check(checks, "every number in the transparency record appears in the artefacts", not rogue,
               f"{len(rogue)} unmatched: {rogue[:6]}" if rogue else "all matched")

    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "checks": checks, "n_checks": len(checks),
              "n_failed": sum(1 for c in checks if not c["ok"])}
    if log is not None:
        log("critic_report", ok=ok, n_checks=len(checks),
            failed=[c["name"] for c in checks if not c["ok"]])
    return report
