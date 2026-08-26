# disc-pipeline

A set of utility scripts to assist in ripping and transcoding physical media
from DVD and Blu-ray discs.

Put a disc in the drive and the pipeline rips it, works out what each title
actually is, names everything to Plex's conventions, transcodes it, copies it to
your library, and ejects the disc so you can feed the next one. It stops and
asks you twice: once before deleting anything local, and once more only if the
naming came back uncertain.

It is not a daemon. Nothing runs on the days you are not ripping.

```
disc-watch → disc-rip → disc-verify → disc-identify → disc-apply → disc-transcode → disc-ship → disc-cleanup
```

`disc-run` decides which of those can run next and starts it. `disc-status`
shows where everything stands.

## Why it exists

Ripping a disc is the easy part. The work is everything after: a Blu-ray
routinely presents dozens of titles, and telling a real featurette from a
chapter of the main feature, a duplicate playlist, or a trailer for a different
film takes actually looking at the video. Get it wrong and you end up with a
library full of files named `Title-07.mkv`, or worse, a movie that plays with
scenes out of order.

These scripts automate the mechanical parts and hand the judgment call to an
agent that reads title cards, checks runtimes against the disc's published
feature list, and explains why it thinks each file is what it says it is. You
review its reasoning rather than the files.

## Requirements

Everything in this project is Python standard library — no `pip`, no
virtualenv, no dependencies to go missing between uses. External tools are
called as subprocesses.

