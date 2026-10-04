"""Running a long job and reading its output as it arrives.

MakeMKV, rsync and HandBrake run for minutes or hours, so output is read line
by line rather than collected at the end. stderr is folded in because
HandBrake writes its log there, and the log is where a failed transcode says
why.
"""

import subprocess


def stream(command, on_line=None, cwd=None):
    """Run command, hand each output line to on_line. Returns the exit code."""
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        if on_line:
            on_line(line.rstrip())
    process.wait()
    return process.returncode
