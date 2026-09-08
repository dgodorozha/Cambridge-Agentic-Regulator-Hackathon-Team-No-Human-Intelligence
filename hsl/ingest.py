"""Data desk: bring observed data to the sandbox without letting it break
the sandbox's guarantees.

Every dataset, whether uploaded or fetched by a connector, passes one
quarantine (chapter 10 of Security Engineering, boundaries): size and type
limits, text only, a schema check, a spreadsheet formula injection check,
a personal identifier scan that refuses rather than redacts, a
classification with a no write down rule, and a provenance record with the
sha256 of the bytes. Nothing is stored before it passes.

Three uses follow, each a modest claim:

  anchoring        the observed return distribution against the battery's
                   quiet family (volatility, kurtosis, volatility
                   clustering, drawdown, largest move), reported as ratios
                   with a band; this is the anchoring check of the ICAIF
                   paper applied to a supervisor's own data
  empirical family held out scenarios whose shock and volatility are the
                   observed ones, so the battery is stressed by a shock the
                   market has actually produced
  observed window  where per participant order flow is supplied, the
                   sentinels run on it as they would on a synthetic market;
                   with no ground truth the report is counts and shares
                   only, and per participant output is withheld below the
                   query set size (chapter 11, inference control)
"""

import csv
import hashlib
import io
import json
import os
import re

import numpy as np

from .security import classify, pii_scan, sanitize_cell, looks_like_formula

MAX_ROWS = 250000
MAX_DATASETS = 20          # datasets held for the next plan; oldest are dropped first
ALLOWED_EXT = {".csv", ".json"}
K_ANON = 5


def _log_returns(prices):
    p = np.asarray(prices, dtype=float)
    p = p[np.isfinite(p) & (p > 0)]
    return np.diff(np.log(p)) if len(p) > 1 else np.array([])


def quarantine(filename, content, uploader="", classification="public", max_bytes=25 * 1024 * 1024):
    """Validate bytes into a dataset record or a refusal. Returns a dict
    with `ok`; on success `rows` (list of dicts), `columns`, `sha256`, the
    provenance and the classification."""
    name = (filename or "").strip()
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    rec = {"name": name, "uploader": uploader, "classification": classification, "ok": False}
    cls = classify(classification)
    if not cls["allowed"]:
        return dict(rec, reason=f"classification '{classification}' refused: {cls['note']}")
    if ext not in ALLOWED_EXT:
        return dict(rec, reason="only CSV or JSON files are accepted")
    if len(content) > max_bytes:
        return dict(rec, reason=f"file exceeds {max_bytes // (1024 * 1024)} MB")
    if b"\x00" in content[:4096]:
        return dict(rec, reason="binary content refused")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dict(rec, reason="file is not UTF 8 text")
    hits = pii_scan(text)
    if hits:
        return dict(rec, reason="personal identifiers found (" + ", ".join(f"{k} {v}" for k, v in hits.items())
                    + "); personal data is refused, not redacted")
    try:
        if ext == ".json":
            data = json.loads(text)
            rows = data if isinstance(data, list) else data.get("rows") or data.get("data")
            if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
                return dict(rec, reason="JSON must be a list of row objects or {rows: [...]}")
        else:
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
    except Exception as e:  # noqa: BLE001
        return dict(rec, reason=f"could not parse: {str(e)[:120]}")
    if not rows:
        return dict(rec, reason="no rows")
    if len(rows) > MAX_ROWS:
        return dict(rec, reason=f"more than {MAX_ROWS} rows")
    cols = [c.strip().lower() for c in rows[0].keys() if c is not None]
    rows = [{(k.strip().lower() if k else k): v for k, v in r.items()} for r in rows]
    formula = sum(1 for r in rows[:5000] for v in r.values() if isinstance(v, str) and looks_like_formula(v))
    if formula:
        return dict(rec, reason=f"{formula} cells begin with a formula character; refused (spreadsheet injection)")
    tcol = next((c for c in ("timestamp", "time", "date", "step", "t") if c in cols), None)
    pcol = next((c for c in ("price", "close", "px_last", "last", "value") if c in cols), None)
    rcol = "return" if "return" in cols else None
    if tcol is None or (pcol is None and rcol is None):
        return dict(rec, reason="schema: need a timestamp or step column and a price (or return) column; optional "
                                "participant and flow columns")
    part = next((c for c in ("participant", "participant_id", "member", "agent", "firm_id") if c in cols), None)
    flow = next((c for c in ("flow", "net_flow", "order_flow", "signed_volume", "qty") if c in cols), None)
    # optional labels for backtesting: a per row event marker (a stress episode
    # is in progress) and a per participant label (a known destabilising
    # participant, for example from an enforcement finding)
    event = next((c for c in ("event", "episode", "stress", "incident") if c in cols), None)
    label = next((c for c in ("label", "destabilising", "destabilizing", "flagged", "sanctioned") if c in cols), None)
    # optional per participant attribute: the vendor or model provider each
    # participant trades on, so a vendor split can be observed, not inferred
    vendor = next((c for c in ("vendor", "provider", "model_provider", "model", "platform") if c in cols), None)
    sha = hashlib.sha256(content).hexdigest()
    return dict(rec, ok=True, rows=rows, columns=cols, n_rows=len(rows), sha256=sha, size=len(content),
                schema={"time": tcol, "price": pcol, "return": rcol, "participant": part, "flow": flow,
                        "event": event, "label": label, "vendor": vendor},
                packable=cls["packable"], provenance={"uploaded_by": uploader, "sha256": sha,
                                                      "bytes": len(content), "classification": classification})


