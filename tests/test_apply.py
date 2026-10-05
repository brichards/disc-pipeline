"""A plan disc-apply --auto will not apply is held for review.

It used to exit with the disc still identified, so the drainer offered it again
every 30 seconds -- 20 times in a row for one disc.
"""

import json

from discpipe import manifest

SLUG = "men-in-black-ii-b23680"


def identified_disc(root, items):
    manifest.save(manifest.new(SLUG, "fp", "MEN_IN_BLACK_II", "bluray"))
    manifest.advance_slug(SLUG, manifest.IDENTIFIED)
    (root / SLUG / "plan.json").write_text(json.dumps({"items": items}))


def test_an_auto_refusal_holds_the_disc_for_review(script, root, monkeypatch):
    apply = script("disc-apply")
    identified_disc(root, [
        {"file": "a.mkv", "action": "feature", "new_name": "Film (2002).mkv",
         "confidence": "high"},
        {"file": "b.mkv", "action": "extra", "new_name": "Trailer-trailer.mkv",
         "confidence": "medium"},
    ])
    monkeypatch.setattr("sys.argv", ["disc-apply", SLUG, "--auto"])

    assert apply.main() == 1

    data = manifest.load(SLUG)
    assert data["state"] == manifest.HELD
    assert data["held_reason"].startswith("needs review: 1 item(s)")
    assert data["held_retryable"] is False
    assert data["held_stage"] == "apply"
