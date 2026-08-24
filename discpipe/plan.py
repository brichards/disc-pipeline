"""The naming proposal, and where a rip lives on disk.

plan.json is written by disc-identify and consumed by disc-apply. Decisions are
written back into it as the review proceeds, so an interrupted review resumes
where it stopped rather than starting over.
"""

import json
import os
from pathlib import Path

from . import config, notify

# What disc-identify proposed.
FEATURE = "feature"
EXTRA = "extra"
REJECT = "reject"
UNKNOWN = "unknown"

# What you decided. Absent means not yet reviewed.
ACCEPT = "accept"
EDIT = "edit"
DECLINE = "reject"  # reject the file regardless of what was proposed
KEEP = "keep"  # leave the file exactly as it is


def resolve_target(value):
    """Accept a queue slug or a path.

    Returns (name, media_dir, work_dir, slug). For a queue entry the media
    lives in raw/ and the working files sit beside it. For a loose directory
    the media is the directory itself and the working files go into a dotted
    subdirectory, which keeps them out of Plex's way.
    """
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        raw = candidate / "raw"
        if raw.is_dir():
            return candidate.name, raw, candidate, candidate.name
        return candidate.name, candidate, candidate / ".disc-pipeline", None

    disc_dir = config.ROOT / value
    if disc_dir.is_dir():
        return value, disc_dir / "raw", disc_dir, value

    notify.fail(f"no queue entry or directory named {value!r}")


def path_for(work_dir):
    return Path(work_dir) / "plan.json"


def load(work_dir):
    target = path_for(work_dir)
    if not target.exists():
        notify.fail(f"no plan at {target} -- run disc-identify first")
    with open(target, encoding="utf-8") as fh:
        return json.load(fh)


def save(plan, work_dir):
    """Atomic, because this is rewritten after every keystroke during review."""
    target = path_for(work_dir)
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, target)


def pending(plan):
    return [i for i in plan.get("items", []) if not i.get("decision")]


def outcome(item):
    """What will happen to this file, after the decision is folded in.

    Returns (action, new_name). An undecided item falls back to what was
    proposed, so --yes and a completed review agree.
    """
    decision = item.get("decision")
    if decision == DECLINE:
        return REJECT, ""
    if decision == KEEP:
        return KEEP, ""
    action = item.get("action", UNKNOWN)
    if action in (FEATURE, EXTRA):
        return action, item.get("new_name", "")
    return action, ""
