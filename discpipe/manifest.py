"""The state of each disc, and the ledger of each disc ever seen.

manifest.json in each disc folder records the stage and the titles of the
disc. The ledger, ledger.jsonl in the queue root, records each disc by its
fingerprint, and stays after disc-cleanup deletes the disc folder.
overrides.json in the queue root records the playlist for a decoy disc.
"""

import json
import time

from . import config, jsonfile

VERSION = 1

QUEUED = "queued"
RIPPED = "ripped"
IDENTIFIED = "identified"
APPLIED = "applied"
TRANSCODED = "transcoded"
SHIPPED = "shipped"
DONE = "done"
HELD = "held"

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


def find(slug):
    try:
        return load(slug)
    except (OSError, ValueError):
        return None


def save(data):
    data["updated"] = now()
    jsonfile.write(path_for(data["slug"]), data)


def queue_dirs():
    if not config.ROOT.exists():
        return []
    return [path for path in sorted(config.ROOT.iterdir())
            if path.is_dir() and not path.name.startswith(".")]


def all_discs():
    if not config.ROOT.exists():
        return []
    found = (find(p.parent.name) for p in sorted(config.ROOT.glob("*/manifest.json")))
    return [data for data in found if data is not None]


def hold(data, reason, retryable=False, stage=None):
    data["state"] = HELD
    data["held_reason"] = reason
    data["held_retryable"] = bool(retryable)
    if stage:
        data["held_stage"] = stage
    save(data)
    return data


def advance(data, state):
    data["state"] = state
    data["held_reason"] = None
    save(data)
    return data


def advance_slug(slug, state):
    return advance(load(slug), state)


def subdir(slug, name):
    path = disc_dir(slug) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_append(entry):
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
                match = entry
    return match


def overrides_load():
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
    jsonfile.write(config.OVERRIDES, data)
    return data
