"""Paths, tunables, and the environment check.

Everything the pipeline needs to locate lives here so a broken assumption is
fixed in one place. Nothing outside the standard library is imported anywhere
in this project -- see check_environment() for why that matters.
"""

import os
import shutil
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)

# Queue root. One subdirectory per disc, plus the two global files below.
ROOT = Path(os.environ.get("DISC_PIPELINE_ROOT", "~/Movies/Rips")).expanduser()

LEDGER = ROOT / "ledger.jsonl"
OVERRIDES = ROOT / "overrides.json"

# Where finished media ends up. Movies with extras ship as a folder; a feature
# with no kept extras ships as a bare file.
NAS_MOVIES = Path("/Volumes/Media/Movies")
NAS_TV = Path("/Volumes/Media/TV Shows")

MAKEMKVCON = Path("/Applications/MakeMKV.app/Contents/MacOS/makemkvcon")

# Shortest title worth ripping.
#
# Four minutes. The policy is that extras under five minutes aren't wanted, so
# there is no value in ripping them only to reject them at the review gate --
# but a hard floor at exactly 300s clips things that are five minutes in
# spirit. On Warm Bodies it dropped 00557.m2ts at 4:43, sitting between two
# siblings of the same featurette block that were kept (00556 at 5:07, 00558
# at 12:38). 240s buys that margin back.
#
# Raise it if too much junk starts reaching the review gate.
MIN_TITLE_LENGTH = 240

# Free space required before a rip: MakeMKV's own size estimate plus headroom.
SPACE_HEADROOM_BYTES = 10 * 1024**3

# Session polling interval, in seconds.
POLL_INTERVAL = 30

# A disc is a feature-length candidate if it runs at least this long.
FEATURE_MIN_SECONDS = 60 * 60

# Decoy detection. Titles within this fraction of the longest title that also
# draw on the same segment pool form a cluster; more than the threshold means
# the disc is using playlist obfuscation and cannot be triaged on metadata.
DECOY_DURATION_TOLERANCE = 0.10
DECOY_CLUSTER_THRESHOLD = 6

# Cluster members must draw on the same pool of stream segments as the longest
# title. This is what keeps a TV season disc -- several similar-length titles
# with disjoint segments -- from reading as an obfuscated movie.
DECOY_SEGMENT_OVERLAP = 0.5


def check_environment():
    """Fail loudly and specifically rather than mysteriously.

    launchd does not inherit your shell's PATH, so a missing tool here shows up
    as a stage that silently never advances. Every entry point calls this first.
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
