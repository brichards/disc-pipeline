"""Driving makemkvcon and parsing its robot-mode output.

Robot mode emits one record per line:

    TINFO:<title>,<attr>,<code>,"<value>"
    SINFO:<title>,<stream>,<attr>,<code>,"<value>"
    MSG:<code>,<flags>,<count>,"<rendered>","<format>",<params...>

The attribute numbers below were read off real output from a RED 2 disc rather
than taken from documentation, because they are not stable enough to guess.
"""

import re
import subprocess
from dataclasses import dataclass, field

from . import config

# TINFO attributes.
T_NAME = 2
T_CHAPTERS = 8
T_DURATION = 9
T_SIZE_HUMAN = 10
T_SIZE_BYTES = 11
T_SOURCE_FILE = 16  # the .mpls (Blu-ray) or .m2ts backing this title
T_SEGMENT_COUNT = 25
T_SEGMENT_MAP = 26
T_OUTPUT_NAME = 27

# SINFO attributes.
S_TYPE = 1  # "Video" / "Audio" / "Subtitles"
S_LAYOUT = 2  # "Surround 7.1"
S_LANG = 3
S_CODEC = 6
S_CHANNELS = 14
S_RESOLUTION = 19
S_FRAMERATE = 21
S_NAME = 30

_TINFO = re.compile(r'^TINFO:(\d+),(\d+),\d+,"(.*)"$')
_SINFO = re.compile(r'^SINFO:(\d+),(\d+),(\d+),\d+,"(.*)"$')
_DRV = re.compile(r'^DRV:\d+,(\d+),\d+,\d+,"([^"]*)","([^"]*)","([^"]*)"$')
_MSG = re.compile(r'^MSG:(\d+),\d+,\d+,"(.*?)",')

# MakeMKV reports a bad read, works around it, and still exits zero. Match on
# text rather than message codes -- the codes vary by failure mode, the wording
# does not.
_TROUBLE = re.compile(
    r"corrupt|invalid|work around|read error|failed to (open|read|save)"
    r"|hash (check|mismatch)|scsi error",
    re.IGNORECASE,
)


def parse_duration(text):
    parts = [int(p) for p in text.split(":") if p != ""]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


@dataclass
class Stream:
    kind: str = ""
    codec: str = ""
    lang: str = ""
    channels: str = ""
    layout: str = ""
    resolution: str = ""
    name: str = ""


@dataclass
class Title:
    index: int
    name: str = ""
    chapters: int = 0
    seconds: int = 0
    duration: str = ""
    size_bytes: int = 0
    source_file: str = ""
    segment_count: int = 0
    segment_map: str = ""
    output_name: str = ""
    streams: list = field(default_factory=list)

    @property
    def segments(self):
        return [int(s) for s in self.segment_map.split(",") if s.strip().isdigit()]

    @property
    def audio(self):
        return [s for s in self.streams if s.kind == "Audio"]

    @property
    def subtitles(self):
        return [s for s in self.streams if s.kind == "Subtitles"]

    @property
    def resolution(self):
        for s in self.streams:
            if s.kind == "Video" and s.resolution:
                return s.resolution
        return ""

    @property
    def height(self):
        if "x" in self.resolution:
            try:
                return int(self.resolution.split("x")[1])
            except ValueError:
                return 0
        return 0

    def stream_signature(self):
        """Identifies titles carrying the same tracks. Decoy playlists on an
        obfuscated disc are usually indistinguishable by this."""
        return "|".join(
            f"{s.kind}/{s.codec}/{s.lang}/{s.channels}" for s in self.streams
        )


@dataclass
class DiscInfo:
    label: str = ""
    device: str = ""
    titles: list = field(default_factory=list)
    messages: list = field(default_factory=list)

    @property
    def warnings(self):
        return [m for m in self.messages if _TROUBLE.search(m)]


def parse(text):
    """Turn a robot-mode dump into a DiscInfo. Pure -- no subprocess, so it can
    be pointed at a saved dump for testing."""
    titles = {}
    streams = {}
    info = DiscInfo()

    for line in text.splitlines():
        line = line.rstrip("\n")

        match = _TINFO.match(line)
        if match:
            tid, attr, value = int(match.group(1)), int(match.group(2)), match.group(3)
            titles.setdefault(tid, {})[attr] = value
            continue

        match = _SINFO.match(line)
        if match:
            tid, sid, attr = int(match.group(1)), int(match.group(2)), int(match.group(3))
            streams.setdefault(tid, {}).setdefault(sid, {})[attr] = match.group(4)
            continue

        match = _DRV.match(line)
        if match and match.group(3):
            info.label = match.group(3)
            info.device = match.group(4)
            continue

        match = _MSG.match(line)
        if match:
            info.messages.append(match.group(2))

    for tid in sorted(titles):
        attrs = titles[tid]
        title = Title(
            index=tid,
            name=attrs.get(T_NAME, ""),
            chapters=int(attrs.get(T_CHAPTERS, 0) or 0),
            seconds=parse_duration(attrs.get(T_DURATION, "0:00:00")),
            duration=attrs.get(T_DURATION, ""),
            size_bytes=int(attrs.get(T_SIZE_BYTES, 0) or 0),
            source_file=attrs.get(T_SOURCE_FILE, ""),
            segment_count=int(attrs.get(T_SEGMENT_COUNT, 0) or 0),
            segment_map=attrs.get(T_SEGMENT_MAP, ""),
            output_name=attrs.get(T_OUTPUT_NAME, ""),
        )
        for sid in sorted(streams.get(tid, {})):
            sattrs = streams[tid][sid]
            title.streams.append(
                Stream(
                    kind=sattrs.get(S_TYPE, ""),
                    codec=sattrs.get(S_CODEC, ""),
                    lang=sattrs.get(S_LANG, ""),
                    channels=sattrs.get(S_CHANNELS, ""),
                    layout=sattrs.get(S_LAYOUT, ""),
                    resolution=sattrs.get(S_RESOLUTION, ""),
                    name=sattrs.get(S_NAME, ""),
                )
            )
        info.titles.append(title)

    return info


def scan(disc=0, min_length=config.MIN_TITLE_LENGTH):
    """Enumerate titles. Returns (DiscInfo, raw_output)."""
    result = subprocess.run(
        [
            str(config.MAKEMKVCON),
            "-r",
            "--cache=1",
            f"--minlength={min_length}",
            "info",
            f"disc:{disc}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return parse(result.stdout), result.stdout


def rip(disc, title_index, out_dir, min_length, on_line=None):
    """Rip one title, streaming output so trouble is caught as it happens.

    Returns (exit_code, warnings, transcript). A zero exit code is not
    sufficient: MakeMKV works around unreadable sectors and still reports
    success, which yields a glitched file and no error. Callers must check the
    warnings list. The transcript is kept so a failure can be diagnosed without
    re-reading the disc.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            str(config.MAKEMKVCON),
            "-r",
            "--noscan",
            f"--minlength={min_length}",
            "mkv",
            f"disc:{disc}",
            str(title_index),
            str(out_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    warnings = []
    transcript = []
    for line in process.stdout:
        line = line.rstrip()
        match = _MSG.match(line)
        rendered = match.group(2) if match else line
        transcript.append(rendered)
        if _TROUBLE.search(rendered):
            warnings.append(rendered)
        if on_line:
            on_line(rendered)
    process.wait()

    return process.returncode, warnings, "\n".join(transcript)
