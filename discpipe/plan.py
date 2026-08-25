"""The naming proposal, and where a rip lives on disk.

plan.json is written by disc-identify and consumed by disc-apply. Decisions are
written back into it as the review proceeds, so an interrupted review resumes
where it stopped rather than starting over.
"""

import json
import os
from pathlib import Path

from . import adopt as adoptlib, config, notify

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


def resolve_target(value=None):
    """Accept a queue slug, a path, or nothing at all.

    With no argument the current directory is the target, so you can cd into a
    rip and run the stages bare. Returns (name, media_dir, work_dir, slug).

    Every target ends up in one shape: a manifest, the media in raw/, and
    everything else beside it. A folder of loose .mkv files gets there by being
    adopted, so there is no second kind of target to reason about.
    """
    candidate = Path.cwd() if value in (None, "") else Path(value).expanduser()
    if not candidate.is_dir():
        candidate = config.ROOT / str(value)
    if not candidate.is_dir():
        notify.fail(f"no queue entry or directory named {value!r}")

    try:
        if candidate.resolve() == config.ROOT.resolve():
            notify.fail(f"{candidate} is the queue root, not a rip -- "
                        "name a disc, or cd into one")
    except OSError:
        pass

    if not (candidate / "manifest.json").exists():
        if not adoptlib.is_adoptable(candidate):
            notify.fail(f"{candidate} has no manifest and no .mkv files")
        adoptlib.adopt(candidate)

    return candidate.name, candidate / "raw", candidate, candidate.name


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
