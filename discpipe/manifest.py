"""Per-disc state.

manifest.json is the single source of truth for where a disc is in the
pipeline. The ledger records identity and disposition only, so it can outlive
the queue directory after cleanup; nothing duplicates stage state, because two
copies of a state machine drift and then you are debugging which one lied.
"""

import json
import os
import time
from pathlib import Path

from . import config

VERSION = 1

# Stage states. The drainer advances a disc whenever its state has an automatic
# successor; HELD and the two gate states are where it stops.
QUEUED = "queued"
RIPPED = "ripped"
IDENTIFIED = "identified"  # gate: awaiting your review
APPLIED = "applied"
TRANSCODED = "transcoded"
SHIPPED = "shipped"  # gate: awaiting retention decision
DONE = "done"
HELD = "held"  # needs a human, see held_reason

GATE_STATES = (IDENTIFIED, SHIPPED, HELD)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def new(slug, fingerprint, label, disc_type):
    return {
        "version": VERSION,
        "slug": slug,
        "fingerprint": fingerprint,
        "label": label,
        "disc_type": disc_type,
        "media_type": "movie",
        "state": QUEUED,
        "held_reason": None,
        "created": now(),
        "updated": now(),
        "titles": [],
        "rip": {"exit_code": None, "warnings": [], "ripped_at": None},
        "keep_source": "ask",
    }


def disc_dir(slug):
    return config.ROOT / slug


def path_for(slug):
    return disc_dir(slug) / "manifest.json"


def load(slug):
    with open(path_for(slug), encoding="utf-8") as fh:
        return json.load(fh)


def save(data):
    """Write atomically so an interrupted save can't truncate the manifest."""
    data["updated"] = now()
    target = path_for(data["slug"])
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, target)


def all_discs():
    """Every queued disc, oldest first. disc-status and the drainer read this."""
    out = []
    if not config.ROOT.exists():
        return out
    for candidate in sorted(config.ROOT.glob("*/manifest.json")):
        try:
            with open(candidate, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def hold(data, reason, retryable=False):
    """Park a disc for attention.

    retryable marks a hold whose cause is external and may simply go away --
    no disk space, share not mounted. Those can be retried by running the stage
    again once the condition clears. A hold that needs a decision -- an
    unresolved decoy disc, a damaged title -- is not retryable, and re-running
    will land in the same place.
    """
    data["state"] = HELD
    data["held_reason"] = reason
    data["held_retryable"] = bool(retryable)
    save(data)
    return data


def advance(data, state):
    data["state"] = state
    data["held_reason"] = None
    save(data)
    return data


def subdir(slug, name):
    path = disc_dir(slug) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_append(entry):
    """Append-only record of every disc ever seen, keyed by fingerprint."""
    config.ensure_root()
    with open(config.LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def ledger_find(fingerprint):
    if not config.LEDGER.exists():
        return None
    match = None
    with open(config.LEDGER, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("fingerprint") == fingerprint:
                match = entry  # last write wins
    return match


def overrides_load():
    """Playlist answers for discs that defeated metadata triage."""
    if not config.OVERRIDES.exists():
        return {}
    try:
        with open(config.OVERRIDES, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def overrides_set(fingerprint, playlist, note=""):
    data = overrides_load()
    data[fingerprint] = {"playlist": playlist, "note": note, "recorded": now()}
    config.ensure_root()
    tmp = Path(str(config.OVERRIDES) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, config.OVERRIDES)
    return data
