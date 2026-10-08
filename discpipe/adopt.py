"""Make a folder of .mkv files into a disc folder of the queue.

The folder gets a manifest, and its .mkv files move into raw/. A stage adopts a
folder only when you point the stage at that folder. The drainer does not adopt.
"""

from pathlib import Path

from . import manifest, notify

FINGERPRINT = None
DISC_TYPE = "adopted"


def is_adoptable(path):
    path = Path(path)
    if (path / "manifest.json").exists():
        return False
    return any(path.glob("*.mkv"))


def adopt(path):
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

    data["state"] = manifest.RIPPED
    manifest.save(data)

    notify.say(f"Adopted {slug}: {moved} file(s) moved into raw/")
    return data
