"""Advancing a disc by slug reads it back from disk first.

Three stages advance a disc they no longer hold in memory, after other writes
have landed. Advancing a stale copy would discard those writes.
"""

from discpipe import manifest


def test_advance_slug_lands_the_state_on_disk(root):
    data = manifest.new("a-disc", "fingerprint", "A DISC", "dvd")
    manifest.save(data)

    manifest.advance_slug("a-disc", manifest.APPLIED)

    assert manifest.load("a-disc")["state"] == manifest.APPLIED


def test_advance_slug_keeps_writes_it_did_not_make(root):
    """The in-memory copy a stage still holds is stale by this point."""
    stale = manifest.new("a-disc", "fingerprint", "A DISC", "dvd")
    manifest.save(stale)
    fresh = manifest.load("a-disc")
    fresh["rip"] = {"verified": True}
    manifest.save(fresh)

    manifest.advance_slug("a-disc", manifest.APPLIED)

    written = manifest.load("a-disc")
    assert written["state"] == manifest.APPLIED
    assert written["rip"] == {"verified": True}


def test_advance_slug_clears_a_hold(root):
    data = manifest.new("a-disc", "fingerprint", "A DISC", "dvd")
    manifest.save(data)
    manifest.hold(manifest.load("a-disc"), "something broke", stage="rip")

    manifest.advance_slug("a-disc", manifest.APPLIED)

    assert manifest.load("a-disc")["held_reason"] is None


def test_queue_dirs_skips_files_and_dotfiles(root):
    (root / "a-disc").mkdir()
    (root / "b-disc").mkdir()
    (root / ".DS_Store").write_bytes(b"")
    (root / "ledger.jsonl").write_text("")
    (root / ".hidden-dir").mkdir()

    assert [p.name for p in manifest.queue_dirs()] == ["a-disc", "b-disc"]


def test_queue_dirs_is_empty_when_the_root_does_not_exist(root, monkeypatch):
    """disc-cleanup walked the root without checking; a fresh Mac has none."""
    monkeypatch.setattr(manifest.config, "ROOT", root / "nowhere")

    assert manifest.queue_dirs() == []


def test_find_returns_none_for_a_disc_with_no_manifest(root):
    assert manifest.find("never-ripped") is None


def test_find_returns_none_for_a_manifest_cut_off_mid_write(root):
    """What a crash during a non-atomic save left behind."""
    (root / "a-disc").mkdir()
    (root / "a-disc" / "manifest.json").write_text('{"state": "rip')

    assert manifest.find("a-disc") is None


def test_find_returns_a_readable_manifest(root):
    manifest.save(manifest.new("a-disc", "fingerprint", "A DISC", "dvd"))

    assert manifest.find("a-disc")["label"] == "A DISC"


def test_one_unreadable_manifest_does_not_hide_the_rest(root):
    manifest.save(manifest.new("a-disc", "fp-a", "A DISC", "dvd"))
    (root / "b-disc").mkdir()
    (root / "b-disc" / "manifest.json").write_text("{")
    manifest.save(manifest.new("c-disc", "fp-c", "C DISC", "dvd"))

    assert [d["slug"] for d in manifest.all_discs()] == ["a-disc", "c-disc"]
