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
