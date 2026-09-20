# Backlog

Ordered. Work top to bottom, except DP-12, which depends on nothing.

Status: `todo`, `doing`, `done`. Reference the ID in commit messages.

## Standards

Adopted 2026-08-26 after Elliot Smith, *Engineering Theatre*.

**Comments explain external reality, not our decisions.** MakeMKV's
undocumented attribute IDs, macOS leaving mount points behind, Blu-ray never
carrying AAC -- keep these. Why a threshold is 240 rather than 300, what
incident prompted a change, what we considered and rejected -- these go in the
commit message. Default to no comment; new ones carry a high bar.

**Assume a competent reader.** Nothing that restates the code or a name.

**Tests: would we add this one if we had none today?** No coverage targets.
A test earns its place by catching a failure that has happened or plausibly
will.

**Comments and tests must be evergreen.** Neither exists to justify a choice
or narrate history.

Current state, for measuring against: 2,859 code lines carry 684 lines of
comment and docstring, and the README is 517 lines.

## Decisions

- License: MIT.
- Tests: pytest, a development dependency. The runtime stays stdlib-only.
- Flags: renamed cleanly, no aliases. There are no outside users yet.
- The README's "zero dependencies" claim is false and comes out. The project
  needs MakeMKV, FFmpeg, HandBrakeCLI, the transcoder scripts and Claude Code.

---

## DP-01 — LICENSE — `done`

MIT, 2026, Brian Richards.

## DP-02 — Fix the install instructions — `done`

The transcoders come from two repos, both installed by hand:
`transcode-video.rb` from `lisamelton/video_transcoding`, `hevc-transcode.rb`
from `lisamelton/more-video-transcoding`. Neither is a gem any more.

## DP-03 — Test harness — `done`

61 tests in `tests/`, pytest from a venv the scripts never touch. Every case
is a regression test for a failure that happened, plus flag pass-through
between commands and the import/`--help` ritual.

Each was verified by mutating the code it covers and confirming it fails.

## DP-04 — Standardize flags — `done`

Two meanings, one name each: `--redo` repeats work already marked done,
`--force` overrides a refusal. `disc-verify --force` and
`disc-transcode --force` became `--redo`; `disc-rip` and `disc-ship` were
already correct.

`disc-apply`'s `--yes` and `--auto` were left alone — they are different in
kind, not inconsistently named.

## DP-05 — Extract the repeated stage shape — `todo`

`resolve_target` appears in 5 commands, `manifest.load` in 8, and the
hold/`locks.Busy` preamble verbatim in 5.

Extract only if the result reads better than the copies. Five honest copies
beat one clever abstraction.

## DP-06 — Simplify the three largest commands — `todo`

`disc-rip` (406), `disc-apply` (402), `disc-cleanup` (372) of 4,298 total.

Includes the prose pass: delete comments failing the Standards bar, and the
27 one-line functions that add no meaning. `_free()` in disc-cleanup and the
9-line `MIN_TITLE_LENGTH` comment in config.py are the reference cases.

## DP-07 — Rewrite the README — `done`

Rewritten on main (756bb9e): 544 lines down to 379, structure reordered, the
"Stops for you?" column and "Why it exists" gone, `inventory.json` and
`scratch/` documented for the first time. Its voice is the house style now,
recorded in CLAUDE.md.

**Standing rule: any change to a command or feature updates the README in the
same branch.**

## DP-08 — CONTRIBUTING — `todo`

After DP-03 and the refactor. Covers running the tests and the conventions:
one thought per commit, one branch per change, the import-plus-`--help`
verification, and the Standards above.

## DP-09 — Split disc-identify's mechanical and agentic halves — `todo`

Run frame extraction and signal gathering with no agent; make the agent half
provider-agnostic so a local model can be substituted. `--frames-only` and
`--from-log` already do part of this. Find the real seam before designing an
interface.

## DP-10 — Interactive identify — `todo`

Show a person the evidence the agent gets and let them name each title and
pick a type, producing the `plan.json` `disc-apply` reads. `disc-apply`'s
review loop already walks items with their evidence; what is missing is a plan
with empty proposals. Depends on DP-09.

## DP-11 — TV series support — `todo`

Wants the refactor finished first. Note the numbering trap: TheTVDB numbers
per segment, Wikipedia per half-hour block, and a disc may match either.

## DP-12 — Interlacing detection — `todo`

Self-contained. `ffmpeg -filter:v idet` counts TFF/BFF/progressive/
undetermined frames, so source and transcode can be compared. Preventing it is
a HandBrake comb-detection question; verify how `transcode-video.rb` exposes
that before promising a flag.

## DP-15 — Re-evaluate the UHD routing — `todo`

`hevc-transcode.rb` comes from `more-video-transcoding`, which its author has
stopped developing: "all the ratecontrol systems and behaviors here have been
rolled into the redesigned and rewritten version of `transcode-video.rb`."

So the above-1080p branch in `transcode.route()` may be routing to a
deprecated script for behavior the current `transcode-video.rb` already has.
Check what the rewritten script does with UHD before deciding. Related to
DP-12, since comb detection sits in the same tool.

## DP-16 — Survive a dead network during identify — `todo`

`disc-identify` spent 172 seconds on a call that could not connect, then wrote
`logs/identify.json` holding `API Error: Unable to connect to API
(ConnectionRefused)` and no plan. The disc was left with `frames/` empty and no
`plan.json`, and nothing distinguished this from the agent declining to answer.

An unreachable agent is not a bad disc. It should fail fast, say that the
network is the problem, and leave a retryable hold so the drainer picks the
disc up again once the connection returns.

## DP-13 — Re-evaluate the language — `todo`

Deferred until feature-complete. The original reason for Python stands until
evidence says otherwise: seven scripts repairable individually beat one binary
that fails as a unit.

## DP-14 — Evaluate a GUI — `todo`

Parked. Swift, for people who do not want a terminal.
