# Deployment guide for an authority

HSL is a single Python process. It needs no database, no external data and
no outbound network unless a model is enabled. This guide covers a
production posture for a central bank or securities regulator.

## Topology

```
analyst browser ── SSO / reverse proxy (TLS, identity header) ── HSL (127.0.0.1:8050)
                                                                   │
                                                                   └── runs/  (persistent volume)
```

- HSL binds to `127.0.0.1` by default. Put it behind the authority's reverse
  proxy (nginx, Apache, an API gateway) that terminates TLS and performs
  single sign on. Set `HSL_AUTH_MODE=header` and `HSL_USER_HEADER` to the
  header the proxy injects (for example `X-Remote-User`). The proxy must
  strip any incoming value of that header from clients; `deploy/nginx.conf`
  shows the pattern.
- Only the proxy may reach port 8050. In compose the port is not published.
- `runs/` is the only writable state. Mount it on a persistent volume with
  backups; ledgers there are signed and append only.
- Set `HSL_SECRET` from the authority's secret store. If it is lost, past
  ledgers still verify as chains but their signatures cannot be checked.

## Configuration

See `.env.example`. The relevant settings:

| Variable | Production value |
|---|---|
| `HSL_HOST` | `127.0.0.1` (or `0.0.0.0` inside a container that publishes no port) |
| `HSL_AUTH_MODE` | `header` |
| `HSL_USER_HEADER` | the SSO identity header set by the proxy |
| `HSL_APPROVERS` | comma separated identities allowed to approve gates |
| `HSL_FOUR_EYES` | `1` |
| `HSL_SECRET` | a 64 hex character secret from the secret store |
| `HSL_RUNS_DIR` | a persistent, backed up directory |
| `HSL_LLM` | `off` unless the authority has approved outbound model calls |
| `ANTHROPIC_API_KEY` | only with `HSL_LLM=auto`; via the secret store |

## Running

```
pip install -r requirements.txt
gunicorn -w 1 --threads 8 -b 127.0.0.1:8050 dash_app:server
```

Use one worker. A run lives in process memory while it streams; the
registry on disk is shared, but the live stream belongs to the worker that
started it. Multiple analysts can view; one run is active at a time. For
container deployment: `docker compose -f deploy/docker-compose.yml up`.

Health: `GET /healthz` returns `{"ok": true, ...}`. Version and effective
configuration (no secrets): `GET /version`.

## Operations

- **Retention.** Keep `runs/` for as long as the authority's records policy
  requires for supervisory decisions. Each run is self contained; delete a
  directory to delete a run.
- **Replay.** `python -m hsl.ledger verify runs/<id>/ledger.jsonl` (with
  `HSL_SECRET` set) checks the chain and signatures. `python -m
  hsl.orchestrator --battery runs/<id>/battery.json --approve-battery
  --approve-briefing --approver "<name>" --outdir replay` recomputes the
  artefacts; compare `code_fingerprint` in `provenance`.
- **Upgrades.** A code change changes `code_fingerprint`. Rerun the battery
  after an upgrade before quoting numbers; the fingerprint in the evidence
  pack tells a reviewer which code produced which figures.
- **Air gap.** Nothing in the default configuration leaves the host. All
  charting libraries and fonts are vendored. With `HSL_LLM=off` there are no
  outbound calls at all.
- **Logs.** The application prints to stdout; the supervisory record is the
  ledger, not the process log.

## Sizing

A full battery (27 scenarios, four sentinels, three rules, bootstrap 400)
takes about two to three minutes on one CPU core and under 1 GB of memory.
The first plan trains the RL population (about 20 s) once per process.
