# Backlog

Ordered. Work top to bottom, except DP-12, which depends on nothing and can be
picked up whenever it is convenient.

Status values: `todo`, `doing`, `done`. Reference the ID in commit messages.

## Decisions already made

- **License:** MIT.
- **Tests:** pytest, scoped as a development dependency. The runtime stays
  standard-library-only; the test suite does not.
- **Flags:** renamed cleanly, no backward-compatible aliases. There are no
  outside users yet, so there is nothing to keep working.
- **The "zero dependencies" claim comes out of the README.** It is false. The
  project needs MakeMKV, FFmpeg, HandBrakeCLI, the transcoder scripts and
  Claude Code, all of which can go missing between uses.

---

## DP-01 — Add a LICENSE — `todo`

MIT. Needs the exact name for the copyright line.

## DP-02 — Fix the install instructions — `todo`

`gem install video_transcoding` installs the wrong tool. That gem ships
`convert-video`, `detect-crop`, `query-handbrake-log` and `transcode-video` --
no `.rb` binaries at all. The scripts this project calls are
`transcode-video.rb` and `hevc-transcode.rb`, Copyright (c) 2025 Lisa Melton,
from her separate standalone-script project. Anyone following the README today
gets a pipeline that fails at transcode.

Confirm the canonical project name and install steps before writing.

## DP-03 — Test harness, covering current behavior — `todo`

Prerequisite for every refactor below. pytest, a `tests/` directory, and a
documented way to run it.

Cover the happy path and the refusals both. Cases worth carrying over from
one-off checks already run by hand:

- Phantom mount: marker file present, no stream files -> not a disc.
- `_refuse()` in disc-cleanup: outside root, the root itself, symlinks
  escaping the root, paths with no pipeline artifact beside them.
- Title indices shift with `--minlength` -- the bug that put nine wrong files
  in the Warm Bodies rip.
- Adoption by duration within tolerance, not by size.
- rsync verification passing on a timestamp-only difference, failing on a
  content difference.
- `already_encoded()` on an all-AAC file.
- Manifest state transitions, including a hold reverting on a failed delete.

## DP-04 — Standardize flags — `todo`

`--force` currently means three different things:

| Command | `--force` means |
| --- | --- |
| `disc-rip` | re-rip a disc already in the ledger |
| `disc-verify` | re-check titles already verified |
| `disc-transcode` | redo files already marked done |

`disc-rip` also splits into `--force` plus `--redo` what the others fold into
`--force` alone. `disc-apply` carries both `--yes` (accept everything) and
`--auto` (accept only when every item is high confidence) -- genuinely
different, badly signposted.

Decide one vocabulary, apply it everywhere, update the README tables.

## DP-05 — Extract the repeated stage shape — `todo`

Every stage opens the same way: resolve the target, load the manifest, take a
lock, step aside if it is held. `resolve_target` appears in 5 commands,
`manifest.load` in 8, and the hold/`locks.Busy` preamble is repeated verbatim
in 5.

Extract without adding indirection for its own sake. If the result is harder
to follow than five honest copies, keep the copies.

## DP-06 — Simplify the three largest commands — `todo`

`disc-rip` (406 lines), `disc-apply` (402), `disc-cleanup` (372), out of 4,298
total. This is where the conditional sprawl lives.

Goal is expressiveness, not fewer branches. Do not trade a clear conditional
for a clever construct that hides it.

## DP-07 — Rewrite the README prose — `todo`

After DP-05 and DP-06, so it describes the shape the code actually has.

Specific fixes already identified:

- Delete "Two notes on those."
- Write `~/Movies/Rips`, not `/Users/you/Movies/Rips`.
- Delete the "Why it exists" section.
- Remove "It's not X, it's Y" and "It is not X." constructions throughout.
- Rename "How a disc moves through" to "How it works" or "The process".
- Drop the "Stops for you?" column -- `disc-status` marks waiting discs with
  `!` and each command documents its own gates.
- Remove the zero-dependency claim (see Decisions).

Then a full pass for places that read as written-to-sound-human rather than
written to be read.

**Standing rule from here on: any change to a command or feature updates the
README in the same branch.**

## DP-08 — CONTRIBUTING — `todo`

After DP-03 and the refactor, since it documents how to run tests and what the
conventions are: one thought per commit, one branch per change, the
import-every-module plus `--help`-every-script verification, sane defaults over
options.

## DP-09 — Split disc-identify's mechanical and agentic halves — `todo`

Run frame extraction and signal gathering without invoking any agent, and make
the agent half provider-agnostic so a local model can be substituted.

`--frames-only` and `--from-log` already do part of this. Establish what the
seam actually is before designing the interface.

## DP-10 — Interactive identify — `todo`

Present a person the same evidence the agent gets -- contact sheets, duration,
track number, encoding signals -- and let them type a name and pick a type
(feature, edition, extra type), producing the same `plan.json` that
`disc-apply` reads.

Most of the machinery exists: `disc-apply`'s review loop already walks items
with their evidence and takes `enter`/`e`/`r`/`k`/`f`/`q`. What is missing is a
way to produce a plan with empty proposals for a human to fill. Depends on
DP-09.

## DP-11 — TV series support — `todo`

Ripping and identifying episodic discs. The largest feature here; wants the
refactor finished first.

Note the numbering trap already hit by hand: TheTVDB numbers per segment,
Wikipedia numbers per half-hour block, and a disc's titles may match either.

## DP-12 — Interlacing detection — `todo`

Self-contained; can jump the queue.

`ffmpeg -filter:v idet` counts frames as TFF, BFF, progressive or
undetermined, so a source and its transcode can be measured and compared.
Preventing it is a HandBrake question -- comb detection deinterlaces only
frames actually flagged combed. Verify how `transcode-video.rb` exposes that
before promising a flag.

## DP-13 — Re-evaluate the language — `todo`

Deferred until feature-complete, as agreed. Rust, Go, Ruby, Bash all on the
table. The original reason for Python stands until the evidence says otherwise:
seven readable scripts that can be repaired individually beat one binary that
fails as a unit.

## DP-14 — Evaluate a GUI — `todo`

Parked deliberately. Swift, for people who do not want a terminal. Capture,
plan and evaluate before deciding whether to support one.
