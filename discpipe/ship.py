"""Copy finished media to the NAS, and verify the copy.

disc-ship copies and verifies. disc-cleanup verifies the copy again before it
offers a delete.
"""

import os
import subprocess
from pathlib import Path

from . import proc

# SMB cannot keep permissions or ownership. If rsync tries, it reports errors
# that do not matter.
#
# --partial leaves a partial file under its real name. In a Plex library, that
# file looks like a complete movie and stops early. --partial-dir keeps the
# partial file in a hidden folder, and rsync excludes that folder from the
# transfer.
PARTIAL_DIR = ".disc-pipeline-partial"
#
# This share does not accept modification times. Each file gets the time of
# the transfer. If rsync compares size and time, it sends each file again on
# each new run.
TRANSFER_ARGS = ["--recursive", "--times", "--size-only",
                 f"--partial-dir={PARTIAL_DIR}", "--human-readable"]
VERIFY_ARGS = ["--recursive", "--times", "--checksum", "--dry-run",
               "--itemize-changes"]


class NotMounted(RuntimeError):
    pass


def volume_root(path):
    path = Path(path)
    candidate = path if path.exists() else path.parent
    while True:
        if os.path.ismount(candidate):
            return candidate
        if candidate == candidate.parent:
            return None
        candidate = candidate.parent


def ensure_mounted(destination):
    """When a share is not mounted, its path has nothing, or a folder on the boot disk.

    Both look writable, but neither is the NAS. os.path.ismount tells them apart.
    """
    destination = Path(destination)
    root = volume_root(destination)
    if root is None or root == Path("/"):
        raise NotMounted(
            f"{destination} is not on a mounted volume -- is the share connected?"
        )
    if not destination.parent.exists():
        raise NotMounted(f"{destination.parent} does not exist on {root}")
    return root


def plan_transfer(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_file():
        return [(source, destination)]
    pairs = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            pairs.append((path, destination / path.relative_to(source)))
    return pairs


def promote(bare_file, folder):
    """Plex attaches extras only to a movie in a movie folder."""
    bare_file, folder = Path(bare_file), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / bare_file.name
    if target.exists():
        raise FileExistsError(target)
    bare_file.rename(target)
    return target


def transfer(source, destination, on_line=None):
    source, destination = Path(source), Path(destination)
    if source.is_dir():
        args = [f"{source}/", f"{destination}/"]
        destination.mkdir(parents=True, exist_ok=True)
    else:
        args = [str(source), str(destination)]
        destination.parent.mkdir(parents=True, exist_ok=True)

    return proc.stream(
        ["rsync", *TRANSFER_ARGS, "--info=progress2", *args], on_line
    )


def verify(source, destination):
    """rsync with --checksum and --dry-run lists the files that it must still send.

    No output means that each byte is already on the NAS.
    """
    source, destination = Path(source), Path(destination)
    args = ([f"{source}/", f"{destination}/"] if source.is_dir()
            else [str(source), str(destination)])
    result = subprocess.run(
        ["rsync", *VERIFY_ARGS, *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, (result.stderr or "rsync verify failed").strip()

    outstanding = [line for line in result.stdout.splitlines()
                   if _is_mismatch(line)]
    if outstanding:
        return False, "; ".join(outstanding[:5])
    return True, ""


def _is_mismatch(line):
    """The flags of an --itemize-changes line are YXcstpoguax.

    A first character of '.' means that rsync sends no data: the file is already
    there. A 't' can follow, because SMB does not keep modification times
    exactly. Only a transfer marker, a checksum flag or a size flag means that
    the copy is different.
    """
    line = line.rstrip()
    if not line or line.startswith(("sending", "sent ", "total ")):
        return False
    if line.endswith("./"):
        return False
    if line.startswith(("*deleting", "cd", "hf")):
        return True
    if len(line) < 4:
        return False
    update, _, checksum, size = line[0], line[1], line[2], line[3]
    if update in (">", "<"):
        return True
    return checksum == "c" or size == "s"
