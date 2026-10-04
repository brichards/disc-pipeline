"""MakeMKV title numbers are positions in an enumeration --minlength decides.

A scan at 240s and a rip at MakeMKV's own default of 300s number the titles
differently, so the index that scan reported addresses a different title by the
time the rip runs.
"""

import subprocess

from discpipe import config, makemkv


def capture_scan(monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(makemkv.subprocess, "run", fake_run)
    return seen


def capture_rip(monkeypatch, lines=()):
    seen = {}

    def fake_stream(command, on_line=None, cwd=None):
        seen["argv"] = command
        for line in lines:
            if on_line:
                on_line(line)
        return 0

    monkeypatch.setattr(makemkv.proc, "stream", fake_stream)
    return seen


def minlength_of(argv):
    for arg in argv:
        if arg.startswith("--minlength="):
            return int(arg.split("=", 1)[1])
    return None


def test_scan_and_rip_use_the_same_minimum_length(monkeypatch, tmp_path):
    scanned = capture_scan(monkeypatch)
    makemkv.scan(disc=0, min_length=240)

    ripped = capture_rip(monkeypatch)
    makemkv.rip(0, 1, tmp_path / "raw", min_length=240)

    assert minlength_of(scanned["argv"]) == 240
    assert minlength_of(ripped["argv"]) == 240


def test_rip_requires_a_minimum_length(monkeypatch, tmp_path):
    """Omitting it silently falls back to MakeMKV's default and shifts indices."""
    capture_rip(monkeypatch)

    try:
        makemkv.rip(0, 1, tmp_path / "raw")
    except TypeError:
        return
    raise AssertionError("rip() accepted a call with no min_length")


def test_scan_defaults_to_the_configured_minimum(monkeypatch):
    scanned = capture_scan(monkeypatch)
    makemkv.scan()

    assert minlength_of(scanned["argv"]) == config.MIN_TITLE_LENGTH


def test_rip_collects_the_read_problems_makemkv_works_around(monkeypatch, tmp_path):
    """A clean exit code is not a clean rip -- Men in Black exited zero."""
    corrupt = ("The source file '/VIDEO_TS/VTS_07_1.VOB' is corrupt or invalid "
               "at offset 36864, attempting to work around")
    capture_rip(monkeypatch, lines=[
        f'MSG:2003,0,3,"{corrupt}","x","y"',
        'MSG:5036,0,1,"Copy complete. 1 titles saved.","x","y"',
    ])

    code, warnings, transcript = makemkv.rip(0, 1, tmp_path / "raw", min_length=240)

    assert code == 0
    assert warnings == [corrupt]
    assert "Copy complete. 1 titles saved." in transcript


def test_rip_keeps_a_quiet_run_free_of_warnings(monkeypatch, tmp_path):
    capture_rip(monkeypatch, lines=['MSG:5036,0,1,"Copy complete.","x","y"'])

    _, warnings, transcript = makemkv.rip(0, 1, tmp_path / "raw", min_length=240)

    assert warnings == []
    assert transcript == "Copy complete."
