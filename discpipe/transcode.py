"""Routing and running the transcoders.

Both tools write their output into the current working directory, named after
the input's basename, and refuse to overwrite an existing file. So the runner
points them at a staging directory and moves a file into the output only once
the tool exits cleanly. The output then holds nothing but finished files: a
transcode killed partway leaves nothing under the final name, and a re-run
skips what is already there.
"""

import contextlib
import os
import shutil
from pathlib import Path

from . import proc, ship

SD_HD = "transcode-video.rb"  # 1080p and below
UHD = "hevc-transcode.rb"  # above 1080p

# Every transcode carries all subtitle tracks through.
COMMON_ARGS = ["--add-subtitle", "all"]

# The transcoders shell out to HandBrake; without it they fail per-file rather
# than up front, which wastes the whole queue's turn.
REQUIRED = ("HandBrakeCLI", "ffprobe")


# Discs do not carry AAC. Blu-ray allows LPCM, Dolby Digital, DD+, DTS, DTS-HD
# and TrueHD; DVD allows AC-3, DTS, PCM and MPEG audio. So a file whose audio is
# entirely AAC did not come off a disc -- it came out of a transcoder, and
# running it through another one would cost hours and a generation of quality
# for no gain.
TARGET_AUDIO = "aac"


def already_encoded(info):
    """Whether this file is already in the format transcoding would produce."""
    audio = (info or {}).get("audio") or []
    if not audio:
        return False
    return all((track.get("codec") or "").lower() == TARGET_AUDIO
               for track in audio)


def staging_for(work_dir):
    return Path(work_dir) / "transcoded" / ship.PARTIAL_DIR


def _staged(source, staging):
    """A clear path to write source's output to before it is finished.

    Anything already there was left by a run that was killed, and the
    transcoders would refuse to overwrite it.
    """
    staged = output_for(source, staging)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.unlink(missing_ok=True)
    return staged


def adopt_encoded(source, out_dir, staging):
    """Put an already-encoded file into the output without re-encoding.

    A hard link costs nothing and no extra space; a copy is the fallback when
    the two are on different filesystems.
    """
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
    """Above 1080 goes to HEVC, everything else to H.264."""
    return UHD if (height or 0) > 1080 else SD_HD


def missing_tools(script):
    absent = [t for t in REQUIRED if shutil.which(t) is None]
    if shutil.which(script) is None:
        absent.append(script)
    return absent


def output_for(source, out_dir):
    return Path(out_dir) / (Path(source).stem + ".mkv")


def run(source, out_dir, script, staging, extra_args=(), on_line=None):
    """Transcode one file into out_dir. Returns (exit_code, output_path)."""
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
