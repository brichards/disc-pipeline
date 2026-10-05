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


def test_a_rip_with_unverified_read_errors_is_flagged_before_review(script, root, capsys):
    """This path raised NameError from 2026-08-24, on exactly the discs it exists to warn about."""
    apply = script("disc-apply")
    data = manifest.new(SLUG, "fp", "AP_MAN_OF_MYSTERY_BD01", "bluray")
    data["rip"] = {"suspect": True}
    data["titles"] = [
        {"index": 0, "duration": "1:29:35", "output_name": "00.mkv",
         "rip": {"warnings": ["read error"] * 161}},
        {"index": 1, "duration": "0:04:58", "output_name": "01.mkv", "rip": {}},
    ]
    manifest.save(data)

    apply._suspect_warning(SLUG)

    out = capsys.readouterr().out
    assert "read errors that MakeMKV worked around" in out
    assert "title 0  1:29:35  00.mkv  (161 error(s))" in out
    assert "title 1" not in out
