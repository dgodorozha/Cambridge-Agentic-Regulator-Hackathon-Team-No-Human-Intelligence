# Deploying the Herding Scenario Lab

## Running a battery: use the demonstration identities

The live prototype at https://hsl-terminal.onrender.com, and any local copy started with `HSL_DEV_MODE=on`, accept two built in identities, so no account and no register entry is needed. On the RUN page enter exactly:

| Field | Value |
|---|---|
| Prepared by | `Developer1` |
| Preparer's function | `Developer1` |
| Approver at the gates | `Developer2` |
| Approver's function | `Developer2` |

Then click **Plan**, then **Gate 1: approve battery**, wait for the battery and the critic to finish (a few minutes on the demonstration profile; the phase line under the command bar shows progress), and click **Gate 2: release briefing**, or **Refuse** with a reason. The preparer and the approver must differ (four eyes). Any other names are checked against the register of regulated persons in `sample_data/register.csv`, which also accepts the four team members listed there with their recorded functions (for example approver `Rajib Ahmed`, function `SMF24`); names not on it are refused, by design.

## GitHub

Drag the contents of the zip (not the zip itself) into a new GitHub repository, or run
`git init && git add . && git commit -m "HSL terminal" && git push`. The repository root holds
`dash_app.py`, the `hsl/` package, `assets/`, `sample_data/`, `requirements.txt`, the `Dockerfile`
and `render.yaml`.

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
