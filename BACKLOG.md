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

## DP-05 — Extract repeated code — `done`

The item named three shapes and a bar of "five honest copies beat one clever
abstraction". It ran to a different bar: any code repeated once or more that
reads better as one function. Every module was scanned, by AST rather than
text.

| Extracted | Sites | Was |
| --- | --- | --- |
| `manifest.find` | 4 | Loading a manifest, giving up if it is missing or unreadable |
| `manifest.advance_slug` | 3 | `advance(load(slug), state)` |
| `proc.stream` | 3 | MakeMKV, rsync and HandBrake each with their own `Popen` |
| `jsonfile.write` | 3 | Manifest, plan and overrides each writing to temp and renaming |
| `notify.ejected` | 3 | Reporting whether the disc came out |
| `plan.kept` | 3 | Folding in the decision, keeping named features and extras |
| `manifest.queue_dirs` | 2 | Walking the queue root, skipping dotfiles |
| `notify.human_duration` | 2 | `probe._hms` had an identical body |
| `probe._ffmpeg` | 2 | Quiet ffmpeg, success measured by whether the file appeared |
| `plan.tally` | 2 | Counting proposed actions for a report header |
| `notify.not_ripped` | 2 | Listing the titles the rip missed |

| Declined | Sites | Why |
| --- | --- | --- |
| `planlib.resolve_target` | 5 | Already the extraction |
| `locks.hold` / `locks.Busy` | 6 | Six distinct forms; a helper takes a parameter per difference |
| `_progress` callbacks | 2 | Differ only in indent; a helper needs a lambda at each site |
| `out_dir` / `destination` setup in `transcode.py` | 2 | Saves two lines for a function that both creates a directory and returns a path |
| `label` / `slug` / `ledger_find` | 2 | Two self-evident assignments and a call that is already named |
| `disc-ship._hold` | 1 | Looks like `manifest.find`, but its guard also covers the save |

Four defects surfaced, all in code nothing covered:

- `disc-cleanup` walked the queue root without checking it existed, and
  raised on a Mac that had never ripped a disc.
- `disc-watch` reported an eject only when it worked, so a disc the drive
  would not release left no trace.
- `disc-status` counted features and extras that review left unnamed, which
  `disc-transcode` skips, so a disc in that state showed a transcode count
  that could never complete.
- `makemkv.rip`'s warning collection had no test. Removing
  `warnings.append` left the suite green, on the one signal that tells a
  glitched rip from a clean one.

## DP-06 — Simplify the three largest commands — `todo`

`disc-rip` (406), `disc-apply` (402), `disc-cleanup` (372) of 4,298 total.

Includes the prose pass: delete comments failing the Standards bar, and the
27 one-line functions that add no meaning. `_free()` in disc-cleanup and the
9-line `MIN_TITLE_LENGTH` comment in config.py are the reference cases.

Carried over from DP-05:

- `disc-cleanup`'s three `_offer_*` functions share a prelude (path, exists,
  size) and a postlude (dry run, ask, delete).
- `resolve_target` returns a four-tuple, and three commands follow it with
  `planlib.load`. A `Target` object would replace both; a five-tuple would
  not.
- `bin/disc-apply` imports `config` and never uses it.

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

## DP-19 — The watcher starts the drainer — `todo`

Decided 2026-10-04: an inserted disc moves through every stage on its own unless
something blocks it. `disc-watch` starts `disc-run --watch` and nothing else.
Its rip, verify and identify chain duplicated three of the drainer's stages
without the drainer's locks or keep-awake, and stopped before the stages that
take longest.

- The drainer rips a disc it does not know yet by running `disc-rip` itself.
  Handing it to `disc-watch` would start a second drainer, which exits on the
  session lock, and the disc would never rip.
- A stage run by hand starts the drainer when it succeeds, so clearing a block
  -- a review, a decoy, a cleaned disc -- carries on without being remembered.
  The session lock makes that a no-op when a drainer is already running.
