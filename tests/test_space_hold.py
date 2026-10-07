"""A retry of a disc held for space rips the titles from its first scan.

The drainer retries a space hold every 10 minutes. Each retry did a full
MakeMKV scan again, of a disc that the first run scanned.
"""

from argparse import Namespace

import pytest

from discpipe import disc, makemkv, manifest

GB = 1000**3
FEATURE = makemkv.Title(index=0, seconds=6600, duration="1:50:00", size_bytes=40 * GB,
                        source_file="00800.mpls", segment_map="1",
                        output_name="Vantage Point-00.mkv")
DECOYS = [makemkv.Title(index=i, seconds=6600, duration="1:50:00", size_bytes=40 * GB,
                        source_file=f"0080{i}.mpls", segment_map=str(i),
                        output_name=f"Vantage Point-0{i}.mkv")
          for i in range(3)]


@pytest.fixture
def rip(script, root, monkeypatch, tmp_path):
    rip = script("disc-rip")
    rip.scans, rip.ripped, rip.space, rip.titles = 0, [], 20 * GB, [FEATURE]

    def scan(drive, min_length):
        rip.scans += 1
        return makemkv.DiscInfo(titles=rip.titles), "scan"

    def rip_title(drive, index, raw_dir, min_length):
        rip.ripped.append(index)
        return 1, [], ""

    monkeypatch.setattr(rip.disc, "fingerprint", lambda mount, kind: "fp-vantage")
    monkeypatch.setattr(rip.disc, "available_bytes", lambda path: rip.space)
    monkeypatch.setattr(rip.makemkv, "scan", scan)
    monkeypatch.setattr(rip.makemkv, "rip", rip_title)
    monkeypatch.setattr(rip.notify, "alert", lambda title, message: None)
    rip.drive = [(tmp_path / "VANTAGE_POINT", disc.BLURAY)]
    return rip


def run(rip, redo=False, playlist=None, dry_run=False):
    args = Namespace(disc=0, force=False, dry_run=dry_run, redo=redo, no_eject=True,
                     wait=False, playlist=playlist)
    return rip._run(args, rip.drive)


def test_a_disc_still_short_of_space_is_not_scanned_again(rip, root):
    assert run(rip) == 1
    assert run(rip) == 1

    assert rip.scans == 1
    data = manifest.load("vantage-point-fp-van")
    assert data["state"] == manifest.HELD and data["held_retryable"]


def test_once_the_space_is_there_the_stored_titles_are_ripped(rip):
    run(rip)
    rip.space = 200 * GB

    run(rip)

    assert rip.scans == 1
    assert rip.ripped == [FEATURE.index]


def test_a_decoy_disc_rips_only_its_override_from_the_stored_titles(rip, monkeypatch):
    """Hitman's Bodyguard: 202 near-identical titles, one of them correct."""
    rip.titles = DECOYS
    monkeypatch.setattr(rip.triage, "summarize", lambda titles, minimum: {
        "titles_seen": 3, "titles_over_minimum": 3, "longest_seconds": 6600,
        "decoy_cluster_size": 3, "obfuscated": True, "segment_order_consistency": 0.5,
        "classifications": {}})
    manifest.overrides_set("fp-vantage", "00801.mpls", note="test")
    run(rip)
    rip.space = 200 * GB

    run(rip)

    assert rip.scans == 1
    assert rip.ripped == [1]


@pytest.mark.parametrize("flag", [{"redo": True}, {"playlist": "00800.mpls"},
                                  {"dry_run": True}])
def test_a_flag_that_changes_the_rip_scans_again(rip, flag):
    run(rip)

    run(rip, **flag)

    assert rip.scans == 2


def test_a_later_hold_for_a_different_reason_still_gets_a_scan(rip):
    run(rip)
    rip.space = 200 * GB
    run(rip)

    run(rip)

    assert rip.scans == 2
