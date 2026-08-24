"""Running Claude Code headless to name ripped titles.

The naming problem is not scriptable. Every disc worked by hand so far needed
a judgement call that metadata could not supply: which of three feature-length
titles is the film, whether eight mid-length titles are featurettes or slices
of the movie, which of two identical-looking sets is the truncated one. So the
stage shells out to an agent, hands it contact sheets and an inventory, and
takes back a proposal -- never a rename.
"""

import json
import shutil
import subprocess

DEFAULT_TIMEOUT = 1800

# Without an allowlist a headless run blocks on a permission prompt that nobody
# is there to answer, and the stage hangs instead of failing. Web access is not
# optional: the agent cannot name extras without looking up what the disc ships.
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


def build_prompt(name, media_dir, work_dir, inventory_file, frames_dir):
    return f"""Invoke the plex-media-namer skill, then identify every file in this rip.

Rip directory: {media_dir}
Inventory (durations, dimensions, stream layout): {inventory_file}
Contact sheets: {frames_dir}

Two sheets per file. `--head.png` covers the first 75 seconds in 3-second
steps, which is where a title card lands once the studio logo clears.
`--scan.png` samples 16 frames across the whole runtime, for content and end
credits. Read them with the Read tool. You have ffmpeg and ffprobe if you need
a frame the sheets do not cover -- comparing tails, or checking whether a file
duplicates part of the feature.

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
    """Invoke the agent. Returns (plan_dict, raw_stdout, error_or_None)."""
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
        return None, "", f"agent timed out after {timeout}s"

    if result.returncode != 0:
        return None, result.stdout, (result.stderr or "").strip()[:500] or "agent failed"

    plan, error = _extract_plan(result.stdout)
    return plan, result.stdout, error


def _extract_plan(stdout):
    """Unwrap the CLI envelope and get at the structured result."""
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return None, "agent output was not JSON"

    if isinstance(envelope, dict) and envelope.get("is_error"):
        return None, str(envelope.get("result", "agent reported an error"))[:500]

    payload = envelope.get("result", envelope) if isinstance(envelope, dict) else envelope

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None, "agent result was not a JSON plan"

    if not isinstance(payload, dict) or "items" not in payload:
        return None, "agent plan had no items"

    return payload, None
