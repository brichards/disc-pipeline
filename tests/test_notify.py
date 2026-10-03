"""An eject that silently failed looked identical to one that worked."""

from pathlib import Path

from discpipe import notify


def test_a_successful_eject_says_so(capsys):
    notify.ejected(Path("/Volumes/MEN_IN_BLACK"), True)

    assert capsys.readouterr().out == "Ejected MEN_IN_BLACK\n"


def test_a_failed_eject_says_which_disc_is_stuck(capsys):
    notify.ejected(Path("/Volumes/MEN_IN_BLACK"), False)

    assert capsys.readouterr().out == "Could not eject MEN_IN_BLACK\n"


def test_durations_pad_minutes_and_seconds():
    """The format the rip report and the agent's inventory both read."""
    assert notify.human_duration(5875.27) == "1:37:55"
    assert notify.human_duration(3605) == "1:00:05"
    assert notify.human_duration(59) == "0:00:59"
