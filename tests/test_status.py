"""disc-status counts what disc-transcode will actually transcode.

It counted every feature and extra, named or not, while disc-transcode skips
an item review left without a name. A disc in that state showed a transcode
count that could never complete.
"""

import json

from discpipe import manifest, plan as planlib


def write_plan(root, items):
    rip = root / "a-disc"
    rip.mkdir()
    (rip / "plan.json").write_text(json.dumps({"items": items}))
    return rip


def test_an_unnamed_feature_is_not_waiting_to_be_transcoded(script, root):
    status = script("disc-status")
    rip = write_plan(root, [
        {"file": "a.mkv", "action": "feature", "new_name": "Film (1997).mkv",
         "transcode": {"status": "done"}},
        {"file": "b.mkv", "action": "feature", "new_name": ""},
    ])

    assert status._progress(rip, {}, manifest.APPLIED) == "1/1 transcoded"


def test_a_declined_item_is_not_counted(script, root):
    status = script("disc-status")
    rip = write_plan(root, [
        {"file": "a.mkv", "action": "feature", "new_name": "Film (1997).mkv"},
        {"file": "b.mkv", "action": "extra", "new_name": "Trailer-trailer.mkv",
         "decision": planlib.DECLINE},
    ])

    assert status._progress(rip, {}, manifest.APPLIED) == "0/1 transcoded"


def test_a_review_hold_points_at_disc_apply(script, root):
    status = script("disc-status")
    slug = "men-in-black-ii-b23680"
    manifest.save(manifest.new(slug, "fp", "MEN_IN_BLACK_II", "bluray"))
    (root / slug / "plan.json").write_text(json.dumps({"items": []}))
    manifest.hold(manifest.load(slug), "needs review: 1 item(s)", stage="apply")

    row = status._queue_row(root / slug)

    assert row["needs_you"] is True
    assert row["command"] == f"disc-apply {slug}"
