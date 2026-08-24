"""Resource locks.

One optical drive, one CPU budget, one NAS link. Stages take a lock over the
resource they monopolise so that a second invocation -- from the drainer, from
a second terminal -- steps aside instead of competing.

Non-blocking by default: a stage that cannot get its lock reports and exits, and
the drainer picks the work up on a later pass.
"""

import fcntl
from contextlib import contextmanager
from pathlib import Path

from . import config

DRIVE = "drive"
CPU = "cpu"
NET = "net"
AGENT = "agent"


class Busy(RuntimeError):
    """Someone else holds the lock."""


def _path(name):
    directory = config.ROOT / ".locks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}.lock"


@contextmanager
def hold(name, blocking=False):
    handle = open(_path(name), "w", encoding="utf-8")
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    try:
        try:
            fcntl.flock(handle, flags)
        except OSError as exc:
            raise Busy(f"another process holds the {name} lock") from exc
        handle.write(str(__import__("os").getpid()))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            handle.close()