def price_series(ds):
    s = ds["schema"]
    rows = ds["rows"]
    if s["participant"]:
        # one price per timestamp: take the first row of each timestamp
        seen, prices = set(), []
        for r in rows:
            t = r.get(s["time"])
            if t in seen:
                continue
            seen.add(t)
            try:
                prices.append(float(r.get(s["price"])))
            except (TypeError, ValueError):
                continue
        return np.asarray(prices, dtype=float)
    if s["price"]:
        out = []
        for r in rows:
            try:
                out.append(float(r.get(s["price"])))
            except (TypeError, ValueError):
                continue
        return np.asarray(out, dtype=float)
    rets = []
    for r in rows:
        try:
            rets.append(float(r.get(s["return"])))
        except (TypeError, ValueError):
            continue
    return np.exp(np.cumsum(np.asarray(rets, dtype=float)))


def stats(prices):
    r = _log_returns(prices)
    if len(r) < 20:
        return None
    p = np.asarray(prices, dtype=float)
    peak = np.maximum.accumulate(p)
    dd = float(np.max((peak - p) / peak))
    ac1 = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if r.std() > 0 else 0.0
    a = np.abs(r)
    vac = float(np.corrcoef(a[:-1], a[1:])[0, 1]) if a.std() > 0 else 0.0
    kurt = float(((r - r.mean()) ** 4).mean() / (r.var() ** 2)) if r.var() > 0 else 0.0
    return {"n": int(len(r)), "vol": float(r.std()), "kurtosis": kurt, "autocorr_1": ac1,
            "abs_autocorr_1": vac, "max_drawdown": dd, "largest_drop": float(-r.min()),
            "largest_rise": float(r.max())}


