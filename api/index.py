"""Vercel entry point: the terminal's Flask server as a WSGI app.

Vercel runs Python as serverless functions. The terminal serves fine this way, but a run
is a background computation that must survive across the polling requests that follow it,
which serverless does not promise: instances are recycled, and /tmp is per instance. Keep
the demonstration profile on (about twenty seconds a run) and expect a run to be lost on a
cold start. For a durable deployment use the Dockerfile (Render, Railway, Fly): see DEPLOY.md.
"""

import os
import sys

os.environ.setdefault("HSL_ASSURANCE", "demo")
os.environ.setdefault("HSL_DEV_MODE", "on")
os.environ.setdefault("HSL_RUNS_DIR", "/tmp/hsl_runs")
os.environ.setdefault("HSL_HOST", "0.0.0.0")
os.environ.setdefault("HSL_AUTH_MODE", "open")
os.environ.setdefault("HSL_REGISTER", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_data", "register.csv"))
if not os.environ.get("HSL_SECRET"):
    os.environ["HSL_SECRET"] = "set-HSL_SECRET-in-the-vercel-project-settings"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dash_app import server as app  # noqa: E402  (Vercel looks for `app`)
