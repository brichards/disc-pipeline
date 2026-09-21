import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
BIN = PROJECT / "bin"
sys.path.insert(0, str(PROJECT))

from discpipe import config  # noqa: E402


@pytest.fixture
def script():
    """Load a bin/ command as a module.

    The commands have no .py extension, so the normal import machinery skips
    them and they need an explicit loader.
    """
    def load(name):
        loader = SourceFileLoader(name.replace("-", "_"), str(BIN / name))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    return load


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Point the pipeline at a throwaway queue root."""
    queue = tmp_path / "Rips"
    queue.mkdir()
    monkeypatch.setattr(config, "ROOT", queue)
    monkeypatch.setattr(config, "LEDGER", queue / "ledger.jsonl")
    return queue


@pytest.fixture
def bluray(tmp_path):
    """Build a directory that looks like a mounted Blu-ray."""
    def build(name, streams=("00042.m2ts",)):
        mount = tmp_path / "volumes" / name
        (mount / "BDMV" / "STREAM").mkdir(parents=True)
        (mount / "BDMV" / "PLAYLIST").mkdir()
        (mount / "BDMV" / "index.bdmv").write_bytes(b"x")
        for stream in streams:
            (mount / "BDMV" / "STREAM" / stream).write_bytes(b"x" * 16)
        return mount
    return build
