"""Every command must load, and the flags one command sends another must exist."""

import ast
import importlib
import pathlib
import subprocess
import sys

import pytest

PROJECT = pathlib.Path(__file__).resolve().parent.parent
BIN = PROJECT / "bin"
COMMANDS = sorted(p.name for p in BIN.glob("disc-*"))
MODULES = sorted(p.stem for p in (PROJECT / "discpipe").glob("*.py")
                 if p.stem != "__init__")


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    """py_compile does not evaluate default arguments, which hid a crash."""
    importlib.import_module(f"discpipe.{name}")


@pytest.mark.parametrize("name", COMMANDS)
def test_command_runs(name):
    result = subprocess.run([sys.executable, str(BIN / name), "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def accepted_flags(command):
    result = subprocess.run([sys.executable, str(BIN / command), "--help"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return {word.strip(",")
            for word in result.stdout.split()
            if word.startswith("--")}


def chained_calls():
    """Every literal [script, "--flag", ...] a command builds for another.

    disc-watch chains stages this way; the list is inside a function, so the
    source is the only place to read it.
    """
    for command in COMMANDS:
        tree = ast.parse((BIN / command).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.List):
                continue
            target, flags = None, []
            for element in node.elts:
                for text in ast.walk(element):
                    if isinstance(text, ast.Constant) and isinstance(text.value, str):
                        if text.value.startswith("disc-"):
                            target = text.value
                        elif text.value.startswith("--"):
                            flags.append(text.value)
            if target and flags:
                for flag in flags:
                    yield command, target, flag


@pytest.mark.parametrize("caller,target,flag", list(chained_calls()))
def test_chained_flag_exists(caller, target, flag):
    assert flag in accepted_flags(target), (
        f"{caller} passes {flag} to {target}, which does not accept it")


def test_drainer_flags_exist(script):
    """disc-run adds these because nobody is watching."""
    run = script("disc-run")
    assert run.UNATTENDED, "no unattended flags found to check"
    for target, flags in run.UNATTENDED.items():
        for flag in flags:
            assert flag in accepted_flags(target), (
                f"disc-run passes {flag} to {target}, which does not accept it")
