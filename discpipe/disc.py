"""Find, identify and eject the disc in the drive, and measure the space for a rip."""

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

# Each authoring of a disc has its own set of segment sizes.
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
    return [(mount, kind) for mount, kind in _marked() if _readable(mount, kind)]


def stale_mounts():
    return [mount for mount, kind in _marked() if not _readable(mount, kind)]


def _marked():
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
    """macOS can keep the mount point after the disc goes out of the drive.

    The volume stays in /Volumes and stat() of its marker file succeeds, but
    each read fails with EIO.
    """
    for pattern in _FINGERPRINT_GLOBS[kind]:
        try:
            for _ in mount.glob(pattern):
                return True
        except OSError:
            return False
    return False


def fingerprint(mount, kind):
    """AACS and CSS encrypt the video of a disc, but not its file system.

    Thus the names and sizes of the files are available with no key and no
    MakeMKV scan.
    """
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
    text = unicodedata.normalize("NFKD", label or "disc")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "disc"
    return f"{text}-{fingerprint_hex[:6]}"


# Finder shows the free space plus the space that macOS can purge for a request
# from the user. Foundation gives this value, and osascript can read it.
_AVAILABLE = """
ObjC.import("Foundation");
function run(argv) {
  const key = "NSURLVolumeAvailableCapacityForImportantUsageKey";
  const url = $.NSURL.fileURLWithPath(argv[0]);
  return url.resourceValuesForKeysError($([key]), null).objectForKey(key).stringValue.js;
}
"""


def available_bytes(path):
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
EJECT_PAUSE = 5


def eject(mount):
    """diskutil does not eject a disc while a process has it open.

    After a rip, a process often has the disc open for a short time. drutil can
    eject a disc that is unmounted but still in the drive. drutil exits with 0
    also when it ejects nothing, so only drutil status shows the result.
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
    if result is None:
        return ""
    lines = [line.strip() for line in (result.stdout + result.stderr).splitlines()
             if line.strip()]
    held = [line for line in lines if "dissented by" in line]
    return (held or lines or [""])[0]