def anchoring(ds, battery_quiet):
    """Observed statistics against the battery's quiet family; ratios in
    [0.5, 2] count as within band."""
    obs = stats(price_series(ds))
    if obs is None:
        return {"ok": False, "reason": "fewer than 20 returns"}
    out = {"ok": True, "observed": obs, "battery_quiet": battery_quiet, "ratios": {}, "within_band": {}}
    for k in ("vol", "kurtosis", "abs_autocorr_1", "max_drawdown"):
        b = battery_quiet.get(k)
        if b is None or b == 0 or obs[k] is None:
            continue
        ratio = float(obs[k] / b) if b > 0 else None
        out["ratios"][k] = ratio
        out["within_band"][k] = bool(ratio is not None and 0.5 <= ratio <= 2.0)
    out["n_within"] = int(sum(out["within_band"].values()))
    out["n_compared"] = int(len(out["within_band"]))
    return out


def empirical_family(ds, n=2, base=None):
    """Held out scenarios whose shock is the largest observed drop and whose
    noise matches the observed volatility, capped to the planner's bounds."""
    from .simulator import ScenarioSpec
    st = stats(price_series(ds))
    if st is None:
        return []
    shock = float(min(0.10, max(0.01, st["largest_drop"])))
    sigma = float(min(0.03, max(0.002, st["vol"])))
    specs = []
    tag = ds.get("sha256", "")[:6] or "obs"
    for s in range(n):
        specs.append(ScenarioSpec(name=f"empirical_{tag}_{s}", family="empirical", holdout=True,
                                  vendor_shares=(0.30, 0.15), vendor_rhos=(0.85, 0.30),
                                  shock_size=shock, sigma=sigma, seed=1200 + s))
    return specs


class ObservedResult:
    """Minimal result for the sentinels: flows, returns, prices."""

    def __init__(self, flows, returns):
        self.flows = flows
        self.returns = returns
        self.prices = np.cumsum(returns)
        n = flows.shape[1]
        self.agent_cluster = np.full(n, -1)
        self.destabilising = np.zeros(n, dtype=bool)


def observed_window(ds, sentinel_classes, k_anon=K_ANON):
    """Run the sentinels on observed per participant flows. Returns counts
    and shares only; participant identifiers are never emitted, and a
    window with fewer than `k_anon` participants returns nothing per
    participant at all."""
    s = ds["schema"]
    if not (s["participant"] and s["flow"]):
        return {"ok": False, "reason": "no participant and flow columns"}
    times, parts = [], []
    for r in ds["rows"]:
        t, p = r.get(s["time"]), r.get(s["participant"])
        if t not in times:
            times.append(t)
        if p not in parts:
            parts.append(p)
    if len(parts) < k_anon:
        return {"ok": False, "reason": f"fewer than {k_anon} participants; withheld (query set size)"}
    ti = {t: i for i, t in enumerate(times)}
    pi = {p: i for i, p in enumerate(parts)}
    F = np.zeros((len(times), len(parts)))
    price = np.full(len(times), np.nan)
    for r in ds["rows"]:
        try:
            F[ti[r[s["time"]]], pi[r[s["participant"]]]] += float(r.get(s["flow"]) or 0.0)
            if s["price"] and np.isnan(price[ti[r[s["time"]]]]):
                price[ti[r[s["time"]]]] = float(r.get(s["price"]))
        except (TypeError, ValueError, KeyError):
            continue
    if len(times) < 80:
        return {"ok": False, "reason": "fewer than 80 time steps"}
    if s["price"] and np.isfinite(price).sum() > 10:
        price = np.where(np.isfinite(price), price, np.nan)
        idx = np.arange(len(price))
        price = np.interp(idx, idx[np.isfinite(price)], price[np.isfinite(price)])
        returns = np.concatenate([[0.0], np.diff(np.log(price))])
    else:
        returns = F.mean(axis=1) * 0.01
    scale = F.std() if F.std() > 0 else 1.0
    res = ObservedResult(F / scale, returns)
    out = {"ok": True, "n_participants": len(parts), "n_steps": len(times), "k_anon": k_anon, "sentinels": {}}
    for S in sentinel_classes:
        o = S().run(res)
        n_flag = int(o["flags"].sum())
        out["sentinels"][S.name] = {"alerted": o["first_alert"] is not None, "first_alert": o["first_alert"],
                                    "peak_stress": float(np.max(o["stress_index"])),
                                    "n_flagged": n_flag if n_flag >= k_anon or n_flag == 0 else f"fewer than {k_anon}",
                                    "share_flagged": float(n_flag / len(parts))}
    return out


