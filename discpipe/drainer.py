"""Start a drainer session from outside a session.

A stage that moves a disc forward calls start(), so the next stage starts with
no wait for a person. start() does nothing when a session is open, or when
disc-run started the stage.
"""

import os
import subprocess
from pathlib import Path

from . import config, locks, notify

BIN = Path(__file__).resolve().parent.parent / "bin"

UNDER_DRAINER = "DISC_PIPELINE_DRAINER"


def start():
    if os.environ.get(UNDER_DRAINER) or not locks.is_free(locks.SESSION):
        return
    config.ensure_root()
    log = config.ROOT / "watch.log"
    _launch_session(log)
    notify.say(f"Started the drainer; tail {log}")


def _launch_session(log):
    with open(log, "a", encoding="utf-8") as handle:
        subprocess.Popen(
            [str(BIN / "disc-run"), "--watch"],
            stdout=handle, stderr=handle, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
