"""Finding a disc in the drive and identifying it without reading its video.

AACS encrypts the .m2ts payloads but not the filesystem, and CSS does the same
on DVD -- so filenames and sizes are readable with no key, no decryption, and
no MakeMKV spin-up. That is enough to fingerprint a disc, which is all we need
to know whether it has been ripped before.
"""

import hashlib
import re
import shutil
import subprocess
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
    """Every mounted volume holding video media we can actually read."""
    return [(mount, kind) for mount, kind in _marked() if _readable(mount, kind)]


def stale_mounts():
    """Volumes that look like a disc but whose media cannot be read.

    Reported rather than skipped in silence: one of these looks exactly like a
    loaded disc to anything checking for BDMV, so a caller finding no disc
    while Finder shows one deserves to be told why. Clearing it takes a
    diskutil unmount, which is the user's call to make, not ours.
    """
    return [mount for mount, kind in _marked() if not _readable(mount, kind)]


def _marked():
    """Mounted volumes carrying a Blu-ray or DVD marker file."""
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


def _readable(mount, kind):
    """Whether the volume's stream files can be listed.

    macOS leaves the mount point behind when a disc is ejected out from under
    it or the drive drops the media: the volume still appears under /Volumes
    and its marker file still stats, but every read returns EIO. Listing one
    stream file is the cheapest thing that separates loaded media from that
    leftover, and it is the same access fingerprint() needs a moment later.
    """
    for pattern in _FINGERPRINT_GLOBS[kind]:
        try:
            for _ in mount.glob(pattern):
                return True
        except OSError:
            return False
    return False


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


def eject(mount):
    """Spit the disc out so the next one can go in unattended.

    diskutil unmounts and ejects in one step; drutil is the fallback for a
    drive that has already been unmounted but still holds the media.
    """
    for command in (["diskutil", "eject", str(mount)], ["drutil", "eject"]):
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return True
    return False
