"""Getting finished media onto the NAS, and proving it arrived.

Two things this module exists to prevent. Writing tens of gigabytes into an
empty directory on the boot volume because the share silently unmounted, and
declaring success on a copy nobody checked.
"""

import os
import subprocess
from pathlib import Path

# Preserve times but not permissions or ownership: SMB cannot honour them, and
# asking makes rsync noisy about failures that do not matter.
#
# --partial-dir rather than --partial. Both resume an interrupted transfer, but
# plain --partial leaves the half-written file under its real name, which in a
# Plex library is a movie that looks complete and plays truncated. Sending
# partials to a hidden sibling directory means the final name only ever appears
# on a finished file. rsync excludes the partial directory from the transfer
# automatically.
PARTIAL_DIR = ".disc-pipeline-partial"
#
# --size-only, because this share does not accept modification times at all:
# files land carrying the time of the transfer, hours off the source. Left to
# compare on size-and-time, rsync would resend every byte on every re-run.
# Content is proved separately by the checksum pass below, so skipping on size
# is safe here in a way it would not be on its own.
TRANSFER_ARGS = ["--recursive", "--times", "--size-only",
                 f"--partial-dir={PARTIAL_DIR}", "--human-readable"]
VERIFY_ARGS = ["--recursive", "--times", "--checksum", "--dry-run",
               "--itemize-changes"]


class NotMounted(RuntimeError):
    pass


def volume_root(path):
    """The mount point a path lives under, or None if it is on no volume."""
    path = Path(path)
    candidate = path if path.exists() else path.parent
    while True:
        if os.path.ismount(candidate):
            return candidate
        if candidate == candidate.parent:
            return None
        candidate = candidate.parent


def ensure_mounted(destination):
    """Refuse to write unless the destination really is on a mounted volume.

    An unmounted share leaves either nothing at the path or a bare directory on
    the boot disk. Both look writable; neither is the NAS. os.path.ismount is
    the difference between the two.
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
    """Every file that will be written, as (source, destination) pairs.

    Computed rather than delegated to rsync so collisions can be reported
    before anything is copied.
    """
    source, destination = Path(source), Path(destination)
    if source.is_file():
        return [(source, destination)]
    pairs = []
    for path in sorted(source.rglob("*")):
        if path.is_file():
            pairs.append((path, destination / path.relative_to(source)))
    return pairs


def promote(bare_file, folder):
    """Move a bare movie file into a folder of the same name.

    Plex needs the movie folder before extras can attach to it, so a title that
    shipped without extras has to be promoted when extras turn up later.
    """
    bare_file, folder = Path(bare_file), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / bare_file.name
    if target.exists():
        raise FileExistsError(target)
    bare_file.rename(target)
    return target


def transfer(source, destination, on_line=None):
    """rsync source to destination. Returns the exit code."""
    source, destination = Path(source), Path(destination)
    if source.is_dir():
        args = [f"{source}/", f"{destination}/"]
        destination.mkdir(parents=True, exist_ok=True)
    else:
        args = [str(source), str(destination)]
        destination.parent.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        ["rsync", *TRANSFER_ARGS, "--info=progress2", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        if on_line:
            on_line(line.rstrip())
    process.wait()
    return process.returncode


def verify(source, destination):
    """A content-level check that everything arrived.

    rsync in checksum dry-run mode lists what it would still need to send.
    Empty output means every byte is already there -- a real comparison, not a
    size-and-timestamp guess, and without hand-rolling checksums over SMB.
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
    """Whether an --itemize-changes line means the content actually differs.

    The flags are YXcstpoguax. A leading '.' means rsync would send no data --
    the file is already there, byte for byte. What follows can still show a 't',
    because SMB does not preserve modification times exactly, and that is not a
    difference worth refusing to clean up over.

    Only a transfer marker, or a checksum or size flag, means the copy is wrong.
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
