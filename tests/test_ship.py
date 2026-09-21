"""SMB does not preserve modification times, so a 't' difference is not a failure."""

import pytest

from discpipe import ship


@pytest.mark.parametrize("line", [
    ".f..t...... Movie (2013).mkv",      # timestamp only, content identical
    ".d..t...... ./",
    ".f.........  Movie (2013).mkv",
    "sending incremental file list",
    "sent 1,234 bytes  received 56 bytes",
    "total size is 4,000,000  speedup is 3.00",
    "",
])
def test_lines_that_do_not_mean_the_copy_is_wrong(line):
    assert ship._is_mismatch(line) is False


@pytest.mark.parametrize("line", [
    ">f.st...... Movie (2013).mkv",      # rsync would send data
    "<f.st...... Movie (2013).mkv",
    ".fc........ Movie (2013).mkv",      # checksum differs
    ".f.s....... Movie (2013).mkv",      # size differs
    "*deleting   Movie (2013).mkv",
])
def test_lines_that_mean_the_copy_is_wrong(line):
    assert ship._is_mismatch(line) is True


def test_verify_uses_checksums_rather_than_size_and_time():
    """A size-and-timestamp comparison would pass files that differ."""
    assert "--checksum" in ship.VERIFY_ARGS
    assert "--dry-run" in ship.VERIFY_ARGS
