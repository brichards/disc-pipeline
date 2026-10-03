"""The manifest and the plan are rewritten while other stages may read them."""

import json

from discpipe import jsonfile


def test_an_interrupted_write_leaves_the_old_file_intact(monkeypatch, tmp_path):
    target = tmp_path / "manifest.json"
    jsonfile.write(target, {"state": "ripped"})

    def explode(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(jsonfile.os, "replace", explode)
    try:
        jsonfile.write(target, {"state": "shipped"})
    except OSError:
        pass

    assert json.loads(target.read_text()) == {"state": "ripped"}


def test_the_temporary_file_does_not_survive_a_good_write(tmp_path):
    target = tmp_path / "manifest.json"

    jsonfile.write(target, {"state": "ripped"})

    assert [p.name for p in tmp_path.iterdir()] == ["manifest.json"]


def test_a_missing_parent_is_created(tmp_path):
    target = tmp_path / "a-disc" / "manifest.json"

    jsonfile.write(target, {"state": "queued"})

    assert json.loads(target.read_text()) == {"state": "queued"}


def test_the_file_ends_with_a_newline(tmp_path):
    target = tmp_path / "plan.json"

    jsonfile.write(target, {"items": []})

    assert target.read_text().endswith("}\n")
