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


def capture_rip(monkeypatch):
    seen = {}

    class FakeProcess:
        stdout = iter(())
        returncode = 0

        def wait(self):
            return 0

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        return FakeProcess()

    monkeypatch.setattr(makemkv.subprocess, "Popen", fake_popen)
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
