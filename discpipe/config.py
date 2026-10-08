"""Paths, settings and the environment check."""

import os
import shutil
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)

ROOT = Path(os.environ.get("DISC_PIPELINE_ROOT", "~/Movies/Rips")).expanduser()

LEDGER = ROOT / "ledger.jsonl"
OVERRIDES = ROOT / "overrides.json"

NAS_ROOT = Path(os.environ.get("DISC_PIPELINE_NAS", "/Volumes/Media")).expanduser()
NAS_MOVIES = NAS_ROOT / "Movies"
NAS_TV = NAS_ROOT / "TV Shows"

MAKEMKVCON = Path("/Applications/MakeMKV.app/Contents/MacOS/makemkvcon")

MIN_TITLE_LENGTH = 240

SPACE_HEADROOM_BYTES = 10 * 1000**3

POLL_INTERVAL = 30

FEATURE_MIN_SECONDS = 60 * 60

DECOY_DURATION_TOLERANCE = 0.10
DECOY_CLUSTER_THRESHOLD = 6

# A TV season disc has several titles of similar length, and each title uses
# different segments. Because of this overlap, triage does not identify such a
# disc as a decoy disc.
DECOY_SEGMENT_OVERLAP = 0.5


def check_environment():
    """launchd does not give a job the PATH of your shell.

    If a tool is not on the PATH of the job, the stage does not advance and
    shows no error.
    """
    problems = []

    if sys.version_info < MIN_PYTHON:
        have = ".".join(str(n) for n in sys.version_info[:3])
        want = ".".join(str(n) for n in MIN_PYTHON)
        problems.append(f"Python {want}+ required, running {have} ({sys.executable})")

    if not MAKEMKVCON.exists():
        problems.append(f"makemkvcon not found at {MAKEMKVCON}")

    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            problems.append(f"{tool} not on PATH (PATH={os.environ.get('PATH', '')})")

    if problems:
        raise EnvironmentError("; ".join(problems))


def ensure_root():
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT
