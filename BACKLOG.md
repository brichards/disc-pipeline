# Backlog

Open items, in the order to work them, except DP-12, which depends on nothing.

Status: `todo`, `doing`. Reference the ID in commit messages.

## DP-31 — Write the README in STE — `todo`

You tuned the README by hand in `756bb9e`, on 2026-09-19. After that, 12
commits that Claude co-authored changed it: 64 lines added and 23 removed.
Review each of those changes against the tuned version, then write the README
in STE.

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

## DP-28 — Stages and folders outside the queue — `todo`

For discussion. Since DP-27, a stage refuses a folder outside the queue. Two
functions can replace the refusal. A stage can have one function or the two
functions together:

- The stage moves the folder into the queue after you accept the move. The
  drainer then controls the disc.
- A stage that you run by hand can use a folder in a different location. The
  drainer ignores that folder.

For the second function, a stage must find a manifest from its folder. At this
time, `manifest.load` finds a manifest only from its slug in the queue root.

## DP-13 — Re-evaluate the language — `todo`

Deferred until feature-complete. The original reason for Python stands until
evidence says otherwise: seven scripts repairable individually beat one binary
that fails as a unit.

## DP-14 — Evaluate a GUI — `todo`

Parked. Swift, for people who do not want a terminal.
