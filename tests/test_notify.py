"""An eject that silently failed looked identical to one that worked."""

from pathlib import Path

from discpipe import notify


def test_a_successful_eject_says_so(capsys):
    notify.ejected(Path("/Volumes/MEN_IN_BLACK"), (True, ""))

    assert capsys.readouterr().out == "Ejected MEN_IN_BLACK\n"


def test_a_failed_eject_says_which_disc_is_stuck(capsys):
    notify.ejected(Path("/Volumes/MEN_IN_BLACK"), (False, ""))

    assert capsys.readouterr().out == "Could not eject MEN_IN_BLACK\n"


def test_durations_pad_minutes_and_seconds():
    """The format the rip report and the agent's inventory both read."""
    assert notify.human_duration(5875.27) == "1:37:55"
    assert notify.human_duration(3605) == "1:00:05"
    assert notify.human_duration(59) == "0:00:59"


def test_titles_the_rip_missed_are_listed_under_a_heading(capsys):
    notify.not_ripped(["Theatrical trailer", "Animated series pilot"])

    assert capsys.readouterr().out == (
        "\nOn the disc but not ripped:\n"
        "  - Theatrical trailer\n"
        "  - Animated series pilot\n"
    )


def test_nothing_is_printed_when_nothing_was_missed(capsys):
    notify.not_ripped([])
    notify.not_ripped(None)

    assert capsys.readouterr().out == ""


def test_sizes_count_in_finders_units():
    """A disc held as needing "42.3 GB" needed 45.4 GB by Finder's count."""
    assert notify.human_bytes(45_400_000_000) == "45.4 GB"
    assert notify.human_bytes(51_810_000_000) == "51.8 GB"
    assert notify.human_bytes(1_500_000) == "1.5 MB"
    assert notify.human_bytes(1_010_000_000) == "1.0 GB"
    assert notify.human_bytes(999) == "999 B"


def test_a_failed_eject_names_what_held_the_disc(capsys):
    notify.ejected(Path("/Volumes/GANGSTER_SQUAD"),
                   (False, "Unmount was dissented by PID 412 (/usr/bin/mds)"))

    assert capsys.readouterr().out == (
        "Could not eject GANGSTER_SQUAD: Unmount was dissented by PID 412 (/usr/bin/mds)\n")
