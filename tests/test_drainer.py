"""The drainer relaunched any stage that failed without changing its disc,
every 30 seconds, and never went idle."""

from argparse import Namespace

import pytest

from discpipe import locks, manifest

SLUG = "men-in-black-ii-b23680"


@pytest.fixture
def drainer(script, root, monkeypatch):
    run = script("disc-run")
    launched = []
    monkeypatch.setattr(run, "_unqueued_disc", lambda: False)
    monkeypatch.setattr(run, "_launch", lambda running, slug, stage, *rest:
                        launched.append(stage) or True)
    clock = {"now": 1000.0}
    monkeypatch.setattr(run.time, "time", lambda: clock["now"])
    return run, launched, clock


def disc_in(state, **hold):
    data = manifest.new(SLUG, "fp", "MEN_IN_BLACK_II", "bluray")
    manifest.save(data)
    if state == manifest.HELD:
        manifest.hold(manifest.load(SLUG), "held", **hold)
    else:
        manifest.advance_slug(SLUG, state)


class Finished:
    def __init__(self, code):
        self.returncode = code

    def poll(self):
        return self.returncode


def test_a_failure_is_recorded_against_the_discs_state(drainer):
    run, _, _ = drainer
    disc_in(manifest.APPLIED)
    failed = {}

    run._reap({SLUG: ("disc-transcode", locks.CPU, Finished(1))}, failed)

    assert failed == {SLUG: ("disc-transcode", manifest.APPLIED)}


def test_a_success_is_not_recorded_as_a_failure(drainer):
    run, _, _ = drainer
    disc_in(manifest.APPLIED)
    failed = {}

    run._reap({SLUG: ("disc-transcode", locks.CPU, Finished(0))}, failed)

    assert failed == {}


def test_a_failed_stage_waits_until_its_disc_moves(drainer):
    run, launched, _ = drainer
    disc_in(manifest.APPLIED)
    failed = {SLUG: ("disc-transcode", manifest.APPLIED)}

    run._pass({}, failed, {}, Namespace())
    assert launched == []

    manifest.advance_slug(SLUG, manifest.TRANSCODED)
    run._pass({}, failed, {}, Namespace())
    assert launched == ["disc-ship"]


def test_a_retryable_hold_is_retried_every_ten_minutes(drainer):
    run, launched, clock = drainer
    disc_in(manifest.HELD, retryable=True, stage="rip")
    tried = {}

    run._pass({}, {}, tried, Namespace())
    clock["now"] += 300
    run._pass({}, {}, tried, Namespace())
    clock["now"] += 301
    run._pass({}, {}, tried, Namespace())

    assert launched == ["disc-rip", "disc-rip"]


def test_the_session_stays_open_while_a_hold_waits_to_be_retried(drainer):
    run, launched, _ = drainer
    disc_in(manifest.HELD, retryable=True, stage="ship")

    started, waiting = run._pass({}, {}, {SLUG: 1000.0}, Namespace())

    assert (started, waiting) == (0, 1)


def test_a_disc_waiting_on_you_does_not_keep_the_session_open(drainer):
    """A review hold needs a person; the drainer may go idle and let the Mac sleep."""
    run, launched, _ = drainer
    disc_in(manifest.HELD, stage="apply")

    started, waiting = run._pass({}, {}, {}, Namespace())

    assert (started, waiting, launched) == (0, 0, [])


def test_a_waiting_hold_keeps_the_session_past_its_idle_grace(drainer, monkeypatch):
    """Otherwise the drainer quits before the first 10-minute retry comes round."""
    run, _, clock = drainer
    passes = []

    def one_pass(running, failed, tried, args):
        passes.append(clock["now"])
        if len(passes) > 5:
            raise KeyboardInterrupt
        return 0, 1

    monkeypatch.setattr(run, "_reap", lambda running, failed: None)
    monkeypatch.setattr(run, "_pass", one_pass)
    monkeypatch.setattr(run.time, "sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds))

    run._session(Namespace(watch=True, dry_run=True, interval=60, grace=120))

    assert len(passes) == 6
