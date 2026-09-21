"""Proving a suspect rip actually decodes.

MakeMKV works around unreadable sectors and exits clean, so a damaged rip
reaches the end of the pipeline looking exactly like a good one. Decoding every
frame and discarding the output is the cheap, definitive answer: silence means
the file is fine.

Measured on a 33 GB, 2:24 feature: 5 minutes 14 seconds. Cheap enough to do
automatically rather than ask.
"""

import re
import subprocess

OFFSET = re.compile(r"at offset '(\d+)'")


def read_error_offsets(warnings):
    """Byte offsets MakeMKV reported as unreadable, in source order."""
    offsets = []
    for line in warnings or ():
        match = OFFSET.search(line)
        if match:
            offsets.append(int(match.group(1)))
    return sorted(set(offsets))


def approximate_times(offsets, size_bytes, seconds):
    """Roughly where in the runtime those offsets fall.

    The ripped file is a remux of the source stream, so byte position maps to
    time only approximately -- and less well at variable bitrate. Good enough
    to know where to look, not good enough to quote.
    """
    if not size_bytes or not seconds:
        return []
    return [offset / size_bytes * seconds for offset in offsets]


def hms(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


# ffmpeg tags each message with the component that produced it. The null muxer
# we discard output through reports non-monotonic timestamps at error level,
# and DVD MPEG-2 produces those in normal playback. Only the decoders speak to
# whether the picture and sound are intact.
_MUXER_NOISE = re.compile(r"^\[null @ ")


def decode(path, start=None, duration=None):
    """Decode and throw the output away. Returns (ok, error_lines)."""
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
