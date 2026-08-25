# disc-pipeline

Takes a Blu-ray or DVD from insertion to a named, transcoded file on the NAS.

Seven stages. Five run unattended; two stop and ask. The pipeline only runs on
the days you're actually ripping — there is no resident daemon.

```
disc-watch → disc-rip → disc-verify → disc-identify → [you] → disc-transcode → disc-ship → [you]
                                                    disc-apply                          disc-cleanup
```

`disc-run` decides which of those can run and starts it; `disc-run --watch`
keeps doing that until only the gates are left.

## Requirements

Everything is Python standard library — no `pip`, no virtualenv, no
dependencies to go missing between uses. External tools are called as
subprocesses.

| Tool | Used by | Notes |
| --- | --- | --- |
| Python 3.9+ | all | `/usr/local/bin/python3` via Homebrew |
| MakeMKV | `disc-rip` | Needs a current beta key for Blu-ray |
| ffmpeg / ffprobe | `disc-identify`, `disc-transcode` | Frame extraction and resolution routing |
| `transcode-video.rb` | `disc-transcode` | 1080p and below |
| `hevc-transcode.rb` | `disc-transcode` | Above 1080p |
| `rsync` | `disc-ship` | Ships to the NAS and verifies the copy |
| ffmpeg | `disc-verify` | Decodes a suspect rip to prove it is intact |
| Claude Code CLI | `disc-identify` | Runs headless to name the ripped titles |
| HandBrakeCLI | `disc-transcode` | Called by the transcode scripts |

## Install

```sh
git clone git@github.com:brichards/disc-pipeline.git ~/Sites/Scripts/disc-pipeline
ln -s ~/Sites/Scripts/disc-pipeline/bin/* /usr/local/bin/
```

Or add `bin/` to your `PATH`. Every script has a shebang and is executable, so
they run as `disc-rip`, not `python3 disc-rip.py`.

## Usage

Insert a disc and `disc-watch` starts a session automatically. Otherwise drive
it by hand — every stage runs standalone.

Stages that act on a rip take a queue slug or a directory, and **default to the
current directory**, so the usual way to work is to cd into a rip:

```sh
cd ~/Movies/Rips/taken-2-2012-a91c4f
disc-identify               # propose names for the ripped titles
disc-apply                  # review the proposal, then rename
disc-transcode
disc-ship
```

Or name the target explicitly from anywhere:

```sh
disc-identify "~/Movies/Rips/Taken 2 (2012)"
disc-apply taken-2-2012-a91c4f
```

The rest are not per-rip:

```sh
disc-rip                    # scan the drive, triage titles, rip, eject
disc-status                 # where every disc stands and what it's waiting on
disc-cleanup                # retention prompts for shipped, verified discs
disc-run --watch            # drain the queue until it's idle
```

Each stage checks its own prerequisites and says which directory it looked in —
`disc-identify` needs `.mkv` files, `disc-apply` needs a `plan.json`.

## Feeding discs unattended

`disc-watch` is a LaunchAgent that notices a disc and starts work on it. Install
it once:

```sh
disc-watch --install
```

Then feed discs one at a time. Each rips, gets identified, and ejects on its
own, so you can insert the next without watching a terminal. You end up with a
queue of discs sitting at the review gate.

### Flags

| Flag | What it does |
| --- | --- |
| `--install` | Write the plist to `~/Library/LaunchAgents` and load it |
| `--uninstall` | Unload and delete the plist |
| `--status` | Report whether the agent is loaded and the plist present |
| `--once` | Run the check now, in the foreground, and wait for it to finish |
| `--no-identify` | Rip and verify only; defer identification (see below) |

### What it does when it fires

1. Looks for `BDMV/index.bdmv` or `VIDEO_TS/VIDEO_TS.IFO` under `/Volumes`.
2. Steps aside if a rip already holds the drive lock.
3. Fingerprints the disc and checks the ledger. **A disc already ripped is
   ejected, not re-ripped** — a duplicate in the stack costs seconds.
