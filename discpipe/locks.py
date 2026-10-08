"""Locks that give a shared resource to one process at a time.

The resources are the drive, the CPU, the NAS link, the agent and the drainer
session. The lock files are in ~/.disc-pipeline/locks, the same for each queue.
A stage that cannot get its lock exits, and the drainer tries again later.
"""

import fcntl
from contextlib import contextmanager
from pathlib import Path

DRIVE = "drive"
CPU = "cpu"
NET = "net"
AGENT = "agent"
SESSION = "session"


class Busy(RuntimeError):
    pass


LOCK_DIR = Path.home() / ".disc-pipeline" / "locks"


def _path(name):
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    return LOCK_DIR / f"{name}.lock"


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


def is_free(name):
    try:
        with hold(name):
            return True
    except Busy:
        return False
