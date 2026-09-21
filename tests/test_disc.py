"""An ejected disc can leave its mount point behind on macOS."""

import pytest

from discpipe import disc


def test_loaded_disc_is_found(bluray, monkeypatch):
    mount = bluray("MOVIE")
    monkeypatch.setattr(disc, "VOLUMES", mount.parent)

    assert disc.find_discs() == [(mount, disc.BLURAY)]
    assert disc.stale_mounts() == []


def test_mount_without_streams_is_not_a_disc(bluray, monkeypatch):
    """The marker file still stats, so disc_type() alone calls it a Blu-ray."""
    mount = bluray("EJECTED", streams=())
    monkeypatch.setattr(disc, "VOLUMES", mount.parent)

    assert disc.disc_type(mount) == disc.BLURAY
    assert disc.find_discs() == []
    assert disc.stale_mounts() == [mount]


def test_fingerprint_refuses_a_volume_with_no_streams(bluray):
    mount = bluray("EJECTED", streams=())

    with pytest.raises(ValueError):
        disc.fingerprint(mount, disc.BLURAY)


def test_fingerprint_is_stable_and_distinguishes_discs(bluray):
    one = bluray("ONE", streams=("00042.m2ts", "00055.m2ts"))
    again = bluray("ONE_AGAIN", streams=("00042.m2ts", "00055.m2ts"))
    other = bluray("OTHER", streams=("00001.m2ts",))

    assert disc.fingerprint(one, disc.BLURAY) == disc.fingerprint(again, disc.BLURAY)
    assert disc.fingerprint(one, disc.BLURAY) != disc.fingerprint(other, disc.BLURAY)
