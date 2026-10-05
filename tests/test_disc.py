"""An ejected disc can leave its mount point behind on macOS."""

import shutil
import subprocess

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


def test_space_is_measured_as_finder_measures_it(monkeypatch, tmp_path):
    """Free space alone held discs that Finder showed room for."""
    seen = []

    def run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "61579284888\n", "")

    monkeypatch.setattr(disc.subprocess, "run", run)

    assert disc.available_bytes(tmp_path) == 61_579_284_888
    assert "NSURLVolumeAvailableCapacityForImportantUsageKey" in seen[0][4]


def test_free_space_stands_in_when_macos_cannot_say(monkeypatch, tmp_path):
    def run(argv, **kwargs):
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(disc.subprocess, "run", run)

    assert disc.available_bytes(tmp_path) == shutil.disk_usage(tmp_path).free


def test_the_finder_figure_reads_on_this_mac(tmp_path):
    """The script is the part a stub cannot check."""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", disc._AVAILABLE, str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) > 0