4. Checks free space.
5. Starts `disc-rip --wait` chained into `disc-identify`, detached, with output
   to `<slug>/logs/watch.log`.

### Behaviour worth knowing

**It is event-driven, not a timer.** launchd only wakes it when `/Volumes`
changes, so it costs nothing on the days you are not ripping. It also fires on
every *eject*, which is why the drive-lock check comes early — that firing is a
no-op.

**Its failure mode is benign and self-announcing.** It is the first link in the
chain, so if it stops working you insert a disc, nothing happens, and you notice
immediately. Run `disc-rip` by hand and nothing is lost. Compare that to a
watcher buried mid-pipeline, where a silent failure looks like the pipeline
working.

**A disc is ejected once it is known good.** A clean rip ejects immediately.
One with read errors stays in the drive until `disc-verify` decodes it — if
every affected title is intact, `disc-verify` ejects it; if not, it stays put,
because the next thing to try is cleaning it and re-ripping. A disc with failed
titles always stays. `--no-eject` on either stage overrides.

Ejection is fingerprint-guarded: verification can finish long after the rip, so
the drive is checked to still hold the same disc before anything is ejected.

**The plist carries an explicit `PATH`**, captured from your shell at install
time. launchd does not inherit one, and every stage shells out to `ffmpeg`,
`rsync`, or the `claude` CLI. **Re-run `disc-watch --install` if you move the
project or change your `PATH`** — the plist holds absolute paths and a snapshot
of the environment, neither of which updates itself.

### Deferring identification

Identification runs serially and costs roughly **$1.44 and four minutes per
disc**, because it reads contact sheets and looks the release up. Ripping a
stack of six is a fair bit of both, spent while you are not looking at the
results anyway.

`--no-identify` shortens the chain to rip and verify, leaving each disc at
`ripped`:

```sh
disc-watch --no-identify
```

**It defers rather than skips.** A disc left at `ripped` is still the drainer's
next job, so `disc-run` picks it up whenever you get to it — or name discs
individually:

```sh
disc-identify casino-royale-f49b43
```

**The installed agent ignores this flag.** launchd invokes `disc-watch` with no
arguments, so `--no-identify` only affects invocations you type. To make the
agent defer identification for a whole session, add the flag to the plist's
`ProgramArguments` and reload:

```sh
/usr/bin/plutil -insert ProgramArguments.1 -string --no-identify ~/Library/LaunchAgents/net.rzen.disc-pipeline.watch.plist
```

Then `launchctl unload` and `launchctl load` the plist. Re-running
`disc-watch --install` rewrites it without the flag, which is how you undo it.

### Watching a session

Everything a stage prints goes to **one log at the queue root**, tagged with
the disc it belongs to, so a stack of discs is a single file to tail:

```sh
tail -f ~/Movies/Rips/watch.log
```

The tag matters because ripping is serialised on the drive lock but
identification is not — one disc's identify can overlap the next disc's rip.

That log answers *what is happening*. For *where does everything stand*, which
is the question when several discs are queued behind two gates:

```sh
disc-status
```

```
/Users/brian/Movies/Rips    150.2 GB free

 ! casino-royale-f49b43  held       needs 52.4 GB, 17.6 GB free  [re-run to retry]
                         -> disc-rip
   warm-bodies-a99d66    applied    3/12 transcoded
                         -> disc-transcode warm-bodies-a99d66
```

A `!` marks a disc waiting on you. `--json` gives the same thing
machine-readably.

### If nothing happens on insert

```sh
disc-watch --status          # is it loaded?
disc-watch --once            # run the same check in the foreground
tail -f ~/Movies/Rips/watch.log
```

The agent's own output goes to `watch.log` at the queue root; each disc's rip
and identify output goes to `<slug>/logs/watch.log`.

## Layout

