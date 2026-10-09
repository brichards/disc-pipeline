"""A disc that a stage could not eject comes out on a later drainer pass.

While the screen is locked, loginwindow refuses each eject. On 2026-10-08,
Hitman's Bodyguard stayed in the drive after its rip for that reason.
"""

from argparse import Namespace
from pathlib import Path

import pytest

from discpipe import disc, locks, manifest

MOUNT = Path("/Volumes/HITMANS_BODYGUARD")
REFUSED = (False, "Unmount was dissented by PID 168 (loginwindow)")
SLUG = "hitmans-bodyguard-021a8d"


def ripped(pending=False):
    data = manifest.new(SLUG, "fp-hitman", "HITMANS_BODYGUARD", disc.BLURAY)
    if pending:
        data["eject_pending"] = True
    manifest.save(data)
    return data


def pending():
    return manifest.load(SLUG).get("eject_pending", False)


ARGS = Namespace(no_eject=False, dry_run=False)
ENDS = {
    "clean rip": lambda rip, data: rip._finish(data, 1, 0, 0, MOUNT, ARGS),
    "hold": lambda rip, data: rip._park(data, "1 title(s) failed: 3", MOUNT, ARGS),
}


@pytest.mark.parametrize("end", ENDS.values(), ids=ENDS.keys())
def test_disc_rip_records_a_refused_eject(script, root, monkeypatch, end):
    rip = script("disc-rip")
    monkeypatch.setattr(rip.disc, "eject", lambda mount: REFUSED)

    end(rip, ripped())

    assert pending() is True


def test_an_eject_that_works_clears_the_record(script, root, monkeypatch):
    rip = script("disc-rip")
    monkeypatch.setattr(rip.disc, "eject", lambda mount: (True, ""))

    ENDS["clean rip"](rip, ripped(pending=True))

    assert pending() is False


def test_disc_verify_records_a_refused_eject(script, root, monkeypatch):
    verify = script("disc-verify")
    monkeypatch.setattr(verify.disc, "find_discs", lambda: [(MOUNT, disc.BLURAY)])
    monkeypatch.setattr(verify.disc, "fingerprint", lambda mount, kind: "fp-hitman")
    monkeypatch.setattr(verify.disc, "eject", lambda mount: REFUSED)

    verify._eject_if_still_ours(ripped())

    assert pending() is True


def drive_with(run, monkeypatch, outcome):
    calls = []
    monkeypatch.setattr(run.disc, "find_discs", lambda: [(MOUNT, disc.BLURAY)])
    monkeypatch.setattr(run.disc, "fingerprint", lambda mount, kind: "021a8d0000")
    monkeypatch.setattr(run.disc, "eject",
                        lambda mount, attempts=6: calls.append(attempts) or outcome)
    return calls


def test_the_drainer_ejects_a_disc_whose_eject_failed(script, root, monkeypatch):
    run = script("disc-run")
    ripped(pending=True)
    calls = drive_with(run, monkeypatch, (True, ""))

    run._retry_eject(Namespace(dry_run=False))

    assert calls == [1]
    assert pending() is False


def test_a_retry_that_fails_keeps_the_record(script, root, monkeypatch):
    """The screen can still be locked at the next pass."""
    run = script("disc-run")
    ripped(pending=True)
    drive_with(run, monkeypatch, REFUSED)

    run._retry_eject(Namespace(dry_run=False))

    assert pending() is True


def test_the_drainer_leaves_a_disc_with_no_record(script, root, monkeypatch):
    """disc-rip --no-eject keeps a disc in the drive on purpose."""
    run = script("disc-run")
    ripped()
    calls = drive_with(run, monkeypatch, (True, ""))

    run._retry_eject(Namespace(dry_run=False))

    assert calls == []


def test_a_dry_run_ejects_nothing(script, root, monkeypatch):
    run = script("disc-run")
    ripped(pending=True)
    calls = drive_with(run, monkeypatch, (True, ""))

    run._retry_eject(Namespace(dry_run=True))

    assert calls == [] and pending() is True


@pytest.mark.parametrize("held, expected", [(False, [True]), (True, [])],
                         ids=["drive free", "drive held"])
def test_a_pass_retries_only_while_no_stage_holds_the_drive(script, root, monkeypatch,
                                                            held, expected):
    run = script("disc-run")
    tried = []
    monkeypatch.setattr(run, "_retry_eject", lambda args: tried.append(True))
    monkeypatch.setattr(run, "_unqueued_disc", lambda: None)

    if held:
        with locks.hold(locks.DRIVE):
            run._pass({}, {}, {}, Namespace(dry_run=False))
    else:
        run._pass({}, {}, {}, Namespace(dry_run=False))

    assert tried == expected
