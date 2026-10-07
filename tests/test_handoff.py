"""An inserted disc runs through every stage unless something blocks it.

disc-watch used to rip, verify and identify on its own and stop there; every
stage after that waited for someone to start disc-run. A stage run by hand
stopped too.
"""

import ast
from argparse import Namespace
from pathlib import Path

import pytest

from discpipe import disc, drainer, locks, manifest

BIN = Path(__file__).resolve().parent.parent / "bin"
MOUNT = Path("/Volumes/KNIGHT_AND_DAY")
# Captured at collection, before conftest stubs it for every test.
LAUNCH_SESSION = drainer._launch_session


def test_the_drainer_rips_a_disc_it_does_not_know_itself(script, root, monkeypatch):
    run = script("disc-run")
    launched = []
    monkeypatch.setattr(run, "_unqueued_disc", lambda: "knight-and-day-7e2ffc")
    monkeypatch.setattr(run, "_launch", lambda running, slug, stage, resource, extra, args:
                        launched.append((stage, extra)) or True)

    run._pass({}, {}, {}, Namespace())

    assert launched == [("disc-rip", ["knight-and-day-7e2ffc"])]


def test_a_stage_the_drainer_starts_knows_it(script, root, monkeypatch, tmp_path):
    """So that, finishing, it does not start a second drainer."""
    run = script("disc-run")
    monkeypatch.delenv(drainer.UNDER_DRAINER)
    seen = {}
    monkeypatch.setattr(run.subprocess, "Popen",
                        lambda argv, **kwargs: seen.update(kwargs) or object())

    run._launch({}, "knight-and-day-7e2ffc", "disc-identify", locks.AGENT,
                ["knight-and-day-7e2ffc"], Namespace(dry_run=False))

    assert seen["env"][drainer.UNDER_DRAINER] == "1"


@pytest.fixture
def spawned(root, monkeypatch, no_real_drainer):
    monkeypatch.delenv(drainer.UNDER_DRAINER)
    return no_real_drainer


def test_start_runs_a_session(spawned, root):
    drainer.start()

    assert spawned == [root / "watch.log"]


def test_the_session_is_detached_watch_mode(monkeypatch, tmp_path):
    """Detached, so it outlives the stage or watcher that started it."""
    calls = []
    monkeypatch.setattr(drainer.subprocess, "Popen",
                        lambda argv, **kwargs: calls.append((argv, kwargs)))

    LAUNCH_SESSION(tmp_path / "watch.log")

    (argv, kwargs), = calls
    assert argv[0].endswith("bin/disc-run") and argv[1:] == ["--watch"]
    assert kwargs["start_new_session"] is True


def test_start_does_nothing_inside_a_drainer_stage(spawned, monkeypatch):
    monkeypatch.setenv(drainer.UNDER_DRAINER, "1")

    drainer.start()

    assert spawned == []


def test_start_does_nothing_while_a_session_runs(spawned):
    with locks.hold(locks.SESSION):
        drainer.start()

    assert spawned == []


@pytest.fixture
def watcher(script, root, monkeypatch):
    watch = script("disc-watch")
    started, ejected = [], []
    monkeypatch.setattr(watch.disc, "find_discs", lambda: [(MOUNT, disc.BLURAY)])
    monkeypatch.setattr(watch.disc, "fingerprint", lambda mount, kind: "fp-knight")
    monkeypatch.setattr(watch.disc, "eject", lambda mount: ejected.append(mount) or (True, ""))
    monkeypatch.setattr(watch.drainer, "start", lambda: started.append(True))
    return watch, started, ejected


def test_the_watcher_hands_a_new_disc_to_the_drainer(watcher):
    watch, started, ejected = watcher

    assert watch._check() == 0
    assert started == [True] and ejected == []


def test_the_watcher_still_ejects_a_disc_already_ripped(watcher):
    watch, started, ejected = watcher
    manifest.ledger_append({"fingerprint": "fp-knight", "slug": "knight-and-day-7e2ffc"})

    watch._check()

    assert ejected == [MOUNT] and started == []


def _is_call(stmt, owner, names):
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == owner and stmt.value.func.attr in names)


def advances_without_starting():
    """Moves of a disc to a state the drainer acts on, not followed by drainer.start()."""
    stops = {"SHIPPED", "DONE"}
    for path in sorted(BIN.glob("disc-*")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(body, list):
                continue
            for i, stmt in enumerate(body):
                if not _is_call(stmt, "manifest", ("advance", "advance_slug")):
                    continue
                state = stmt.value.args[-1]
                if isinstance(state, ast.Attribute) and state.attr in stops:
                    continue
                following = body[i + 1] if i + 1 < len(body) else None
                if not (following and _is_call(following, "drainer", ("start",))):
                    yield f"{path.name}:{stmt.lineno}"


def test_every_stage_that_moves_a_disc_on_starts_the_drainer():
    """Run by hand, the next stage would otherwise wait for someone to notice."""
    assert list(advances_without_starting()) == []


def test_a_verified_rip_run_by_hand_starts_the_drainer(script, root, monkeypatch):
    """Verifying clears the way to identify without changing the disc's state."""
    verify = script("disc-verify")
    slug = "knight-and-day-7e2ffc"
    data = manifest.new(slug, "fp", "KNIGHT_AND_DAY", "bluray")
    data["titles"] = [{"index": 0, "output_name": "00.mkv",
                       "rip": {"status": "done", "warnings": ["read error"]}}]
    data["rip"] = {"suspect": True}
    manifest.save(data)
    manifest.advance_slug(slug, manifest.RIPPED)
    (root / slug / "raw").mkdir()
    (root / slug / "raw" / "00.mkv").write_bytes(b"mkv")
    started = []
    monkeypatch.setattr(verify.verify, "decode", lambda path: (True, []))
    monkeypatch.setattr(verify.drainer, "start", lambda: started.append(True))
    monkeypatch.setattr("sys.argv", ["disc-verify", slug, "--no-eject"])

    assert verify.main() == 0
    assert started == [True]
