"""Turning a folder of loose files into a queue entry.

The pipeline has one shape: a directory with a manifest, the media in raw/, and
everything else written beside it in the open. A folder ripped by hand -- or by
MakeMKV directly -- becomes that shape by gaining a manifest and having its
files moved down a level, which on one filesystem is a rename.

Adoption only ever happens when you point a command at a folder. The drainer
does not adopt: it advances what already has a manifest, so a directory you are
still copying into sits untouched until you act on it.
"""

from pathlib import Path

from . import manifest, notify

# A folder ripped by hand has no disc behind it, so there is nothing to
# fingerprint. The ledger only uses fingerprints to answer "have I ripped this
# disc before", which does not apply here -- so record nothing rather than
# inventing an identifier that claims to mean something.
FINGERPRINT = None
DISC_TYPE = "adopted"


def is_adoptable(path):
    """A directory holding .mkv files and no manifest."""
    path = Path(path)
    if (path / "manifest.json").exists():
        return False
    return any(path.glob("*.mkv"))


def adopt(path):
    """Give a folder a manifest and move its media into raw/.

    The directory keeps its own name. Fingerprint-derived slugs exist because
    disc-rip needs a collision-proof name before it knows what the disc is; a
    folder you named yourself already has one.
    """
    path = Path(path)
    slug = path.name
    raw = path / "raw"
    files = sorted(p for p in path.glob("*.mkv") if p.is_file())

    data = manifest.new(slug, FINGERPRINT, slug, DISC_TYPE)
    data["adopted"] = manifest.now()
    data["titles"] = [
        {
            "index": index,
            "output_name": one.name,
            "size_bytes": one.stat().st_size,
            "source_file": one.name,
            "rip": {"status": "done", "exit_code": 0, "output": one.name,
                    "warnings": [], "at": manifest.now(), "adopted": True},
        }
        for index, one in enumerate(files)
    ]

    raw.mkdir(exist_ok=True)
    moved = 0
    for one in files:
        target = raw / one.name
        if target.exists():
            notify.say(f"  ! {one.name} already in raw/, leaving it")
            continue
        one.rename(target)
        moved += 1

    # Ripped, not queued: queued would send the drainer looking for a disc.
    data["state"] = manifest.RIPPED
    manifest.save(data)

    notify.say(f"Adopted {slug}: {moved} file(s) moved into raw/")
    return data
