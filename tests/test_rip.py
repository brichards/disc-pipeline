"""Adopting a file already in raw/ matches on runtime, not on file size.

Sizes cluster tightly across the titles of one disc, so a size comparison
accepted files that held a different title entirely.
"""

from discpipe import makemkv, probe


def title(index, seconds, size_bytes, playlist):
    return makemkv.Title(
        index=index,
        seconds=seconds,
        size_bytes=size_bytes,
        source_file=playlist,
        output_name=f"Movie-{index:02d}.mkv",
    )


def stub_probe(monkeypatch, rip, seconds):
    monkeypatch.setattr(rip.probe, "ffprobe",
                        lambda path: {"seconds": seconds, "size_bytes": 0})


def test_adopts_a_file_whose_runtime_matches(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    candidate = title(1, seconds=4610, size_bytes=20_000_000_000,
                      playlist="00800.mpls")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / candidate.output_name).write_bytes(b"x")
    records = {"00800.mpls": {}}
    stub_probe(monkeypatch, rip, 4610)

    todo, have = rip._split_todo([candidate], records, raw, redo=False)

    assert have == [candidate]
    assert todo == []
    assert records["00800.mpls"]["rip"]["adopted"] is True


def test_rejects_a_file_holding_a_different_title(script, monkeypatch, tmp_path):
    """Same byte size, wrong runtime -- the Warm Bodies failure."""
    rip = script("disc-rip")
    candidate = title(1, seconds=4610, size_bytes=20_000_000_000,
                      playlist="00800.mpls")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / candidate.output_name).write_bytes(b"x")
    records = {"00800.mpls": {}}
    stub_probe(monkeypatch, rip, 283)

    todo, have = rip._split_todo([candidate], records, raw, redo=False)

    assert todo == [candidate]
    assert have == []
    assert "rip" not in records["00800.mpls"]


def test_tolerance_is_seconds_not_minutes(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    candidate = title(1, seconds=4610, size_bytes=1, playlist="00800.mpls")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / candidate.output_name).write_bytes(b"x")

    stub_probe(monkeypatch, rip, 4610 + rip.DURATION_TOLERANCE)
    _, have = rip._split_todo([candidate], {"00800.mpls": {}}, raw, redo=False)
    assert have == [candidate]

    stub_probe(monkeypatch, rip, 4610 + rip.DURATION_TOLERANCE + 1)
    todo, _ = rip._split_todo([candidate], {"00800.mpls": {}}, raw, redo=False)
    assert todo == [candidate]


def test_redo_re_rips_even_a_matching_file(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    candidate = title(1, seconds=4610, size_bytes=1, playlist="00800.mpls")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / candidate.output_name).write_bytes(b"x")
    records = {"00800.mpls": {"rip": {"status": "done"}}}
    stub_probe(monkeypatch, rip, 4610)

    todo, have = rip._split_todo([candidate], records, raw, redo=True)

    assert todo == [candidate]
    assert have == []


def test_an_unprobeable_file_is_not_adopted(script, monkeypatch, tmp_path):
    rip = script("disc-rip")
    candidate = title(1, seconds=4610, size_bytes=1, playlist="00800.mpls")
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / candidate.output_name).write_bytes(b"x")
    monkeypatch.setattr(rip.probe, "ffprobe", lambda path: None)

    todo, have = rip._split_todo([candidate], {"00800.mpls": {}}, raw, redo=False)

    assert todo == [candidate]
    assert have == []
