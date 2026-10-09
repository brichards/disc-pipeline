"""A disc that a stage could not eject comes out on a later drainer pass.

While the screen is locked, loginwindow refuses each eject. On 2026-10-08,
Hitman's Bodyguard stayed in the drive after its rip for that reason.
"""

from argparse import Namespace
from pathlib import Path

import pytest

from discpipe import disc, manifest

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
