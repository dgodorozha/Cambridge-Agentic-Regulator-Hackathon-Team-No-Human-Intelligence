"""Evidence pack: everything a second authority needs to replay a run.

The pack is a zip of the run directory (artefacts, per scenario rows,
autonomy scores, network frames, battery, ledger, briefing in markdown and
HTML, approvals) plus a manifest listing the SHA-256 of every file and a
VERIFY.md explaining how to check the ledger and reproduce the numbers.
"""

import datetime
import hashlib
import json
import os
import zipfile

PACK_FILES = ["artefacts.json", "rows.json", "aut.json", "net.json",
              "battery.json", "ledger.jsonl", "briefing.md", "briefing.html",
              "approvals.json", "meta.json", "critic.json", "atrs_record.md", "atrs_record.json",
              "security_framework.md", "exchange_record.json"]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


VERIFY_MD = """# Verifying this evidence pack

1. Check the manifest: every file's SHA-256 is listed in `manifest.json`.
   `python -c "import json,hashlib,sys; m=json.load(open('manifest.json'));
   [print(f, hashlib.sha256(open(f,'rb').read()).hexdigest()==h) for f,h in m['files'].items()]"`
2. Replay the ledger chain: `python -m hsl.ledger verify ledger.jsonl`.
   Set `HSL_SECRET` to the server secret to also check the signatures.
3. Reproduce the numbers: the battery is in `battery.json` with every seed.
   `python -m hsl.orchestrator --battery battery.json --approve-battery
   --approve-briefing --approver "<name>" --outdir replay` recomputes
   `artefacts.json`; the sentinel and rule figures should match to the
   printed precision, and the `code_fingerprint` in `provenance` should
   match the code you run.
4. The briefing was drafted only from `artefacts.json`; `critic.json` lists
   the checks that passed before release, including the vetting of every
   number in the briefing against the artefacts.
"""


def build_pack(run_dir, out_path=None):
    out_path = out_path or os.path.join(run_dir, "evidence_pack.zip")
    files = {}
    for name in PACK_FILES:
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            files[name] = _sha(p)
    # datasets: the index always; rows only where the classification is
    # packable (public or synthetic); licensed or pseudonymised rows stay in
    # the run directory (no write down)
    idx_path = os.path.join(run_dir, "data", "index.json")
    if os.path.isfile(idx_path):
        files["data/index.json"] = _sha(idx_path)
        with open(idx_path) as f:
            for entry in json.load(f):
                p = os.path.join(run_dir, "data", os.path.basename(entry["file"]))
                if entry.get("packable") and os.path.isfile(p):
                    files["data/" + os.path.basename(entry["file"])] = _sha(p)
    manifest = {"built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "run_dir": os.path.basename(os.path.abspath(run_dir)),
                "files": files}
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(os.path.join(run_dir, name), name)
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("VERIFY.md", VERIFY_MD)
    return out_path, manifest
