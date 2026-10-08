# Backlog

Open items, in the order to work them. An item has no ID. The pull request that
completes an item deletes it from this file.

## Eject a ripped disc after the screen unlocks

While the screen is locked, loginwindow refuses each eject: "Unmount was
dissented by PID 168 (loginwindow)". A test on 2026-10-08 confirmed this, and
the same eject worked after the unlock. `disc-rip` tries for about 30 seconds,
so a disc ripped while the screen is locked stays in the drive.

On each pass, the drainer ejects a disc that is in the drive, is in the
ledger, and that no stage uses. The disc then comes out on the first pass
after the unlock, while a session is open. A rip with read errors stays in the
drive until `disc-verify` checks it.

## Write the README in STE

You tuned the README by hand in `756bb9e`, on 2026-09-19. After that, 12
commits that Claude co-authored changed it: 64 lines added and 23 removed.
Review each of those changes against the tuned version, then write the README
in STE.

Expand the "Decoy discs" section with this text:

> Studios like Lionsgate use playlist obfuscation to make Blu-ray copying
> harder. The [MakeMKV forum's Blu-ray
> section](https://forum.makemkv.com/forum/viewforum.php?f=8) keeps a thread
> for most obfuscated titles. Searching for "[title] mpls
> site:forum.makemkv.com" usually finds the right playlist number.

## Take each command's --help description from its docstring

Each command now states its purpose three different ways: in `--help`, in its
module docstring and in the README. `argparse` can take its description from
the module docstring, so the two cannot differ. The command's README section
then starts with the same sentence.

## Test the README flag tables against the commands

A test compares the flag table of each command in the README with the flags
that `argparse` defines. At this time, the two agree for each command.

## Add usage examples to --help

An `argparse` epilog shows the same usage examples as the README section of
the command.

## Move the command docs into docs/

When the README gets too long, the README keeps the overview, the install
steps and a quick start. Each command gets one page in `docs/`. Use `docs/`,
not a GitHub wiki: a pull request cannot change a wiki with the code, and a
clone does not include the wiki.

## Remove triage.select_feature

`triage.select_feature` has no caller in `bin/`, `discpipe/` or `tests/`.

## Show the correct retry command in disc-status

For each retryable hold, `disc-status` shows `disc-rip` as the command. A
retryable hold can also come from `disc-identify`, when the agent is not
available, or from `disc-ship`, when the NAS is not mounted. `held_stage`
records the stage. The code shows this problem. Nobody has seen it in
operation.

## CONTRIBUTING

Covers running the tests and the conventions: one thought per commit, one
branch per change, the import-plus-`--help` verification, and the rules in
CLAUDE.md.

## Split disc-identify's mechanical and agentic halves

Run frame extraction and signal gathering with no agent; make the agent half
provider-agnostic so a local model can be substituted. `--frames-only` and
`--from-log` already do part of this. Find the real seam before designing an
interface.

## Interactive identify

Show a person the evidence the agent gets and let them name each title and
pick a type, producing the `plan.json` `disc-apply` reads. `disc-apply`'s
review loop already walks items with their evidence; what is missing is a plan
with empty proposals. Depends on the split of disc-identify.

## TV series support

Note the numbering trap: TheTVDB numbers per segment, Wikipedia per half-hour
block, and a disc may match either.

## Interlacing detection

Self-contained. `ffmpeg -filter:v idet` counts TFF/BFF/progressive/
undetermined frames, so source and transcode can be compared. Preventing it is
a HandBrake comb-detection question; verify how `transcode-video.rb` exposes
that before promising a flag.

## Re-evaluate the UHD routing

`hevc-transcode.rb` comes from `more-video-transcoding`, which its author has
stopped developing: "all the ratecontrol systems and behaviors here have been
rolled into the redesigned and rewritten version of `transcode-video.rb`."

So the above-1080p branch in `transcode.route()` may be routing to a
deprecated script for behavior the current `transcode-video.rb` already has.
Check what the rewritten script does with UHD before deciding. Related to
interlacing detection, since comb detection sits in the same tool.

## Stages and folders outside the queue

For discussion. A stage refuses a folder outside the queue. Two functions can
replace the refusal. A stage can have one function or the two functions
together:

- The stage moves the folder into the queue after you accept the move. The
  drainer then controls the disc.
- A stage that you run by hand can use a folder in a different location. The
  drainer ignores that folder.

For the second function, a stage must find a manifest from its folder. At this
time, `manifest.load` finds a manifest only from its slug in the queue root.

## Re-evaluate the language

Deferred until feature-complete. The original reason for Python stands until
evidence says otherwise: seven scripts repairable individually beat one binary
that fails as a unit.

## Evaluate a GUI

Parked. Swift, for people who do not want a terminal.
