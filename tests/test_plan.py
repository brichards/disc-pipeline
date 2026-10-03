"""Which items survived review, and under what name.

disc-ship and disc-transcode each spelled this filter out, and a mismatch
between them would ship a file that was never transcoded.
"""

from discpipe import plan as planlib


def test_kept_skips_rejected_and_undecided_items():
    """A declined item keeps its proposed name in the plan; it is not kept."""
    plan = {"items": [
        {"file": "a.mkv", "action": "feature", "new_name": "Film (1997).mkv"},
        {"file": "b.mkv", "action": "extra", "new_name": "Trailer-trailer.mkv"},
        {"file": "c.mkv", "action": "feature", "new_name": "Nope.mkv",
         "decision": planlib.DECLINE},
        {"file": "d.mkv", "action": "reject", "new_name": ""},
        {"file": "e.mkv", "action": "unknown"},
    ]}

    assert [n for _, _, n in planlib.kept(plan)] == [
        "Film (1997).mkv", "Trailer-trailer.mkv"]


def test_kept_drops_an_item_review_left_without_a_name():
    plan = {"items": [{"file": "a.mkv", "action": "feature", "new_name": ""}]}

    assert list(planlib.kept(plan)) == []


def test_kept_reports_the_action_alongside_the_name():
    plan = {"items": [
        {"file": "a.mkv", "action": "feature", "new_name": "Film (1997).mkv"},
        {"file": "b.mkv", "action": "extra", "new_name": "Trailer-trailer.mkv"},
    ]}

    assert [a for _, a, _ in planlib.kept(plan)] == [
        planlib.FEATURE, planlib.EXTRA]


def test_kept_tolerates_a_plan_with_no_items():
    assert list(planlib.kept({})) == []


def test_outcome_gives_a_name_only_to_what_is_kept():
    """kept() leans on this: anything else comes back with no name at all."""
    for action in (planlib.REJECT, planlib.UNKNOWN):
        item = {"file": "a.mkv", "action": action, "new_name": "Film.mkv"}
        assert planlib.outcome(item)[1] == ""

    declined = {"file": "a.mkv", "action": planlib.FEATURE,
                "new_name": "Film.mkv", "decision": planlib.DECLINE}
    assert planlib.outcome(declined) == (planlib.REJECT, "")
