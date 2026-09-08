"""Herding Scenario Lab (HSL) core library.

Version 2 adds a signed ledger, run provenance, uncertainty on every
headline metric, held out and adversarial scenario families, a no lookahead
intervention harness, an autonomy gate with leave one out validation, an
expanded critic and an evidence pack exporter. Version 3 adds the herding
versus noise sentinels, LLM persona traders by policy distillation, a
colluding ignition family, alternative market generators, conformal
certification with a false alert guarantee, Shapley attribution, a truth
dependence audit, a concentration dose response, a jurisdiction rule
library, a supervisory cost frontier and a red team (adversarial evasion
search and an injection suite). The simulation dynamics of versions 1 and 2
are unchanged, so earlier batteries still reproduce their numbers.
"""

import hashlib
import os
import platform
import sys

__version__ = "3.9.9"


def code_fingerprint() -> str:
    """SHA-256 over the source of every module in this package, in sorted
    order. Recorded in artefacts so a run can be tied to the exact code."""
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for name in sorted(os.listdir(here)):
        if name.endswith(".py"):
            with open(os.path.join(here, name), "rb") as f:
                h.update(name.encode())
                h.update(f.read())
    return h.hexdigest()


def provenance() -> dict:
    import numpy
    import scipy
    return {
        "hsl_version": __version__,
        "code_fingerprint": code_fingerprint(),
        "python": sys.version.split()[0],
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
    }
