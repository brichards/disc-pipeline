"""A stage acts only on a disc folder in the queue.

Adopting a folder outside the queue moved its media into its own raw/ and
wrote its manifest into the queue, so neither half could find the other.
"""

import pytest

from discpipe import plan as planlib


def loose_folder(parent, name="My Movie"):
    folder = parent / name
    folder.mkdir(parents=True)
    (folder / "title_t00.mkv").write_bytes(b"x")
    return folder


def contents(path):
    return sorted(p.relative_to(path) for p in path.rglob("*"))


@pytest.mark.parametrize("where", ["outside", "inside a disc folder"])
def test_a_folder_that_is_not_a_disc_folder_is_refused(root, tmp_path, where):
    parent = tmp_path / "elsewhere" if where == "outside" else root / "sample-f49b43"
    folder = loose_folder(parent)
    before = contents(tmp_path)

    with pytest.raises(SystemExit):
        planlib.resolve_target(str(folder))

    assert contents(tmp_path) == before


def test_a_loose_folder_in_the_queue_is_adopted(root):
    folder = loose_folder(root)

    assert planlib.resolve_target(str(folder)) == folder
    assert (folder / "raw" / "title_t00.mkv").exists()
    assert (folder / "manifest.json").exists()
