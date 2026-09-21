"""Adopting a file already in raw/ matches on runtime, not on file size.

Sizes cluster tightly across the titles of one disc, so a size comparison
accepted files that held a different title entirely.
"""

from discpipe import disc, makemkv


def bluray_title(index, seconds, playlist, size_bytes=20_000_000_000):
    return makemkv.Title(
        index=index, seconds=seconds, size_bytes=size_bytes,
        source_file=playlist, segment_map="42",
        output_name=f"Movie-{index:02d}.mkv",
    )


def dvd_title(index, seconds, segments, size_bytes=4_098_029_568):
    """A DVD title reports no source file; that field is a Blu-ray playlist."""
    return makemkv.Title(
        index=index, seconds=seconds, size_bytes=size_bytes,
        source_file="", segment_map=segments,
        output_name=f"Men In Black-{index:02d}.mkv",
    )


def prepare(rip, monkeypatch, tmp_path, titles, on_disk=(), probed=None):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in on_disk:
        (raw / name).write_bytes(b"x")
    records = {rip._title_key(t): {} for t in titles}
    if probed is not None:
        monkeypatch.setattr(rip.probe, "ffprobe", probed)
    return raw, records


def fixed(seconds):
    return lambda path: {"seconds": seconds, "size_bytes": 0}


def test_adopts_a_file_whose_runtime_matches(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    one = bluray_title(1, 4610, "00800.mpls")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(4610))

    todo, have = rip._split_todo([one], records, raw, False, disc.BLURAY)

    assert have == [one] and todo == []
    assert records[rip._title_key(one)]["rip"]["adopted"] is True


def test_rejects_a_file_holding_a_different_title(script, monkeypatch, tmp_path):
    """Same byte size, wrong runtime -- the Warm Bodies failure."""
    rip = script("disc-rip")
    one = bluray_title(1, 4610, "00800.mpls")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(283))

    todo, have = rip._split_todo([one], records, raw, False, disc.BLURAY)

    assert todo == [one] and have == []
    assert "rip" not in records[rip._title_key(one)]


def test_redo_re_rips_even_a_matching_file(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    one = bluray_title(1, 4610, "00800.mpls")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(4610))
    records[rip._title_key(one)]["rip"] = {"status": "done"}

    todo, have = rip._split_todo([one], records, raw, True, disc.BLURAY)

    assert todo == [one] and have == []


def test_an_unprobeable_file_is_not_adopted(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    one = bluray_title(1, 4610, "00800.mpls")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name],
                           lambda path: None)

    todo, have = rip._split_todo([one], records, raw, False, disc.BLURAY)

    assert todo == [one] and have == []


def test_dvd_titles_get_separate_records(script, monkeypatch, tmp_path):
    """Keying on source_file collapsed every DVD title into one record.

    Title 1's result then overwrote title 0's, and a good file was judged
    against the wrong title's runtime.
    """
    rip = script("disc-rip")
    first = dvd_title(0, 5850, "1-48")
    second = dvd_title(1, 5848, "2-48")

    assert rip._title_key(first) != rip._title_key(second)

    raw, records = prepare(rip, monkeypatch, tmp_path, [first, second],
                           [first.output_name], fixed(5877))

    todo, have = rip._split_todo([first, second], records, raw, False, disc.DVD)

    assert have == [first]
    assert todo == [second]
    assert "rip" not in records[rip._title_key(second)]


def test_dvd_allows_the_drift_an_ifo_reports(script, monkeypatch, tmp_path):
    """Men in Black ran 5877.9s against an IFO claiming 5850."""
    rip = script("disc-rip")
    one = dvd_title(0, 5850, "1-48")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(5877.9))

    todo, have = rip._split_todo([one], records, raw, False, disc.DVD)

    assert have == [one] and todo == []


def test_bluray_still_refuses_that_much_drift(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    one = bluray_title(1, 5850, "00800.mpls")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(5877.9))

    todo, have = rip._split_todo([one], records, raw, False, disc.BLURAY)

    assert todo == [one] and have == []


def test_dvd_tolerance_still_catches_a_different_title(script, monkeypatch, tmp_path):
    """A looser bound is not an absent one."""
    rip = script("disc-rip")
    one = dvd_title(0, 5850, "1-48")
    raw, records = prepare(rip, monkeypatch, tmp_path, [one], [one.output_name], fixed(5850 - 240))

    todo, have = rip._split_todo([one], records, raw, False, disc.DVD)

    assert todo == [one] and have == []


def test_title_keys_are_unique_on_every_disc_layout(script):
    rip = script("disc-rip")
    layouts = {
        "dvd": [dvd_title(0, 5850, "1-48"), dvd_title(1, 5848, "2-48")],
        "bluray": [bluray_title(1, 4610, "00800.mpls"),
                   bluray_title(2, 4610, "00801.mpls")],
    }
    for name, titles in layouts.items():
        keys = [rip._title_key(t) for t in titles]
        assert len(set(keys)) == len(keys), f"{name} keys collide: {keys}"

    # A record read back from the manifest is a dict, and must key the same.
    one = dvd_title(0, 5850, "1-48")
    assert rip._title_key(rip._title_record(one)) == rip._title_key(one)
