"""disc-cleanup is the only code here that deletes anything."""

import json

from discpipe import manifest


def make_disc(root, slug="movie-abc123"):
    folder = root / slug
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps({
        "slug": slug, "state": manifest.SHIPPED, "fingerprint": "f" * 64,
    }))
    return folder


def test_refuses_a_path_outside_the_queue_root(root, script, tmp_path):
    """Carries a manifest, so only the root check can refuse it."""
    cleanup = script("disc-cleanup")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "manifest.json").write_text("{}")

    refusal = cleanup._refuse(outside)

    assert refusal is not None
    assert "outside" in refusal


def test_refuses_the_queue_root_itself(root, script):
    cleanup = script("disc-cleanup")

    assert cleanup._refuse(root) is not None


def test_refuses_a_symlink_pointing_out_of_the_root(root, script, tmp_path):
    """resolve() follows the link, so the target is what gets checked."""
    cleanup = script("disc-cleanup")
    library = tmp_path / "library"
    library.mkdir()
    (library / "manifest.json").write_text("{}")
    escape = root / "looks-local"
    escape.symlink_to(library)

    refusal = cleanup._refuse(escape)

    assert refusal is not None
    assert "outside" in refusal


def test_refuses_a_directory_the_pipeline_did_not_build(root, script):
    cleanup = script("disc-cleanup")
    stranger = root / "someone-elses-folder"
    stranger.mkdir()

    assert cleanup._refuse(stranger) is not None


def test_allows_a_disc_folder_and_its_contents(root, script):
    cleanup = script("disc-cleanup")
    folder = make_disc(root)
    raw = folder / "raw"
    raw.mkdir()

    assert cleanup._refuse(folder) is None
    assert cleanup._refuse(raw) is None


def test_delete_refuses_rather_than_raising(root, script, tmp_path):
    """A refusal returns zero bytes freed and leaves the path alone."""
    cleanup = script("disc-cleanup")
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "file.mkv").write_bytes(b"x" * 10)

    assert cleanup._delete(outside, 10) == 0
    assert outside.exists()


def test_a_folder_that_will_not_delete_goes_back_to_shipped(root, script,
                                                            monkeypatch):
    """"done" must never describe a disc whose folder is still on disk."""
    cleanup = script("disc-cleanup")
    folder = make_disc(root)
    data = manifest.load(folder.name)
    nas = root / "nas"
    nas.mkdir()
    entry = {
        "name": folder.name, "slug": folder.name, "root": folder,
        "source": folder / "raw", "transcoded": folder / "transcoded",
        "destination": nas, "manifest": data, "auto_applied": False,
    }

    monkeypatch.setattr(cleanup, "_ask", lambda question: True)
    monkeypatch.setattr(cleanup, "_delete", lambda path, size: 0)

    class Args:
        dry_run = False

    freed = cleanup._offer_remainder(entry, Args())

    assert freed == 0
    assert manifest.load(folder.name)["state"] == manifest.SHIPPED
