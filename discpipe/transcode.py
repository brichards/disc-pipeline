"""Choose a transcoder for a file, and run it.

Both transcoders write their output into the current working directory, with
the base name of the input. Neither one writes over a file that exists.
"""

import contextlib
import os
import shutil
from pathlib import Path

from . import proc, ship

SD_HD = "transcode-video.rb"
UHD = "hevc-transcode.rb"

COMMON_ARGS = ["--add-subtitle", "all"]

# The transcoders run HandBrakeCLI. Without it, they fail on each file, not at
# the start.
REQUIRED = ("HandBrakeCLI", "ffprobe")


# A disc does not carry AAC. Blu-ray permits LPCM, Dolby Digital, DD+, DTS,
# DTS-HD and TrueHD. DVD permits AC-3, DTS, PCM and MPEG audio. Thus a file with
# only AAC audio came from a transcoder, not from a disc.
TARGET_AUDIO = "aac"


def already_encoded(info):
    audio = (info or {}).get("audio") or []
    if not audio:
        return False
    return all((track.get("codec") or "").lower() == TARGET_AUDIO
               for track in audio)


def staging_for(work_dir):
    return Path(work_dir) / "transcoded" / ship.PARTIAL_DIR


def _staged(source, staging):
    staged = output_for(source, staging)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.unlink(missing_ok=True)
    return staged


def adopt_encoded(source, out_dir, staging):
    """A hard link uses no extra space, but only in one file system."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = output_for(source, out_dir)
    if destination.exists():
        return destination
    try:
        os.link(source, destination)
    except OSError:
        staged = _staged(source, staging)
        shutil.copy2(source, staged)
        os.replace(staged, destination)
        with contextlib.suppress(OSError):
            staged.parent.rmdir()
    return destination


def route(height):
    return UHD if (height or 0) > 1080 else SD_HD


def missing_tools(script):
    absent = [t for t in REQUIRED if shutil.which(t) is None]
    if shutil.which(script) is None:
        absent.append(script)
    return absent


def output_for(source, out_dir):
    return Path(out_dir) / (Path(source).stem + ".mkv")


def run(source, out_dir, script, staging, extra_args=(), on_line=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = output_for(source, out_dir)
    staged = _staged(source, staging)

    code = proc.stream(
        [script, str(Path(source).resolve()), *COMMON_ARGS, *extra_args],
        on_line,
        cwd=staged.parent,
    )
    if code == 0 and staged.exists():
        os.replace(staged, destination)
    staged.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        staged.parent.rmdir()
    return code, destination
