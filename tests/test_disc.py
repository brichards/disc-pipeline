"""An ejected disc can leave its mount point behind on macOS."""

import pathlib
import shutil
import subprocess

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


def test_every_command_measures_space_the_same_way():
    """disc-cleanup kept free space after the others changed to Finder's figure."""
    project = pathlib.Path(__file__).resolve().parent.parent
    sources = [*project.glob("bin/disc-*"), *project.glob("discpipe/*.py")]
    measured = [path.name for path in sources if path.name != "disc.py"
                and any(call in path.read_text() for call in ("disk_usage", "statvfs"))]

    assert measured == []


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


DISSENT = ("Unmount of disk2 failed: at least one volume could not be unmounted\n"
           "Unmount was dissented by PID 412 (/usr/bin/mds)\n")
EMPTY = "           Type: No Media Inserted\n"
LOADED = "           Type: BD-ROM               Name: /dev/disk2\n"


class FakeDrive:
    """diskutil refuses while the disc is held; drutil eject exits 0 either way.

    Both measured on 2026-10-06 by holding a file open on a mounted Blu-ray.
    """

    def __init__(self, held_for=0, drutil_ejects=False):
        self.held_for = held_for
        self.drutil_ejects = drutil_ejects
        self.loaded = True
        self.calls = []

    def run(self, argv, **kwargs):
        self.calls.append(" ".join(argv[:2]))
        if argv[:2] == ["diskutil", "eject"]:
            if self.held_for:
                self.held_for -= 1
                return subprocess.CompletedProcess(argv, 1, "", DISSENT)
            self.loaded = False
            return subprocess.CompletedProcess(argv, 0, "Disk ejected\n", "")
        if argv == ["drutil", "eject"]:
            self.loaded = self.loaded and not self.drutil_ejects
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv == ["drutil", "status"]:
            return subprocess.CompletedProcess(argv, 0, LOADED if self.loaded else EMPTY, "")
        raise AssertionError(f"unexpected command {argv}")


@pytest.fixture
def drive(monkeypatch):
    def install(**behaviour):
        fake = FakeDrive(**behaviour)
        monkeypatch.setattr(disc.subprocess, "run", fake.run)
        monkeypatch.setattr(disc.time, "sleep", lambda seconds: None)
        return fake
    return install


def test_a_disc_held_for_a_moment_is_ejected_once_let_go(drive, tmp_path):
    fake = drive(held_for=2)

    assert disc.eject(tmp_path) == (True, "")
    assert fake.calls.count("diskutil eject") == 3


def test_drutil_exiting_0_is_not_an_eject(drive, tmp_path):
    """The Gangster Squad failure: logged "Ejected" with the disc still mounted."""
    fake = drive(held_for=99)

    ok, why = disc.eject(tmp_path)

    assert ok is False
    assert why == "Unmount was dissented by PID 412 (/usr/bin/mds)"
    assert fake.loaded is True


def test_one_attempt_makes_one_diskutil_call(drive, tmp_path):
    """The drainer tries once on each pass, so a locked screen does not delay it."""
    fake = drive(held_for=99)

    assert disc.eject(tmp_path, attempts=1)[0] is False
    assert fake.calls.count("diskutil eject") == 1


def test_a_disc_already_unmounted_is_ejected_by_drutil(drive, tmp_path):
    fake = drive(drutil_ejects=True)

    assert disc.eject(tmp_path / "GONE") == (True, "")
    assert "diskutil eject" not in fake.calls
