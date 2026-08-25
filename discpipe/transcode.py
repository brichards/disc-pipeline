"""Routing and running the transcoders.

Both tools write their output into the current working directory, named after
the input's basename, and refuse to overwrite an existing file. So the runner
sets cwd to the destination rather than passing an output path -- and that
refusal is what makes a re-run resumable: finished files are simply skipped.
"""

import os
import shutil
import subprocess
from pathlib import Path

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


def adopt_encoded(source, out_dir):
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
        shutil.copy2(source, destination)
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


def build_command(source, script, extra_args=()):
    return [script, str(source), *COMMON_ARGS, *extra_args]


def run(source, out_dir, script, extra_args=(), on_line=None):
    """Transcode one file into out_dir. Returns (exit_code, output_path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = output_for(source, out_dir)

    process = subprocess.Popen(
        build_command(Path(source).resolve(), script, extra_args),
        cwd=str(out_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        if on_line:
            on_line(line.rstrip())
    process.wait()
    return process.returncode, destination
