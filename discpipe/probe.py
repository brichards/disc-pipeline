"""Read the streams of a ripped file, and make its contact sheets.

The contact sheets go to the agent of disc-identify. Other stages use ffprobe()
to read the runtime, the size or the height of a file.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from . import notify

HEAD_FRAMES = 25
HEAD_GRID = "5x5"
HEAD_WINDOW = 75.0
SCAN_FRAMES = 16
SCAN_GRID = "4x4"

THUMB_W = 320
THUMB_H = 180


def ffprobe(path):
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
        "duration": notify.human_duration(seconds),
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


def _ffmpeg(args, out):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args, str(out)],
        capture_output=True,
        check=False,
    )
    return out.exists()


def _grab(path, timestamp, out):
    """With -ss before -i, ffmpeg does not decode the frames that it skips.

    Thus the seek is fast, also in a 20 GB file.
    """
    return _ffmpeg([
        "-ss", f"{timestamp:.2f}",
        "-i", str(path),
        "-frames:v", "1",
        "-vf",
        f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease,"
        f"pad={THUMB_W}:{THUMB_H}:(ow-iw)/2:(oh-ih)/2",
    ], out)


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
        return _ffmpeg([
            "-framerate", "1",
            "-i", str(tmp / "f%03d.png"),
            "-vf", f"tile={grid}",
            "-frames:v", "1",
        ], out)


def contact_sheets(path, seconds, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    made = {}

    head_span = min(HEAD_WINDOW, max(seconds - 1, 1))
    head = [head_span * i / HEAD_FRAMES for i in range(HEAD_FRAMES)]
    head_out = out_dir / f"{stem}--head.png"
    if _sheet(path, head, HEAD_GRID, head_out):
        made["head"] = head_out.name

    scan = [seconds * (0.02 + 0.96 * i / (SCAN_FRAMES - 1)) for i in range(SCAN_FRAMES)]
    scan_out = out_dir / f"{stem}--scan.png"
    if _sheet(path, scan, SCAN_GRID, scan_out):
        made["scan"] = scan_out.name

    return made