State lives on disk, one directory per disc, so any stage can be resumed or
re-run.

```
~/Movies/Rips/
├── ledger.jsonl              # every disc ever seen, keyed by fingerprint
├── overrides.json            # hard-won answers: fingerprint → correct playlist
└── <disc-slug>/
    ├── manifest.json         # disc info, title triage, stage status
    ├── plan.json             # proposed names, evidence, your decisions
    ├── raw/                  # MakeMKV output, untouched
    ├── frames/               # title cards pulled during identification
    ├── rejected/             # demoted titles — moved, never deleted
    ├── transcoded/           # shaped exactly as it ships to the NAS
    └── logs/
```

`manifest.json` is the single source of truth for stage state. The ledger holds
identity and disposition only, so it can outlive the queue directory after
cleanup.

Run against a loose directory of `.mkv` files rather than a queue entry and the
working files go into a `.disc-pipeline/` subdirectory instead, which keeps them
out of Plex's way.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISC_PIPELINE_ROOT` | `~/Movies/Rips` | Queue root |
| `DISC_PIPELINE_NAS` | `/Volumes/Media` | Library root, holding `Movies/` and `TV Shows/` |

## Reclaiming space

`disc-cleanup` runs whenever you get to it, over everything that has shipped —
deliberately not chained to shipping, because you cannot know whether to keep a
source in the minute the transfer finishes. The interlaced-cartoon case only
surfaces once you watch the result, and that is exactly when you want the raw
file still there.

```sh
disc-cleanup                 # every shipped disc
disc-cleanup <slug>          # just one
disc-cleanup --verify-only   # re-check the NAS copies, offer nothing
```

It re-proves the copy before offering anything. The check at ship time is not
enough — that was then, and a NAS can lose a file in between. Only after a fresh
checksum comparison does it ask, **separately, per folder**:

- **Transcoded output** — what shipped. Safe to delete; keep it only to re-ship
  without re-transcoding.
- **Source files** — keep these if the transcode might need redoing. Recovering
  them otherwise means the disc goes back in the drive.

Two things are never offered. A source taller than 1080p is kept automatically,
because re-ripping a UHD disc to recover a master is not a trade worth making
twice. And a disc whose `keep_source` is `always` is skipped.

Deletion refuses any path outside the queue root, and nothing is deleted without
a yes, per disc and per folder.

## Design notes

**Nothing is ever deleted.** Rejected titles are moved aside; retention prompts
are explicit and per-folder.

**Exit code zero is not success.** MakeMKV works around bad reads and exits
clean, so `disc-rip` scans its output for corruption messages and flags the rip
suspect regardless of exit status.

**A suspect rip gets proved rather than guessed at.** `disc-verify` decodes
every frame and discards the output — silence means the file is fine. It runs
*before* identification, because identifying costs money and minutes and there
is no sense paying that for a rip that turns out to be unusable. A 33 GB, 2:24
feature takes about five minutes, which is cheap enough to do automatically. A
clean rip skips it entirely, so it sits unconditionally in the chain.

**A title index is a position, not an identity.** It depends on the minimum
length used to enumerate, so every MakeMKV call has to agree on that value or
the wrong title gets ripped. Rips are verified against the expected runtime for
the same reason.

**Some discs fight back.** Lionsgate releases in particular ship dozens of decoy
playlists — RED 2 presents 130 feature-length titles, identical in chapter
count, size, and stream layout. When the cluster metric trips, `disc-rip` works
a resolution ladder rather than guessing, and records the answer in
`overrides.json` so the disc is only ever solved once.

## Status

Under construction. See `git log` for what's landed.

## References

- [Plex: local files for trailers and extras](https://support.plex.tv/articles/local-files-for-trailers-and-extras/)
- [MakeMKV CLI docs](https://www.makemkv.com/developers/usage.txt)
- [TheTVDB](https://thetvdb.com) — episode numbering for TV discs (v2)
