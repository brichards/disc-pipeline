"""Desktop notifications and console output.

Failures notify, because they stop the pipeline and you may not look for a day.
Gates do not -- the disc is not going anywhere, and interrupting you to say a
thing succeeded is how notifications get ignored. Use disc-status for those.
"""

import os
import shlex
import subprocess
import sys


def alert(title, message):
    """A macOS notification. Failures only."""
    script = "display notification {} with title {}".format(
        _applescript_string(message), _applescript_string(title)
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass  # never let a notification failure take down a stage
    say(f"! {title}: {message}")


def _applescript_string(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


# Set by disc-watch so several discs can share one tailable log without their
# output becoming impossible to attribute.
LOG_PREFIX = os.environ.get("DISC_LOG_PREFIX", "")


def say(message):
    if LOG_PREFIX and message:
        message = "\n".join(
            f"{LOG_PREFIX}{line}" for line in str(message).split("\n")
        )
    print(message, flush=True)


def fail(message, code=1):
    print(f"error: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


def human_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def quote(args):
    return " ".join(shlex.quote(str(a)) for a in args)
