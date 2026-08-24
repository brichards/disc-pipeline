"""Reading ripped files: stream inventory and contact sheets.

Identification is a visual problem -- title cards, credits, whether two files
are the same programme -- so this module's job is to put enough of each file
in front of the agent that it can decide without opening anything itself.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

# Frames per contact sheet, and the grid they are tiled into.
# The head window has to clear the studio logo before the title card appears.
# 75 seconds at 3-second intervals: a card typically holds for 3-5 seconds, and
# on Taken 2 the Fox logo alone runs past 36. SpongeBob discs are worse -- the
# card lands after the theme song, around 40-60 seconds in.
HEAD_FRAMES = 25
HEAD_GRID = "5x5"
HEAD_WINDOW = 75.0
SCAN_FRAMES = 16  # spread across the runtime, for content and credits
SCAN_GRID = "4x4"

THUMB_W = 320
THUMB_H = 180


def ffprobe(path):
    """Duration, dimensions, and stream layout for one file."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-show_entries", "stream=index,codec_type,codec_name,channels,width,height",
            "-show_entries", "stream_tags=language,title",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    seconds = float(data.get("format", {}).get("duration") or 0)
    video = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    subs = [s for s in data.get("streams", []) if s.get("codec_type") == "subtitle"]

    return {
        "file": path.name,
        "seconds": round(seconds, 2),
        "duration": _hms(seconds),
        "width": video[0].get("width") if video else None,
        "height": video[0].get("height") if video else None,
        "audio_tracks": len(audio),
        "audio": [
            {
                "codec": a.get("codec_name"),
                "channels": a.get("channels"),
                "language": (a.get("tags") or {}).get("language"),
                "title": (a.get("tags") or {}).get("title"),
            }
            for a in audio
        ],
        "subtitle_tracks": len(subs),
        "size_bytes": path.stat().st_size,
    }


def _hms(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def _grab(path, timestamp, out):
    """One frame, scaled and padded to a uniform size so it can be tiled.

    -ss before -i is input seeking: near-instant even on a 20 GB file, because
    it never decodes the frames it skips.
    """
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-ss", f"{timestamp:.2f}",
            "-i", str(path),
            "-frames:v", "1",
            "-vf",
            f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease,"
            f"pad={THUMB_W}:{THUMB_H}:(ow-iw)/2:(oh-ih)/2",
            str(out),
        ],
        capture_output=True,
        check=False,
    )
    return out.exists()


def _sheet(path, timestamps, grid, out):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        kept = 0
        for stamp in timestamps:
            target = tmp / f"f{kept:03d}.png"
            if _grab(path, stamp, target):
                kept += 1
        if not kept:
            return False
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-framerate", "1",
                "-i", str(tmp / "f%03d.png"),
                "-vf", f"tile={grid}",
                "-frames:v", "1",
                str(out),
            ],
            capture_output=True,
            check=False,
        )
    return out.exists()


def contact_sheets(path, seconds, out_dir):
    """A head sheet for the title card and a scan sheet for the content."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    made = {}

    head_span = min(HEAD_WINDOW, max(seconds - 1, 1))
    head = [head_span * i / HEAD_FRAMES for i in range(HEAD_FRAMES)]
    head_out = out_dir / f"{stem}--head.png"
    if _sheet(path, head, HEAD_GRID, head_out):
        made["head"] = head_out.name

    # Skip the first and last few percent: leader black and trailing black
    # waste tiles that could be showing content.
    scan = [seconds * (0.02 + 0.96 * i / (SCAN_FRAMES - 1)) for i in range(SCAN_FRAMES)]
    scan_out = out_dir / f"{stem}--scan.png"
    if _sheet(path, scan, SCAN_GRID, scan_out):
        made["scan"] = scan_out.name

    return made


def have_tools():
    return all(shutil.which(t) for t in ("ffprobe", "ffmpeg"))