def dataset_summary(ds):
    """What enters the artefacts and the evidence pack: never the rows of a
    restricted dataset."""
    return {"name": ds["name"], "classification": ds["classification"], "sha256": ds["sha256"],
            "n_rows": ds["n_rows"], "bytes": ds["size"], "columns": ds["columns"], "schema": ds["schema"],
            "packable": ds["packable"], "provenance": ds["provenance"], "source": ds.get("source", "upload")}


def export_csv(rows, columns):
    """CSV export with formula injection defence."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([sanitize_cell(r.get(c, "")) for c in columns])
    return buf.getvalue()


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def persist_datasets(datasets, run_dir):
    """Write each quarantined dataset to `<run_dir>/data/` as a sanitised
    CSV (formula defence applied) and an index with the classification and
    the sha256 of the original bytes. Rows of every accepted dataset live
    here, in the run directory, whatever the classification; the evidence
    pack takes only those whose classification is packable (no write down).
    Returns the index."""
    d = os.path.join(run_dir, "data")
    os.makedirs(d, exist_ok=True)
    index = []
    for ds in datasets or []:
        base = _SAFE.sub("_", os.path.basename(ds["name"]))[:80] or "dataset"
        if not base.lower().endswith(".csv"):
            base = base.rsplit(".", 1)[0] + ".csv"
        fname = f"{ds['sha256'][:16]}_{base}"
        with open(os.path.join(d, fname), "w", newline="") as f:
            f.write(export_csv(ds["rows"], ds["columns"]))
        index.append({"file": fname, "name": ds["name"], "classification": ds["classification"],
                      "packable": bool(ds["packable"]), "sha256": ds["sha256"], "n_rows": ds["n_rows"],
                      "source": ds.get("source", "upload")})
    with open(os.path.join(d, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
    return index


def keep_recent(datasets, limit=MAX_DATASETS):
    """Bound the datasets held in memory: the most recent `limit`."""
    return list(datasets)[-limit:]


def flow_matrix_with_meta(ds):
    """(times by participants) aggregate flow matrix, the price per time and
    the ordered time keys; (None, None, None) without participant flows."""
    s = ds["schema"]
    if not (s.get("participant") and s.get("flow")):
        return None, None, None
    times, parts = {}, {}
    for r in ds["rows"]:
        t, p = r.get(s["time"]), r.get(s["participant"])
        if t not in times:
            times[t] = len(times)
        if p not in parts:
            parts[p] = len(parts)
    F = np.zeros((len(times), len(parts)))
    price = np.full(len(times), np.nan)
    for r in ds["rows"]:
        try:
            F[times[r[s["time"]]], parts[r[s["participant"]]]] += float(r.get(s["flow"]) or 0.0)
            if s.get("price") and np.isnan(price[times[r[s["time"]]]]):
                price[times[r[s["time"]]]] = float(r.get(s["price"]))
        except (TypeError, ValueError, KeyError):
            continue
    return F, price, list(times)


def participant_vendors(ds):
    """Vendor or provider per participant (by column position), from the
    vendor column; {} without one. Blank, none or unknown count as no vendor."""
    s = ds["schema"]
    if not (s.get("participant") and s.get("vendor")):
        return {}
    order, vend = {}, {}
    for r in ds["rows"]:
        pid = r.get(s["participant"])
        if pid not in order:
            order[pid] = len(order)
        v = str(r.get(s["vendor"]) or "").strip()
        if v and v.lower() not in ("none", "null", "unknown", "n/a", "na", "-") and order[pid] not in vend:
            vend[order[pid]] = v
    return vend
