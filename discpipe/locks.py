"""Resource locks.

One optical drive, one CPU budget, one NAS link. Stages take a lock over the
resource they monopolise so that a second invocation -- from the drainer, from
a second terminal -- steps aside instead of competing.

Non-blocking by default: a stage that cannot get its lock reports and exits, and
the drainer picks the work up on a later pass.

The lock directory is fixed per user, deliberately not under the queue root.
These guard hardware, and the hardware does not care which queue you pointed
at: locks under DISC_PIPELINE_ROOT gave two roots two separate namespaces, so a
second queue would happily drive the same optical drive as the first.
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
    """Someone else holds the lock."""


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
    """Whether a resource is currently unlocked.

    The drainer only tracks what it started itself, so a stage run by hand --
    or by disc-watch -- is invisible to it. Testing the lock directly keeps it
    from launching a duplicate that would only step aside and exit.
    """
    try:
        with hold(name):
            return True
    except Busy:
        return False
