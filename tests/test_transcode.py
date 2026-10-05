"""A transcode that does not finish must not leave a file under the final name.

The transcoders write straight into their working directory. Killed partway,
the truncated file used to keep the final name, and the next run took it for
finished and shipped it.
"""

from argparse import Namespace
from pathlib import Path

import pytest

from discpipe import transcode


def fake_transcoder(monkeypatch, exit_code=0, writes=b"complete"):
    """Behaves like transcode-video.rb: writes into cwd, refuses an existing file."""
    seen = {}

    def stream(command, on_line=None, cwd=None):
        seen["cwd"] = Path(cwd)
        out = Path(cwd) / (Path(command[1]).stem + ".mkv")
        if out.exists():
            return 1
        out.write_bytes(writes)
        return exit_code

    monkeypatch.setattr(transcode.proc, "stream", stream)
    return seen


@pytest.fixture
def disc(tmp_path):
    source = tmp_path / "raw" / "Film (1997).mkv"
    source.parent.mkdir()
    source.write_bytes(b"source")
    out_dir = tmp_path / "transcoded"
    return source, out_dir, transcode.staging_for(tmp_path)


def test_a_finished_transcode_lands_under_its_final_name(monkeypatch, disc):
    source, out_dir, staging = disc
    fake_transcoder(monkeypatch)

    code, destination = transcode.run(source, out_dir, "transcode-video.rb", staging)

    assert code == 0
    assert destination.read_bytes() == b"complete"
    assert not staging.exists()


def test_a_killed_transcode_leaves_nothing_under_the_final_name(monkeypatch, disc):
    source, out_dir, staging = disc
    fake_transcoder(monkeypatch, exit_code=-15, writes=b"truncat")

    code, destination = transcode.run(source, out_dir, "transcode-video.rb", staging)

    assert code == -15
    assert not destination.exists()
    assert not staging.exists()


def test_a_partial_left_by_a_killed_run_does_not_block_the_next(monkeypatch, disc):
    """The transcoder would refuse to start over a file it finds in its way."""
    source, out_dir, staging = disc
    staging.mkdir(parents=True)
    (staging / "Film (1997).mkv").write_bytes(b"truncat")
    fake_transcoder(monkeypatch)

    code, destination = transcode.run(source, out_dir, "transcode-video.rb", staging)

    assert code == 0
    assert destination.read_bytes() == b"complete"


def test_redo_replaces_a_finished_output(monkeypatch, disc):
    """Pointed at the output directory, the transcoder refused, and --redo failed."""
    source, out_dir, staging = disc
    out_dir.mkdir()
    (out_dir / "Film (1997).mkv").write_bytes(b"old")
    fake_transcoder(monkeypatch)

    code, destination = transcode.run(source, out_dir, "transcode-video.rb", staging)

    assert code == 0
    assert destination.read_bytes() == b"complete"


def test_an_interrupted_copy_leaves_nothing_under_the_final_name(monkeypatch, disc):
    """The copy is the fallback when a hard link crosses filesystems."""
    source, out_dir, staging = disc

    def no_link(src, dst):
        raise OSError("cross-device link")

    def half_copy(src, dst):
        Path(dst).write_bytes(b"sou")
        raise OSError("No space left on device")

    monkeypatch.setattr(transcode.os, "link", no_link)
    monkeypatch.setattr(transcode.shutil, "copy2", half_copy)

    with pytest.raises(OSError):
        transcode.adopt_encoded(source, out_dir, staging)

    assert not transcode.output_for(source, out_dir).exists()


def test_a_finished_copy_lands_under_its_final_name(monkeypatch, disc):
    source, out_dir, staging = disc

    def no_link(src, dst):
        raise OSError("cross-device link")

    monkeypatch.setattr(transcode.os, "link", no_link)

    destination = transcode.adopt_encoded(source, out_dir, staging)

    assert destination.read_bytes() == b"source"
    assert not staging.exists()


def test_disc_transcode_runs_the_transcoder_in_staging(monkeypatch, script, tmp_path):
    stage = script("disc-transcode")
    seen = fake_transcoder(monkeypatch)
    source = tmp_path / "raw" / "Film (1997).mkv"
    source.parent.mkdir()
    source.write_bytes(b"source")
    out_dir = tmp_path / "transcoded" / "Film (1997)"
    item = {"file": "Film-00.mkv", "new_name": "Film (1997).mkv"}
    todo = [({"item": item}, source, "transcode-video.rb", {"height": 1080})]

    failures = stage._transcode_all(todo, out_dir, {"items": [item]}, tmp_path,
                                    Namespace(quiet=True))

    assert failures == 0
    assert (out_dir / "Film (1997).mkv").read_bytes() == b"complete"
    assert seen["cwd"] == transcode.staging_for(tmp_path)


def test_disc_ship_never_takes_staging_for_the_movie(script, tmp_path):
    """Staging sits in transcoded/, so it must be somewhere disc-ship looks past."""
    ship = script("disc-ship")
    staging = transcode.staging_for(tmp_path)
    staging.mkdir(parents=True)
    (staging / "Trailer-trailer.mkv").write_bytes(b"truncat")
    feature = tmp_path / "transcoded" / "Film (1997).mkv"
    feature.write_bytes(b"complete")

    assert ship._source(tmp_path) == feature
