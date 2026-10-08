"""Run a long job, and read its output line by line.

HandBrake writes its log to stderr, and the log gives the cause of a failed
transcode.
"""

import subprocess


def stream(command, on_line=None, cwd=None):
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
