"""disc-verify --force accepts a title that failed only its duration check.

The file is often fine, and re-ripping reaches the same file. But a clean
decode does not prove it is the title that was asked for, so only a person
asking makes it count.
"""

import pytest

from discpipe import locks, manifest

SLUG = "men-in-black-f1bb84"
SHORT = "output runs 0:04:32, expected 0:04:36"


def title(index, rip, on_disk=True):
    return {"index": index, "duration": "0:04:36", "output_name": f"{index:02d}.mkv",
            "rip": rip, "on_disk": on_disk}


def failed_runtime(**extra):
    return {"status": "failed", "exit_code": 0, "error": SHORT, **extra}


@pytest.fixture
def held(script, root, monkeypatch):
    stage = script("disc-verify")
    decoded = []

    def setup(titles, bad=()):
        data = manifest.new(SLUG, "fp", "MEN_IN_BLACK", "bluray")
        data["titles"] = [{k: v for k, v in t.items() if k != "on_disk"} for t in titles]
        data["rip"] = {"warnings": [w for t in titles for w in t["rip"].get("warnings", [])]}
        manifest.save(data)
        manifest.hold(manifest.load(SLUG), "1 title(s) failed: 2")
        raw = root / SLUG / "raw"
        raw.mkdir()
        for t in titles:
            if t["on_disk"]:
                (raw / t["output_name"]).write_bytes(b"mkv")

        def decode(path):
            decoded.append(path.name)
            return (False, ["[vc1] damaged"]) if path.name in bad else (True, [])
        monkeypatch.setattr(stage.verify, "decode", decode)

    def run(*argv):
        monkeypatch.setattr("sys.argv", ["disc-verify", SLUG, *argv])
        return stage.main()

    return setup, run, decoded


def test_a_runtime_mismatch_that_decodes_clean_is_accepted(held):
    setup, run, _ = held
    setup([title(0, {"status": "done", "exit_code": 0}), title(2, failed_runtime())])

    assert run("--force") == 0

    data = manifest.load(SLUG)
    rip = data["titles"][1]["rip"]
    assert rip["status"] == "done"
    assert rip["accepted"]["overrode"] == SHORT
    assert "error" not in rip
    assert data["state"] == manifest.RIPPED


def test_the_disc_stays_held_while_a_title_still_fails(held):
    setup, run, _ = held
    setup([title(2, failed_runtime()), title(3, failed_runtime())], bad={"03.mkv"})

    assert run("--force") == 1

    data = manifest.load(SLUG)
    assert [t["rip"]["status"] for t in data["titles"]] == ["done", "failed"]
    assert data["state"] == manifest.HELD


def test_a_title_makemkv_itself_failed_is_never_offered(held):
    """It may be cut short, and a cut-short file can still decode clean."""
    setup, run, decoded = held
    setup([title(2, {"status": "failed", "exit_code": 1})])

    assert run("--force") == 0

    assert decoded == []
    assert manifest.load(SLUG)["titles"][0]["rip"]["status"] == "failed"


def test_a_failed_title_with_no_file_is_never_offered(held):
    setup, run, decoded = held
    setup([title(2, failed_runtime(), on_disk=False)])

    run("--force")

    assert decoded == []


def test_without_force_a_failed_title_is_left_alone(held):
    setup, run, decoded = held
    setup([title(2, failed_runtime(warnings=["read error"]))])

    run()

    assert decoded == []
    assert manifest.load(SLUG)["titles"][0]["rip"]["status"] == "failed"


def test_an_accepted_rip_with_read_errors_still_goes_to_verify(held, script):
    """Acceptance hands the disc back to the drainer, which checks the rest."""
    setup, run, _ = held
    setup([title(0, {"status": "done", "exit_code": 0, "warnings": ["read error"]}),
           title(2, failed_runtime())])

    run("--force")

    assert script("disc-run")._next_action(manifest.load(SLUG)) == ("disc-verify", locks.CPU)
