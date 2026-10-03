"""Frame extraction reports success by whether the file appeared.

ffmpeg exits zero on inputs it could not usefully read, so the exit code is
not the signal -- an empty contact sheet would otherwise reach the agent.
"""

import subprocess

from discpipe import probe


def stub_ffmpeg(monkeypatch, creates=None):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        if creates is not None:
            creates.write_bytes(b"png")
        return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    return seen


def test_a_missing_output_reads_as_failure_despite_a_clean_exit(monkeypatch, tmp_path):
    out = tmp_path / "frame.png"
    stub_ffmpeg(monkeypatch)

    assert probe._ffmpeg(["-i", "movie.mkv"], out) is False


def test_a_written_output_reads_as_success(monkeypatch, tmp_path):
    out = tmp_path / "frame.png"
    stub_ffmpeg(monkeypatch, creates=out)

    assert probe._ffmpeg(["-i", "movie.mkv"], out) is True


def test_the_command_is_quiet_and_ends_at_the_output(monkeypatch, tmp_path):
    out = tmp_path / "frame.png"
    seen = stub_ffmpeg(monkeypatch, creates=out)

    probe._ffmpeg(["-i", "movie.mkv", "-frames:v", "1"], out)

    assert seen["argv"][:4] == ["ffmpeg", "-v", "error", "-y"]
    assert seen["argv"][-1] == str(out)


def test_grab_seeks_before_the_input(monkeypatch, tmp_path):
    """-ss after -i decodes everything it skips; on a 20 GB file that is minutes."""
    out = tmp_path / "frame.png"
    seen = stub_ffmpeg(monkeypatch, creates=out)

    probe._grab("movie.mkv", 42.0, out)

    argv = seen["argv"]
    assert argv.index("-ss") < argv.index("-i")
