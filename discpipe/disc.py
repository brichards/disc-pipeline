"""Finding a disc in the drive and identifying it without reading its video.

AACS encrypts the .m2ts payloads but not the filesystem, and CSS does the same
on DVD -- so filenames and sizes are readable with no key, no decryption, and
no MakeMKV spin-up. That is enough to fingerprint a disc, which is all we need
to know whether it has been ripped before.
"""

import hashlib
import re
import shutil
import unicodedata
from pathlib import Path

BLURAY = "bluray"
DVD = "dvd"

VOLUMES = Path("/Volumes")

_MARKERS = {
    BLURAY: Path("BDMV/index.bdmv"),
    DVD: Path("VIDEO_TS/VIDEO_TS.IFO"),
}

# Files whose names and sizes form the fingerprint. Segment sizes are
# effectively a per-authoring signature.
_FINGERPRINT_GLOBS = {
    BLURAY: ("BDMV/STREAM/*.m2ts", "BDMV/PLAYLIST/*.mpls"),
    DVD: ("VIDEO_TS/*.VOB", "VIDEO_TS/*.IFO"),
}


def disc_type(mount):
    for kind, marker in _MARKERS.items():
        if (mount / marker).exists():
            return kind
    return None


def find_discs():
    """Every mounted volume that looks like video media."""
    found = []
    if not VOLUMES.exists():
        return found
    for mount in sorted(VOLUMES.iterdir()):
        try:
            kind = disc_type(mount)
        except OSError:
            continue
        if kind:
            found.append((mount, kind))
    return found


def fingerprint(mount, kind):
    digest = hashlib.sha256()
    entries = []
    for pattern in _FINGERPRINT_GLOBS[kind]:
        for path in mount.glob(pattern):
            try:
                entries.append(f"{path.name}:{path.stat().st_size}")
            except OSError:
                continue
    if not entries:
        raise ValueError(f"no stream files found under {mount}")
    for entry in sorted(entries):
        digest.update(entry.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def slugify(label, fingerprint_hex):
    """Queue directory name: readable, unique, filesystem-safe."""
    text = unicodedata.normalize("NFKD", label or "disc")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "disc"
    return f"{text}-{fingerprint_hex[:6]}"


def free_bytes(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free


def estimated_bytes(titles):
    """MakeMKV's own size estimates for the titles we intend to rip."""
    return sum(t.size_bytes for t in titles)