| Tool | Needed by | Install |
| --- | --- | --- |
| Python 3.9+ | everything | `brew install python` |
| [MakeMKV](https://www.makemkv.com) | `disc-rip` | `brew install --cask makemkv` |
| [FFmpeg](https://ffmpeg.org) | `disc-identify`, `disc-verify`, `disc-transcode` | `brew install ffmpeg` |
| [HandBrakeCLI](https://handbrake.fr) | `disc-transcode` | `brew install handbrake` |
| [video_transcoding](https://github.com/lisamelton/video_transcoding) | `disc-transcode` | `gem install video_transcoding` |
| [Claude Code](https://claude.com/claude-code) | `disc-identify` | `npm install -g @anthropic-ai/claude-code` |
| rsync | `disc-ship` | ships with macOS |

Two notes on those.

**MakeMKV needs a key to read Blu-ray discs.** The beta key is free and posted
on [the MakeMKV forum](https://forum.makemkv.com/forum/viewtopic.php?t=1053),
but it expires every couple of months. DVDs work without one.

**video_transcoding provides `transcode-video.rb` and `hevc-transcode.rb`**,
Lisa Melton's tools for producing files much smaller than the source while
staying hard to tell apart from it. `disc-transcode` calls whichever suits the
source resolution. If you want different encoding settings, those are the files
to configure rather than anything here.

## Install

Clone anywhere and put `bin/` on your `PATH`:

```sh
git clone https://github.com/brichards/disc-pipeline.git
echo 'export PATH="$PATH:/path/to/disc-pipeline/bin"' >> ~/.zshrc
```

Every script has a shebang and is executable, so they run as `disc-rip`, not
`python3 disc-rip.py`.

Two paths are configurable, both by environment variable:

| Variable | Default | What it is |
| --- | --- | --- |
| `DISC_PIPELINE_ROOT` | `~/Movies/Rips` | Working directory: one folder per disc |
| `DISC_PIPELINE_NAS` | `/Volumes/Media` | Your library, containing `Movies/` and `TV Shows/` |

Nothing else is configurable, on purpose. Behavior is decided rather than
switched.

## Getting started

Install the watcher once:

```sh
disc-watch --install
```

Then insert a disc. It rips, verifies, identifies itself, and ejects. Start the
drainer and the rest happens on its own:

```sh
disc-run --watch
```

Check on it whenever:

```sh
disc-status
```

```
/Users/you/Movies/Rips    150.2 GB free

   casino-royale-f49b43  applied    4/10 transcoded
                         -> disc-transcode casino-royale-f49b43
 ! taken-2-2012-a91c4f   identified 20 file(s) proposed
                         -> disc-apply taken-2-2012-a91c4f
```

A `!` marks a disc waiting on you. Everything a stage prints also goes to a
single log, tagged with the disc it belongs to:

```sh
tail -f ~/Movies/Rips/watch.log
```

You can also skip the automation entirely and run each stage by hand. They all
work standalone.

## How a disc moves through

Each stage does one job and records where the disc got to. Nothing calls
anything else — `disc-run` reads that state and starts whatever can run next,
which is what makes the whole thing resumable. Kill it mid-transcode, start it
again, and it picks up at the next file.

Stages that act on a disc take a **queue slug or a directory**, and default to
the current directory. So the usual way to work by hand is to change into a
disc's folder and run bare commands.

| Stage | What it does | Stops for you? |
| --- | --- | --- |
| `disc-watch` | Notices a disc and starts work on it | |
| `disc-rip` | Triages titles, rips them, ejects the disc | |
| `disc-verify` | Decodes a rip that reported read errors | |
| `disc-identify` | Works out what each file is, proposes names | |
| `disc-apply` | Applies the names | only if uncertain |
| `disc-transcode` | Encodes what survived review | |
| `disc-ship` | Copies to the library and proves it arrived | |
| `disc-cleanup` | Offers to reclaim local space | yes |

### Where files live

One folder per disc, everything visible:

```
~/Movies/Rips/
├── ledger.jsonl              # every disc ever seen
├── overrides.json            # answers for discs that fought back
├── watch.log
└── casino-royale-f49b43/
    ├── manifest.json         # where this disc stands
    ├── plan.json             # proposed names, evidence, your decisions
    ├── raw/                  # what MakeMKV produced
    ├── frames/               # contact sheets used to identify the titles
    ├── rejected/             # demoted files — moved, never deleted
    ├── transcoded/           # shaped exactly as it ships
    └── logs/
```

`manifest.json` is the single source of truth for stage state. The ledger holds
identity and disposition only, so it outlives the folder after cleanup.

Already have a folder of files ripped by hand? Point any stage at it and it
becomes a disc folder — it gains a manifest, its media moves into `raw/`, and it
keeps its own name. The drainer picks it up from there. Adoption only happens
when you point a command at a folder, never on its own, so a directory you are
still copying into stays untouched.

---

## Commands

### disc-watch

Notices a disc and starts work on it. A LaunchAgent that macOS wakes only when
`/Volumes` changes, so it costs nothing on the days you are not ripping.

```sh
disc-watch --install      # set it up once
disc-watch --status       # is it loaded?
disc-watch                # run the same check by hand
```

| Flag | Effect |
| --- | --- |
| `--install` | Write the LaunchAgent and load it |
| `--uninstall` | Unload and delete it |
| `--status` | Report whether it is loaded |
| `--once` | Run the check in the foreground and wait for it to finish |
| `--no-identify` | Rip and verify only; leave naming for later |

On a disc it fingerprints, checks whether it has been ripped before, checks free
space, then starts ripping in the background. **A disc already in the ledger is
ejected rather than ripped again**, so a duplicate in the stack costs seconds.

The LaunchAgent captures your `PATH` at install time and stores absolute paths,
so **re-run `--install` if you move the project or change your `PATH`**.

Identification costs money and time — roughly $1.44 and four minutes per disc.
`--no-identify` defers it rather than skipping it; the disc waits at `ripped`
and the drainer picks it up later. Note the installed agent ignores this flag,
since macOS invokes the script with no arguments. To defer for a whole session,
add the flag to the LaunchAgent's `ProgramArguments` and reload it.

### disc-rip

Scans the disc, decides which titles are worth keeping, rips them, and ejects.

```sh
disc-rip                  # rip whatever is in the drive
disc-rip --dry-run        # scan and triage only
disc-rip --redo           # retry titles that failed
```

| Flag | Effect |
| --- | --- |
| `--disc N` | MakeMKV drive index, for more than one drive |
| `--force` | Rip a disc that is already in the ledger |
| `--dry-run` | Scan and triage; rip nothing |
| `--redo` | Re-rip titles already recorded as done |
| `--no-eject` | Leave the disc in the drive even on a clean rip |
| `--wait` | Block for the drive lock instead of stepping aside |

Titles shorter than four minutes are skipped. **A failed title does not stop the
disc** — the rest still rip, and re-running retries only what failed, because
the disc being in the drive is the expensive part.

The disc ejects as soon as there is nothing more the drive can do for it. A
clean rip ejects immediately. Read errors leave it loaded only until
`disc-verify` has ruled, then it goes either way. A hold ejects too, unless the
cause is something you fix without touching the disc — no free space, share
offline — in which case it stays loaded so you can just re-run.

That matters for more than tidiness: when a drive wedges mid-rip, ejecting is
itself the first thing to try.

### disc-verify

Decodes a rip that reported read errors and finds out whether it is actually
damaged.

```sh
disc-verify               # check whatever needs checking
disc-verify --all         # check every title, not just suspect ones
```

| Flag | Effect |
| --- | --- |
| `--all` | Check every title, not only those with read errors |
| `--force` | Re-check titles already verified |
| `--wait` | Block for the CPU lock instead of stepping aside |
| `--no-eject` | Leave the disc in the drive even once it verifies |

MakeMKV works around unreadable sectors and still exits successfully, which
means a damaged rip reaches your library looking exactly like a good one. This
decodes every frame and discards the output: silence means the file is intact.
A 33 GB feature takes about five minutes.

It runs before identification, since identifying costs real money and there is
no sense paying that for a rip that turns out to be unusable. **A clean rip
exits immediately**, so it costs nothing when there is nothing to check.

### disc-identify

Works out what each ripped file actually is, and proposes names.

```sh
disc-identify
disc-identify --frames-only    # build contact sheets, skip the agent
disc-identify --from-log       # rebuild the plan from the last run
```

| Flag | Effect |
| --- | --- |
| `--refresh-frames` | Rebuild contact sheets even if they exist |
| `--frames-only` | Build the inventory and sheets, then stop |
| `--from-log` | Re-derive the plan from the saved run, without calling the agent again |
| `--timeout N` | Seconds before the agent is given up on (default 1800) |
| `--model NAME` | Override the model |

For each file it probes the streams and builds two contact sheets — the first 75
seconds in 3-second steps, where title cards live, and 16 frames spread across
the runtime. Those go to a headless Claude Code session along with an inventory,
which reads them, looks up what the disc actually ships, and writes `plan.json`.

It proposes; it never renames. Every entry carries the evidence behind it —
title card text, a runtime that matched and its source, or where in the feature
a file's footage sits — so review means reading reasons rather than opening
files.

`--from-log` matters because a run costs money: if the plan format changes, you
can rebuild it from the saved response instead of paying twice.

### disc-apply

Applies the naming plan, after review.

```sh
disc-apply                # review it item by item
disc-apply --dry-run      # show what would happen
disc-apply --revert       # put the files back
```

| Flag | Effect |
| --- | --- |
| `--yes` | Accept every proposal without review |
| `--auto` | Accept only if every item came back high confidence |
| `--reset` | Put the files back, then review again |
| `--revert` | Put the files back under their original names |
| `--dry-run` | Show what would happen; change nothing |

Review walks each item with its evidence: `enter` accepts, `e` edits the name,
`r` rejects, `k` leaves the file alone, `f` opens the contact sheets, `q` stops.
Decisions save as you make them, so quitting and resuming picks up where you
left off. A final summary lists every rename and move before anything happens.

**The drainer applies plans on its own** using `--auto`, which accepts only when
every item is high confidence and nothing was left unidentified. One uncertain
item sends the whole disc to review, because the items are judged together. So
this is a gate exactly when there is something worth looking at.

Rejected files are moved to `rejected/`, never deleted. `--revert` puts
everything back, which is how to recover a wrongly rejected extra without
putting the disc back in the drive.

### disc-transcode

Encodes what survived review.

```sh
disc-transcode
disc-transcode --dry-run --quiet
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show the commands; transcode nothing |
| `--force` | Redo files already marked done |
| `--wait` | Block for the CPU lock instead of stepping aside |
| `--quiet` | Hide the transcoder's progress output |

Routes on resolution: above 1080p to `hevc-transcode.rb`, otherwise
`transcode-video.rb`, both carrying all subtitle tracks through.

Output is shaped exactly as it will ship — a movie folder when more than one
file is involved, a bare file when the feature is all there is, because Plex
needs the folder for extras to attach and does not want one otherwise.

Progress is tracked per file, so an interrupted run resumes at the next file
rather than restarting a two-hour feature. Files already in the target format
are linked rather than re-encoded, so pointing this at already-transcoded
content costs nothing.

**The drainer transcodes quietly** using `--quiet`, because the transcoders
print a line per percent and every disc writes to the same log — an hour of
encoding would bury a rip running beside it. The start and finish lines for
each file still appear. Run the stage yourself to watch the encode live.

### disc-ship

Copies the transcoded output to your library and proves it arrived.

```sh
disc-ship
disc-ship --dry-run
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show what would be copied; copy nothing |
| `--force` | Overwrite files already at the destination |
| `--wait` | Block for the network lock instead of stepping aside |
| `--quiet` | Hide rsync progress |

Two checks make this safe to run unattended. It **confirms the share is really
mounted** rather than just that the path exists — an unmounted share leaves a
bare directory on your startup disk that looks writable and is not. And it
**verifies the copy** afterward with a checksum comparison, so success means
every byte arrived rather than that rsync did not complain.

A name collision parks the disc instead of overwriting. If a movie is already in
your library as a single file and extras turn up later, the existing file is
moved into a folder first, since Plex needs the folder for extras to attach.

### disc-cleanup

Offers to reclaim local space, once there is proof the media is safe elsewhere.

```sh
disc-cleanup              # every shipped disc
disc-cleanup --dry-run    # show what would go
```

| Flag | Effect |
| --- | --- |
| `--verify-only` | Re-check the copies in your library; offer nothing |
| `--dry-run` | Show what would be deleted; delete nothing |

Deliberately not chained to shipping: you cannot know whether to keep a source
in the minute the transfer finishes. A bad crop or an interlaced cartoon only
shows up once you watch the result, and that is exactly when you want the
original still there.

It re-proves the copy before offering anything, then asks separately about the
transcoded output and the source files, because the case that comes up is
discarding a bad transcode while keeping the source to retry.

Once both are gone it offers the disc folder itself — the manifest, the plan,
contact sheets, logs, and anything left in `rejected/`, which it names rather
than sweeping up silently. Accept and the only remaining record of the disc is
its ledger entry; the result lives in your library. Verification gates the media
prompts only, since what is left afterward has no counterpart on the NAS to
check against.

This is the only code in the project that deletes anything, so the delete site
re-establishes every precondition itself:

| Guard | Refuses |
| --- | --- |
| Inside the working directory | Any path outside `DISC_PIPELINE_ROOT` |
| Not the root itself | The working directory, however it was reached |
| Symlinks resolved first | A link inside the queue pointing out of it |
| Provenance | A path with no manifest beside it |
| Shipped only | Anything that has not reached your library |
| Freshly verified | Anything whose copy does not match *right now* |
| Explicit consent | Anything you did not answer `y` to |
| Masters | Sources above 1080p, kept automatically |

### disc-run

Decides what can happen next and starts it.

```sh
disc-run                  # one pass
disc-run --watch          # keep going until only the gates are left
disc-run --dry-run        # report what would start
```

| Flag | Effect |
| --- | --- |
| `--watch` | Keep polling until nothing is left to advance |
| `--interval N` | Seconds between passes (default 30) |
| `--grace N` | Seconds idle before a watch session exits (default 120) |
| `--dry-run` | Report what would start; start nothing |

Stages never call each other. Each records where it got to, and this reads that
and launches whatever can run — which is why the pipeline survives being killed
partway through.

It respects one lock per resource: one optical drive, one CPU budget, one
network link. Anything already holding a lock, including a stage you started by
hand, is left alone. A session holds off idle sleep for exactly as long as it
runs, and exits on its own once only the gates remain.

### disc-status

Shows where every disc stands and what it is waiting on.

```sh
disc-status
disc-status --json
```

| Flag | Effect |
| --- | --- |
| `--json` | Machine-readable output |

Reads state from disk and starts nothing. A log tells you what happened; this
tells you what needs you.

---

## Design notes

**Nothing is deleted except by `disc-cleanup`, and only with your say-so.**
Rejected files are moved aside. Every other stage only adds.

**Exit code zero is not success.** MakeMKV works around bad reads and exits
clean, so `disc-rip` reads its output for corruption messages and flags the rip
suspect regardless of what it returned.

**A title index is a position, not an identity.** It depends on the minimum
length used to enumerate titles, so every MakeMKV call has to agree on that
value or a different title gets ripped than the one you asked for. Rips are
checked against the expected runtime for the same reason.

**Some discs fight back.** Lionsgate releases in particular ship dozens of decoy
playlists — RED 2 presents 130 feature-length titles, identical in chapter
count, size, and stream layout, differing only in which short alternate segments
they splice in. Pick wrong and the film plays with a scene looping. When that
pattern is detected, `disc-rip` works a resolution ladder rather than guessing,
and records the answer in `overrides.json` so the disc is only ever solved once.

**Extras are named to
[Plex's conventions](https://support.plex.tv/articles/local-files-for-trailers-and-extras/)**
— `Descriptive Name-<type>.mkv`, where the type is one of `behindthescenes`,
`deleted`, `featurette`, `interview`, `scene`, `short`, `trailer`, or `other`.

## Not yet supported

**TV discs.** The queue records a media type and routes to `TV Shows/`, but
episode identification needs subtitle extraction and a numbering scheme that
handles shows pairing two segments per half-hour, where broadcast and database
numbering disagree. Movies only for now.

## References

- [Plex: local files for trailers and extras](https://support.plex.tv/articles/local-files-for-trailers-and-extras/)
- [MakeMKV CLI documentation](https://www.makemkv.com/developers/usage.txt)
- [video_transcoding](https://github.com/lisamelton/video_transcoding) — the transcoders this calls
- [TheTVDB](https://thetvdb.com) — episode numbering, for when TV support lands

## License

MIT. See [LICENSE](LICENSE).
