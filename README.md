# disc-pipeline

Takes a Blu-ray or DVD from insertion to a named, transcoded file on the NAS.

Seven stages. Five run unattended; two stop and ask. The pipeline only runs on
the days you're actually ripping — there is no resident daemon.

```
disc-watch → disc-rip → disc-identify → [you] → disc-transcode → disc-ship → [you]
                                      disc-apply                          disc-cleanup
```

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
| Claude Code CLI | `disc-identify` | Runs headless to name the ripped titles |

## Install

```sh
git clone git@github.com:brichards/disc-pipeline.git ~/Sites/Scripts/disc-pipeline
ln -s ~/Sites/Scripts/disc-pipeline/bin/* /usr/local/bin/
```

Or add `bin/` to your `PATH`. Every script has a shebang and is executable, so
they run as `disc-rip`, not `python3 disc-rip.py`.

## Usage

Insert a disc and `disc-watch` starts a session automatically. Otherwise drive
it by hand — every stage runs standalone:

```sh
disc-status                 # what's in the queue and what each disc is waiting on
disc-rip                    # scan the drive, triage titles, rip
disc-identify <disc>        # propose names for the ripped titles
disc-apply <disc>           # review the proposal, then rename
disc-transcode <disc>
disc-ship <disc>
disc-cleanup                # retention prompts for shipped, verified discs
disc-run --watch            # drain the queue until it's idle
```

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

Override the root with `DISC_PIPELINE_ROOT`.

## Design notes

**Nothing is ever deleted.** Rejected titles are moved aside; retention prompts
are explicit and per-folder.

**Exit code zero is not success.** MakeMKV works around bad reads and exits
clean, so `disc-rip` scans its output for corruption messages and flags the disc
regardless of exit status.

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
