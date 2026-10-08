"""Run Claude Code in headless mode to get a naming plan for the ripped titles.

disc-identify gives the agent an inventory and contact sheets of the titles.
The agent returns a plan, and renames nothing.
"""

import dataclasses
import json
import re
import shutil
import subprocess

DEFAULT_TIMEOUT = 1800


@dataclasses.dataclass(frozen=True)
class Failure:
    message: str
    retryable: bool = False


# The claude CLI gives the HTTP status in its envelope when a request got to the
# API. When a request did not get to the API, the message names the transport.
RETRYABLE_STATUSES = frozenset({401, 408, 429, 500, 502, 503, 504})
_UNREACHABLE = re.compile(
    r"unable to connect|connection (refused|reset|error)"
    r"|network is unreachable|temporary failure in name resolution",
    re.IGNORECASE,
)

# With no allowlist, a headless run stops at a permission prompt that nobody
# answers. The stage then waits with no end and does not fail.
ALLOWED_TOOLS = [
    "Skill",
    "Read",
    "Glob",
    "Grep",
    "Bash(ffmpeg:*)",
    "Bash(ffprobe:*)",
    "WebSearch",
    "WebFetch",
]

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Film or show name"},
        "year": {"type": "string"},
        "disc_notes": {
            "type": "string",
            "description": "What this disc turned out to be, in a sentence or two",
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Existing filename"},
                    "action": {
                        "type": "string",
                        "enum": ["feature", "extra", "reject", "unknown"],
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Proposed filename, empty unless renaming",
                    },
                    "extra_type": {
                        "type": "string",
                        "enum": [
                            "behindthescenes", "deleted", "featurette", "interview",
                            "scene", "short", "trailer", "other", "",
                        ],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Why. Title card text, runtime match, "
                                       "where the footage sits in the feature.",
                    },
                },
                "required": ["file", "action", "confidence", "evidence"],
            },
        },
        "missing_from_rip": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Extras the disc ships that were not ripped",
        },
    },
    "required": ["title", "items"],
}


def available():
    return shutil.which("claude") is not None


def build_prompt(name, media_dir, work_dir, inventory_file, frames_dir, scratch_dir):
    return f"""Invoke the plex-media-namer skill, then identify every file in this rip.

Rip directory: {media_dir}
Inventory (durations, dimensions, stream layout): {inventory_file}
Contact sheets: {frames_dir}
Scratch space for any frames you pull yourself: {scratch_dir}

Two sheets per file. `--head.png` covers the first 75 seconds in 3-second
steps, which is where a title card lands once the studio logo clears.
`--scan.png` samples 16 frames across the whole runtime, for content and end
credits. Read them with the Read tool. You have ffmpeg and ffprobe if you need
a frame the sheets do not cover -- comparing tails, or checking whether a file
duplicates part of the feature. Run them as a single command with absolute
paths: shell chaining like `cd somewhere && ffmpeg ...` is refused by the
permission allowlist, and the scratch directory already exists so you do not
need mkdir.

The folder is named "{name}", which is a strong hint at the film but not proof.
Confirm it, then look up what this specific disc release actually ships so you
can match extras by name and runtime.

Rules that matter here:

- Do not rename anything. Produce a proposal. A separate reviewed step applies it.
- Files that are chunks of the main feature, credits-only titles, or trailers
  for other films are not extras. Mark them `reject` and say what they are.
- A file you cannot place gets `unknown`, not a guess.
- `evidence` is the field a human reads to approve in one second. Make it
  specific: the title card text, the runtime that matched and its source, or
  where in the feature the footage sits.
- Set `confidence` honestly. `high` means a title card or an exact published
  runtime. Duration alone is `medium` at best.

Return the plan as structured output."""


def run(prompt, cwd, extra_dirs=(), timeout=DEFAULT_TIMEOUT, model=None):
    command = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(PLAN_SCHEMA),
        "--allowedTools", *ALLOWED_TOOLS,
    ]
    for directory in extra_dirs:
        command += ["--add-dir", str(directory)]
    if model:
        command += ["--model", model]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", Failure(f"agent timed out after {timeout}s", True)

    if result.returncode != 0:
        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError:
            envelope = None
        detail = (result.stderr or "").strip()[:500]
        return None, result.stdout, _error_in(envelope) or Failure(
            detail or f"agent exited {result.returncode}"
        )

    plan, failure = _extract_plan(result.stdout)
    return plan, result.stdout, failure


def _extract_plan(stdout):
    """With --json-schema, the claude CLI puts the validated object in
    `structured_output`. `result` holds only a prose summary of the plan.
    """
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return None, Failure("agent output was not JSON")

    failure = _error_in(envelope)
    if failure:
        return None, failure

    if isinstance(envelope, dict) and isinstance(envelope.get("structured_output"), dict):
        payload = envelope["structured_output"]
    else:
        payload = envelope.get("result", envelope) if isinstance(envelope, dict) else envelope

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None, Failure("agent result was not a JSON plan")

    if not isinstance(payload, dict) or "items" not in payload:
        return None, Failure("agent plan had no items")

    return payload, None


def _error_in(envelope):
    """The claude CLI describes a failed run on stdout, whatever its exit code."""
    if not isinstance(envelope, dict) or not envelope.get("is_error"):
        return None
    message = str(envelope.get("result", "agent reported an error"))[:500]
    return Failure(message, _is_retryable(envelope, message))


def _is_retryable(envelope, message):
    status = envelope.get("api_error_status")
    if isinstance(status, int):
        return status in RETRYABLE_STATUSES
    return bool(_UNREACHABLE.search(message))
