"""disc-rip <slug> rips the disc it names, or nothing.

With no slug it rips whatever is mounted first, which is right for the watcher
and wrong for a retry: a retry for one disc must not rip another.
"""

from pathlib import Path

import pytest

from discpipe import disc

FIRST = (Path("/Volumes/MEN_IN_BLACK"), disc.BLURAY)
SECOND = (Path("/Volumes/MEN_IN_BLACK_II"), disc.BLURAY)


@pytest.fixture
def rip(script, root, monkeypatch):
    stage = script("disc-rip")
    ripped = []
    monkeypatch.setattr(stage.config, "check_environment", lambda: None)
    monkeypatch.setattr(stage.disc, "find_discs", lambda: [FIRST, SECOND])
    monkeypatch.setattr(stage.disc, "fingerprint", lambda mount, kind: "fp-" + mount.name)
    monkeypatch.setattr(stage, "_run", lambda args, discs: ripped.append(discs) or 0)

    def run(*argv):
        monkeypatch.setattr("sys.argv", ["disc-rip", *argv])
        return stage.main(), ripped
    return run


def slug_of(found):
    mount, _ = found
    return disc.slugify(mount.name, "fp-" + mount.name)


def test_a_slug_rips_only_the_disc_it_names(rip):
    code, ripped = rip(slug_of(SECOND))

    assert ripped == [[SECOND]]


def test_a_slug_for_a_disc_not_in_the_drive_rips_nothing(rip):
    with pytest.raises(SystemExit):
        rip("some-other-disc-abc123")


def test_without_a_slug_the_mounted_disc_is_ripped(rip):
    """The watcher's path, which has no slug to give."""
    code, ripped = rip()

    assert ripped == [[FIRST, SECOND]]
