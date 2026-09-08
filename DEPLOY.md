# Deploying the Herding Scenario Lab

## GitHub

Drag the contents of the zip (not the zip itself) into a new GitHub repository, or run
`git init && git add . && git commit -m "HSL terminal" && git push`. The repository root holds
`dash_app.py`, the `hsl/` package, `assets/`, `sample_data/`, `requirements.txt`, the `Dockerfile`,
`vercel.json` with `api/index.py`, and `render.yaml`.

## Vercel (auto deploy from GitHub)

Import the repository in Vercel; the framework preset is "Other". `vercel.json` routes every
path to `api/index.py`, which exposes the terminal's Flask server as a WSGI app. Set
`HSL_SECRET` in the project's environment variables (a 64 hex character value; the ledger is
signed with it). Every push to the default branch redeploys.

What to expect on Vercel: the terminal loads and every page works, and short runs complete
on the demonstration profile (`HSL_ASSURANCE=demo`, about twenty seconds). A run is a
background computation kept in the memory of one instance and polled by later requests;
serverless platforms do not promise that the same instance answers, and they recycle
instances, so a run can be lost mid way or after a cold start, and the run registry lives in
the instance's `/tmp`. Vercel is fine for showing the interface; it is not a place to certify a
tool. Use it with Fluid Compute enabled and the function `maxDuration` at 300 seconds.

## A durable host: Render, Railway or Fly (Docker)

The `Dockerfile` runs the terminal as one long lived process, which is what a run needs.
`render.yaml` is a one click Render blueprint: connect the repository, and Render builds the
image and redeploys on every push, with a generated `HSL_SECRET`. Mount a disk at
`/app/runs` if the run registry should survive restarts. Railway and Fly read the same
Dockerfile.

## Environment

| Variable | Purpose |
|---|---|
| `HSL_SECRET` | ledger signing key; required for a persistent, verifiable ledger |
| `HSL_ASSURANCE` | `demo` (twenty seconds), `light`, or `full` |
| `HSL_DEV_MODE` | `on` accepts Developer1 and Developer2 at the gates |
| `HSL_REGISTER` | register of regulated persons the approver is checked against |
| `HSL_AUTH_MODE` | `open` (names typed) or `header` (identities from an authenticating proxy) |
| `HSL_RUNS_DIR` | where runs are written |
