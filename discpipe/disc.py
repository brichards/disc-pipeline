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
import time
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


# Finder's "available" is free space plus whatever macOS will purge on demand
# for something the user asked for, read from Foundation. osascript reaches
# Foundation without adding a dependency.
_AVAILABLE = """
ObjC.import("Foundation");
function run(argv) {
  const key = "NSURLVolumeAvailableCapacityForImportantUsageKey";
  const url = $.NSURL.fileURLWithPath(argv[0]);
  return url.resourceValuesForKeysError($([key]), null).objectForKey(key).stringValue.js;
}
"""


def available_bytes(path):
    """Room for a write, as Finder counts it. Free space if macOS cannot say."""
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", _AVAILABLE, str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return shutil.disk_usage(path).free


EJECT_ATTEMPTS = 6
EJECT_PAUSE = 5  # seconds


def eject(mount):
    """Spit the disc out so the next one can go in unattended.

    Returns (ejected, why not). diskutil refuses while anything has the disc
    open, and something often does for a moment after a rip, so a refusal is
    retried. drutil is the fallback for a disc already unmounted but still in
    the drive; it exits 0 whether or not it ejected anything, so only the
    drive's own report counts for it.
    """
    refusal = ""
    for attempt in range(EJECT_ATTEMPTS):
        if not Path(mount).exists():
            break
        if attempt:
            time.sleep(EJECT_PAUSE)
        result = _run(["diskutil", "eject", str(mount)])
        if result is not None and result.returncode == 0:
            return True, ""
        refusal = _refusal(result)
    _run(["drutil", "eject"])
    status = _run(["drutil", "status"])
    if status is not None and "No Media Inserted" in status.stdout:
        return True, ""
    return False, refusal or "still in the drive"


def _run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _refusal(result):
    """The line where diskutil names whatever held the disc, if it did."""
    if result is None:
        return ""
    lines = [line.strip() for line in (result.stdout + result.stderr).splitlines()
             if line.strip()]
    held = [line for line in lines if "dissented by" in line]
    return (held or lines or [""])[0]
