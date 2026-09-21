"""A decode check reports on the decoders, not on the muxer it writes into."""

import subprocess

import pytest

from discpipe import verify

MUXER = ("[null @ 0x7fcee88156c0] Application provided invalid, non "
         "monotonically increasing dts to muxer in stream 0: 4 >= 4")
DECODER = "[mpeg2video @ 0x7f8851309e80] ac-tex damaged at 12 7"


def stub_ffmpeg(monkeypatch, stderr, returncode=0):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode, stdout="",
                                           stderr=stderr)
    monkeypatch.setattr(verify.subprocess, "run", fake_run)


def test_muxer_timestamp_complaints_are_not_decode_errors(monkeypatch, tmp_path):
    """DVD MPEG-2 emits thousands of these on a perfectly good rip."""
    stub_ffmpeg(monkeypatch, "\n".join([MUXER] * 11754))

    ok, errors = verify.decode(tmp_path / "movie.mkv")

    assert ok is True
    assert errors == []


def test_decoder_errors_still_fail(monkeypatch, tmp_path):
    stub_ffmpeg(monkeypatch, "\n".join([MUXER, DECODER, MUXER]))

    ok, errors = verify.decode(tmp_path / "movie.mkv")

    assert ok is False
    assert errors == [DECODER]


def test_a_nonzero_exit_fails_even_with_no_error_lines(monkeypatch, tmp_path):
    stub_ffmpeg(monkeypatch, "", returncode=1)

    ok, errors = verify.decode(tmp_path / "movie.mkv")

    assert ok is False


@pytest.mark.parametrize("line", [MUXER, "", "   "])
def test_nothing_reportable_reads_as_clean(monkeypatch, tmp_path, line):
    stub_ffmpeg(monkeypatch, line)

    ok, errors = verify.decode(tmp_path / "movie.mkv")

    assert (ok, errors) == (True, [])
