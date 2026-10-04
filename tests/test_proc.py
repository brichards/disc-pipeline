"""Streaming a subprocess line by line.

MakeMKV, rsync and HandBrake run for minutes to hours, so output is read as it
arrives. Collecting it at the end would hide a rip going wrong until it ended.
"""

import sys

from discpipe import proc


def emit(*lines):
    body = "; ".join(f"print({line!r})" for line in lines)
    return [sys.executable, "-c", body]


def test_every_line_arrives_in_order_without_its_newline():
    seen = []

    code = proc.stream(emit("first", "second", "third"), seen.append)

    assert seen == ["first", "second", "third"]
    assert code == 0


def test_the_exit_code_comes_back():
    code = proc.stream([sys.executable, "-c", "raise SystemExit(3)"], lambda _: None)

    assert code == 3


def test_stderr_is_folded_into_the_stream():
    """HandBrake writes its log to stderr; dropping it hides why a transcode failed."""
    seen = []

    proc.stream([sys.executable, "-c",
                 "import sys; print('out'); print('err', file=sys.stderr)"],
                seen.append)

    assert sorted(seen) == ["err", "out"]


def test_a_caller_that_wants_nothing_still_runs_the_command(tmp_path):
    marker = tmp_path / "ran"

    code = proc.stream([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])

    assert code == 0
    assert marker.exists()


def test_cwd_is_where_the_command_runs(tmp_path):
    seen = []

    proc.stream([sys.executable, "-c", "import os; print(os.getcwd())"],
                seen.append, cwd=tmp_path)

    assert seen == [str(tmp_path.resolve())]
