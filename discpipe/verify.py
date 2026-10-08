"""Decode a ripped file in full, and report the errors of its decoders.

disc-verify uses it for each title with read errors.
"""

import re
import subprocess

OFFSET = re.compile(r"at offset '(\d+)'")


def read_error_offsets(warnings):
    offsets = []
    for line in warnings or ():
        match = OFFSET.search(line)
        if match:
            offsets.append(int(match.group(1)))
    return sorted(set(offsets))


def approximate_times(offsets, size_bytes, seconds):
    """The ripped file is a remux of the source stream.

    Thus a byte position gives only an approximate time, and less accurate at
    a variable bit rate.
    """
    if not size_bytes or not seconds:
        return []
    return [offset / size_bytes * seconds for offset in offsets]


def hms(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


# ffmpeg starts each message with the name of the component that sent it. The
# null muxer reports timestamps that are not monotonic at the error level, and
# DVD MPEG-2 gives such timestamps in normal playback. Only the decoders report
# damage to the picture and the sound.
_MUXER_NOISE = re.compile(r"^\[null @ ")


def decode(path, start=None, duration=None):
    command = ["ffmpeg", "-v", "error"]
    if start is not None:
        command += ["-ss", str(start)]
    command += ["-i", str(path)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-f", "null", "-"]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    lines = [line for line in result.stderr.splitlines()
             if line.strip() and not _MUXER_NOISE.match(line)]
    return (result.returncode == 0 and not lines), lines
