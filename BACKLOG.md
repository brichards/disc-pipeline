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

## DP-03 — Test harness — `todo`

Prerequisite for every refactor below.

Each case below is a regression test for a bug that actually shipped, which is
why they pass the zero-tests bar:

- Phantom mount: marker present, no stream files, not a disc.
- `_refuse()`: outside root, the root itself, a symlink escaping the root, a
  path with no pipeline artifact beside it.
- Title indices shift with `--minlength` -- put 9 wrong files in Warm Bodies.
- Adoption matches on duration, not size -- size accepted 8 wrong files.
- rsync verification passes on a timestamp-only difference, fails on a content
  difference.
- A hold reverts to SHIPPED when the delete fails.

Do not pad this list to look thorough.

## DP-04 — Standardize flags — `todo`

`--force` means three different things:

| Command | `--force` |
| --- | --- |
| `disc-rip` | re-rip a disc already in the ledger |
| `disc-verify` | re-check titles already verified |
| `disc-transcode` | redo files already marked done |

`disc-rip` also splits `--force` and `--redo` where others use `--force`
alone. `disc-apply` carries `--yes` (accept everything) and `--auto` (accept
only when unanimously high confidence).

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

## DP-07 — Rewrite the README — `todo`

After DP-05 and DP-06.

It should cover install, run, and what each command does. Fixes already
identified: delete "Two notes on those."; write `~/Movies/Rips`; delete "Why
it exists"; remove "It's not X, it's Y" constructions; rename "How a disc
moves through"; drop the "Stops for you?" column; remove the zero-dependency
claim.

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

## DP-13 — Re-evaluate the language — `todo`

Deferred until feature-complete. The original reason for Python stands until
evidence says otherwise: seven scripts repairable individually beat one binary
that fails as a unit.

## DP-14 — Evaluate a GUI — `todo`

Parked. Swift, for people who do not want a terminal.
