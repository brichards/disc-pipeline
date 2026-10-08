"""The naming plan of a disc, and the disc folder that a command acts on.

disc-identify writes plan.json. disc-apply records each decision in it, and
disc-transcode and disc-ship read the result.
"""

import collections
import json
from pathlib import Path

from . import adopt as adoptlib, config, jsonfile, notify

# Values of item["action"], from disc-identify.
FEATURE = "feature"
EXTRA = "extra"
REJECT = "reject"
UNKNOWN = "unknown"

# Values of item["decision"], from the review. An item with no decision is not
# reviewed.
ACCEPT = "accept"
EDIT = "edit"
DECLINE = "reject"
KEEP = "keep"


def resolve_target(value=None):
    candidate = Path.cwd() if value in (None, "") else Path(value).expanduser()
    if not candidate.is_dir():
        candidate = config.ROOT / str(value)
    if not candidate.is_dir():
        notify.fail(f"no queue entry or directory named {value!r}")

    root = config.ROOT.resolve()
    if candidate.resolve() == root:
        notify.fail(f"{candidate} is the queue root, not a rip -- "
                    "name a disc, or cd into one")
    if candidate.resolve().parent != root:
        notify.fail(f"{candidate} is not a disc folder in {config.ROOT}. "
                    f"Name a disc, or move the folder into {config.ROOT}.")

    if not (candidate / "manifest.json").exists():
        if not adoptlib.is_adoptable(candidate):
            notify.fail(f"{candidate} has no manifest and no .mkv files")
        adoptlib.adopt(candidate)

    return candidate


def path_for(work_dir):
    return Path(work_dir) / "plan.json"


def load(work_dir):
    target = path_for(work_dir)
    if not target.exists():
        notify.fail(f"no plan at {target} -- run disc-identify first")
    with open(target, encoding="utf-8") as fh:
        return json.load(fh)


def save(plan, work_dir):
    jsonfile.write(path_for(work_dir), plan)


def tally(plan):
    counts = collections.Counter(item.get("action", "?") for item in plan.get("items", []))
    return ", ".join(f"{n} {action}" for action, n in sorted(counts.items()))


def kept(plan):
    for item in plan.get("items", []):
        action, new_name = outcome(item)
        if action in (FEATURE, EXTRA) and new_name:
            yield item, action, new_name


def pending(plan):
    return [i for i in plan.get("items", []) if not i.get("decision")]


def outcome(item):
    decision = item.get("decision")
    if decision == DECLINE:
        return REJECT, ""
    if decision == KEEP:
        return KEEP, ""
    action = item.get("action", UNKNOWN)
    if action in (FEATURE, EXTRA):
        return action, item.get("new_name", "")
    return action, ""