- The drainer's `caffeinate` covers the whole run. That closes the gap where a
  rip the watcher started had nothing keeping the Mac awake; on 2026-10-04 a
  Blu-ray rip lost its only keep-awake when the drainer stopped partway through.
- The README's two-step workflow becomes one step.

Needs DP-21 and DP-23 first, or a drainer started on every insert spins on the
first block it meets.

## DP-17 — disc-verify should adjudicate a failed title — `todo`

A title that failed only its duration check leaves a file on disk that may
well be fine, and there is no way to accept it short of editing the manifest.
Re-ripping an hour of video to reach the same file is the only supported path.

`disc-verify --force` fits the vocabulary -- it overrides the refusal to look
at a failed title. Decode it; on a clean result promote it to done, recording
that a person asked. Decoding proves the file is intact, not that it is the
title that was asked for, so this stays explicit rather than automatic.

## DP-18 — Resolving a decoy disc means editing JSON by hand — `todo`

`disc-rip` holds a decoy disc and tells you to run `disc-resolve <slug>`, which
does not exist. Underneath, `manifest.overrides_set` records which playlist to
rip, and nothing calls it, so the only way through is editing `overrides.json`.

`disc-rip <slug> --playlist 00800.mpls` should record the override and rip.
Same branch as DP-21, which gives `disc-rip` its slug.

## DP-16 — Survive a transient agent failure — `done`

`disc-identify` treated every agent failure the same way: a hold nobody
retries, reading `agent failed: agent failed`. Two of them in two days were
transport faults that cleared on their own -- the network down, then an
expired OAuth token.

The CLI describes both in its JSON envelope on stdout, which the non-zero exit
path discarded in favour of an empty stderr. It now reads the envelope either
way, and holds a run that never reached a verdict as retryable against the
identify stage, so the drainer picks the disc back up once the cause clears.

## DP-13 — Re-evaluate the language — `todo`

Deferred until feature-complete. The original reason for Python stands until
evidence says otherwise: seven scripts repairable individually beat one binary
that fails as a unit.

## DP-14 — Evaluate a GUI — `todo`

Parked. Swift, for people who do not want a terminal.

## DP-20 — A killed transcode can ship truncated — `todo`

The transcoders write straight to the final name in `transcoded/`. Kill one
partway through and the truncated file keeps that name: the next
`disc-transcode` reports it as already there, marks it done, and `disc-ship`
sends it to the library. Nothing anywhere says it is short.

Transcode into a staging directory, and move a file into place only once the
transcoder exits cleanly. `ship.py` does the same for rsync with
`--partial-dir`.

## DP-21 — The drainer cannot retry a rip — `todo`

`disc-run` starts every stage as `<stage> <slug>`, and `disc-rip` takes no
target, so it exits on an argument error. Both of the drainer's paths to
`disc-rip` fail this way -- retrying a hold for disk space, and resuming a disc
left `queued` by an interrupted rip -- and have since the drainer was added. On
2026-10-04 one held Blu-ray drew over 300 failed launches, one per pass, and
the drainer never went idle.

`disc-rip` should take an optional slug, and rip only when that disc is the one
in the drive. Same branch as DP-18, which adds a flag to the same command.

## DP-22 — Sizes are GiB labelled GB — `todo`

`notify.human_bytes` divides by 1024 and labels the result GB, so every size the
pipeline prints reads about 7% below Finder's for the same bytes. A disc held
as needing "42.3 GB" needed 45.4 GB by Finder's count. Divide by 1000, as Finder
does.

## DP-23 — The drainer spins on a refusal — `todo`

The drainer relaunches any stage that exits non-zero without changing the
disc's state, every pass. `disc-apply --auto` refuses a plan that is not
unanimously high confidence by exiting 1 and leaves the disc `identified`, so a
disc waiting for review is offered to it again every 30 seconds -- 20 times in a
row for Men in Black 3, with the Mac held awake throughout. A code comment calls
this a gate; `GATES` does not include it.

A refusal should hold the disc for review, and the drainer should not relaunch
a stage that failed until the disc's state has changed.
