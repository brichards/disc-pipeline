"""Routing and running the transcoders.

Both tools write their output into the current working directory, named after
the input's basename, and refuse to overwrite an existing file. So the runner
sets cwd to the destination rather than passing an output path -- and that
refusal is what makes a re-run resumable: finished files are simply skipped.
"""

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
