# disc-pipeline

A series of scripts for macOS to automatically convert your DVDs and Blu-ray discs into a digital media library (e.g. Plex, Jellyfin, et al).

Insert a disc and the pipeline will rip, identify, name, transcode, and transfer the finished files. It targets the main feature and disc extras, including audio and subtitle tracks according to your MakeMKV preferences (Preferences → Advanced).

Discs are ejected automatically when finished, and another disc can begin while previous stages are still in progress. Afterward, a manual cleanup step helps delete the artifacts from any/all stages, with separate verification and validation on each step for each disc.

## How it works

A disc moves through the stages below. Each stage does one job, records its progress in the disc's `manifest.json`, and exits; `disc-run` reads every manifest and calls the next stage for each disc. Because progress lives on disk rather than in a running process, an interrupted pipeline resumes where it left off.

| Stage | Description |
| --- | --- |
| [`disc-watch`](#disc-watch) | Notices a disc in the drive and starts ripping it. |
| [`disc-run`](#disc-run) | Automatically calls the next stage for any incomplete disc. `disc-run --watch` will persist until every stage is finished. |
| [`disc-rip`](#disc-rip) | Rips every title above the configured minimum length, then ejects the disc. |
| [`disc-verify`](#disc-verify) | Verifies file integrity of titles that ripped with errors. |
| [`disc-identify`](#disc-identify) | Generates artifacts to help identify each file, prompts an LLM to generate a plan to rename or remove each file. |
| [`disc-apply`](#disc-apply) | Automatically renames or rejects files according to the identify plan. Holds disc for an interactive review if any file was uncertain. |
| [`disc-transcode`](#disc-transcode) | Encodes the kept files. |
| [`disc-ship`](#disc-ship) | Copies the finished files to your media library and checksums the result. |
| [`disc-status`](#disc-status) | Shows where every disc stands and which ones need attention. |
| [`disc-cleanup`](#disc-cleanup) | Analyzes local files and recommends files for deletion after validating each stage. Manual run with approval only. |

### What's on disk

```
~/Movies/Rips/
├── ledger.jsonl              # persistent log of every disc processed by the pipeline
├── overrides.json            # which playlist to rip, for discs that hide the movie among decoys
├── watch.log                 # one log for all discs
└── sample-movie-f49b43/      # a ripped disc
    ├── manifest.json         # this disc's state
    ├── plan.json             # proposed names, evidence, and your decisions
    ├── inventory.json        # ffprobe data for each ripped file
    ├── raw/                  # what MakeMKV produced
    ├── frames/               # contact sheets used for identification
    ├── scratch/              # frames an agent generated
    ├── rejected/             # raw files rejected during review, for later deletion
    ├── transcoded/           # finished output, organized for transfer to media library
    └── logs/                 # MakeMKV scan output, failed-rip transcripts, raw agent response
```

### File naming

Media files are named according to [Plex's naming rules](https://support.plex.tv/articles/naming-and-organizing-your-movie-media-files/), which [Jellyfin](https://jellyfin.org/docs/general/server/media/movies) recognizes as well.

- Features: `Title (Year).mkv`
- Editions: `Title (Year) {edition-Name}.mkv`. Jellyfin's docs list `-`, `.`, `_`, or `[ ]` as version separators rather than this tag, so editions may need renaming for a Jellyfin library.
- Folders: `Title (Year)/`, created only when more than one file ships (extras or a second edition). A lone feature ships as a bare file.
- Extras: `Descriptive Name-<type>.mkv` inside the movie folder, where the type is one of `behindthescenes`, `deleted`, `featurette`, `interview`, `scene`, `short`, `trailer`, or `other` ([Plex](https://support.plex.tv/articles/local-files-for-trailers-and-extras/), [Jellyfin](https://jellyfin.org/docs/general/server/media/movies#file-suffix))

## Current Limitations

- **Movies only.** Manifests carry a media type and `disc-ship` would route TV to `TV Shows/`, but nothing identifies episodes yet.
- **Identification requires Claude Code.** `disc-identify` currently calls the `claude` CLI to write `plan.json`, which every later stage reads. A fully manual mode and support for other agents are planned.

## Requirements

Requires macOS, Python 3.9+ (standard library only), and the following tools:

| Tool | Purpose | Used by |
| --- | --- | --- |
| [MakeMKV](https://www.makemkv.com) | Rips discs. | `disc-rip` |
| [FFmpeg](https://ffmpeg.org) | Inspects and decodes video; generates artifacts for identification. | `disc-rip`, `disc-verify`, `disc-identify`, `disc-transcode` |
| [transcode-video.rb](https://github.com/lisamelton/video_transcoding) | Transcodes 1080p and below. | `disc-transcode` |
| [hevc-transcode.rb](https://github.com/lisamelton/more-video-transcoding) | Transcodes 4K. | `disc-transcode` |
| [HandBrakeCLI](https://handbrake.fr) | Encodes video (called by video_transcoding). | `disc-transcode` |
| [Claude Code](https://code.claude.com/docs/en/setup), or LLM of choice | Identifies each file and writes a plan to rename or reject it. | `disc-identify` |
| rsync (included with macOS) | Copies files to the media library and checksums the result. | `disc-ship`, `disc-cleanup` |

MakeMKV must be installed at `/Applications/MakeMKV.app`. Blu-rays need a key; the beta key is free on the [MakeMKV forum](https://forum.makemkv.com/forum/viewtopic.php?t=1053) but expires periodically.

The two transcoder scripts come from separate projects by the same author. `more-video-transcoding` is no longer developed; its author has folded that behavior into `transcode-video.rb`.

## Installation

Clone this repo and add its `bin/` directory to your `PATH`. Adapt to suit your setup:

```
git clone https://github.com/brichards/disc-pipeline.git
echo 'export PATH="$PATH:/path/to/disc-pipeline/bin"' >> ~/.zshrc
```

You can install most missing dependencies via [Homebrew](https://brew.sh):

```
brew install python ffmpeg handbrake
brew install --cask makemkv claude-code
```

The transcoder scripts install by hand rather than as a gem:

```
git clone https://github.com/lisamelton/video_transcoding.git
git clone https://github.com/lisamelton/more-video-transcoding.git
chmod +x video_transcoding/*.rb more-video-transcoding/*.rb
cp video_transcoding/transcode-video.rb more-video-transcoding/hevc-transcode.rb /usr/local/bin/
```

If you installed `video_transcoding` as a gem previously, run `gem uninstall video_transcoding` to remove the older commands it placed on your `PATH`.

Two locations are set by environment variable:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DISC_PIPELINE_ROOT` | `~/Movies/Rips` | Working directory for ripped disc pipeline. |
| `DISC_PIPELINE_NAS` | `/Volumes/Media` | Your media library. Movies ship to `Movies/` inside it. |

Additional preferences can be fine-tuned in `discpipe/config.py`.

## Usage

### Automatic

Install the watcher once. It is a macOS LaunchAgent that runs only when something mounts or unmounts under `/Volumes`.

```
disc-watch --install
```

Insert a disc. The watcher responds and kicks things off, automatically ejecting the disc when finished or if it was already ripped.

Then, start a new session to automatically move all discs through each remaining stage:

```
disc-run --watch
```

The session polls every 30 seconds, starts stages as their resources free up, and exits on its own when nothing is left to do. Failures post a macOS notification.

To check pipeline progress, call `disc-status`:

```
~/Movies/Rips    150.2 GB free

   sample-movie-f49b43   applied    4/10 transcoded
                         -> disc-transcode sample-movie-f49b43
 ! another-movie-a91c4f  identified 20 file(s) proposed
                         -> disc-apply another-movie-a91c4f
```

Discs that need your attention are prefixed with `!`.

You can also monitor the pipeline's progress by tailing the shared log file:

```
tail -f ~/Movies/Rips/watch.log
```

### By hand

Every stage runs on its own. Stages that act on a disc accept a directory or disc slug and default to the current directory:

```
cd ~/Movies/Rips/sample-movie-f49b43
disc-identify
disc-apply
disc-transcode
disc-ship
```

A folder of `.mkv` files ripped some other way works too: point any stage at it and it becomes a tracked disc directory, retaining its original name.

## Commands

Every command accepts `--help`.

### disc-watch

Notices a disc and starts work on it. Installed as a LaunchAgent that runs whenever `/Volumes` changes.

```
disc-watch --install
disc-watch --status
disc-watch              # run one check by hand
```

| Flag | Effect |
| --- | --- |
| `--install` | Write the LaunchAgent to `~/Library/LaunchAgents` and load it. Re-run if your `PATH` or install location move |
| `--uninstall` | Unload and remove the LaunchAgent |
| `--status` | Report whether the LaunchAgent is loaded |
| `--once` | Run the check now, in the foreground |
| `--no-identify` | Rip and verify only, skip the identify step until later |

### disc-run

Checks each disc's manifest and starts its next stage if the stage is ready and the resource it needs is free, then exits without waiting for the stages to finish. With `--watch`, it keeps the Mac awake and repeats the check until nothing has run or been started for the grace period.

```
disc-run
disc-run --watch
disc-run --dry-run
```

| Flag | Effect |
| --- | --- |
| `--watch` | Keep polling until nothing is left to advance |
| `--interval N` | Seconds between passes (default 30) |
| `--grace N` | Seconds idle before a watch session exits (default 120) |
| `--dry-run` | Report what would start; start nothing |

### disc-rip

Scans the disc, rips every title above the configured minimum length, and ejects. Discs already in the ledger are skipped. [Decoy discs](#decoy-discs) are held for review.

```
disc-rip
disc-rip --dry-run
disc-rip --redo
```

| Flag | Effect |
| --- | --- |
| `--disc N` | MakeMKV drive index, for machines with more than one drive (default 0) |
| `--force` | Rip a disc that is already in the ledger |
| `--dry-run` | Scan and triage; rip nothing |
| `--redo` | Re-rip titles already marked done |
| `--no-eject` | Leave the disc in the drive after a clean rip |
| `--wait` | Wait for the drive lock instead of exiting when another rip is running |

Notes:

- Ripping continues through every title even if one fails.
- Running `disc-rip` again retries only the failed titles; `--redo` re-rips every title.
- A rip with read errors stays in the drive until `disc-verify` has checked it.

#### Decoy discs

Some discs list dozens of near-identical feature-length playlists, only one of which plays correctly. `disc-rip` detects this and holds the disc for review. To resolve, manually add the correct playlist ID to `overrides.json` then call `disc-rip` again.

Example `overrides.json`, each entry is keyed by the fingerprint in the disc's `manifest.json`:

```json
{
  "<disc-fingerprint>": { "playlist": "00800.mpls", "note": "confirmed by watching" }
}
```

### disc-verify

Runs a decode step on titles that logged rip errors to verify file integrity. Exits immediately when there is nothing to check.

```
disc-verify
disc-verify --all
```

| Flag | Effect |
| --- | --- |
| `--all` | Check every title, not only those with read errors |
| `--force` | Re-check titles already verified |
| `--wait` | Wait for the CPU lock instead of stepping aside |
| `--no-eject` | Leave the disc in the drive after it verifies |

A file that will not decode holds the disc for review and ejects it. Clean the disc, reinsert it, and run `disc-rip --redo`.

### disc-identify

Generates still frames and metadata for each title, then calls an LLM to generate `plan.json` with a proposed [filename](#file-naming) (or rejection) and confidence score for each title.

```
disc-identify
disc-identify --frames-only
disc-identify --from-log
```

| Flag | Effect |
| --- | --- |
| `--refresh-frames` | Rebuild contact sheets even if they exist |
| `--frames-only` | Build the inventory and contact sheets, then stop (no LLM needed) |
| `--from-log` | Rebuild `plan.json` from the last saved agent run, without calling the LLM again |
| `--timeout N` | Seconds before the agent run is abandoned (default 1800) |
| `--model NAME` | Model name to pass to the agent (default: the agent's own default) |

Notes:

- Two contact sheets are built per title: 25 frames from the first 75 seconds, and 16 frames spread across the runtime.
- An `ffprobe` inventory records each title's duration, dimensions, and audio and subtitle streams.
- These artifacts go to a headless LLM session that looks up the disc release, matches each title against it, and writes `plan.json` and `logs/identify.json`.
- For each title, the plan proposes an action (`feature`, `extra`, `reject`, or `unknown`), a name, a confidence level, and supporting evidence.
- `--from-log` rebuilds the plan from `logs/identify.json` without calling the LLM again.

### disc-apply

Applies the `plan.json` written by `disc-identify`, renaming kept titles and setting rejected ones aside. When run by `disc-run`, it proceeds automatically only if every title came back high confidence; otherwise it holds the disc for interactive review.

```
disc-apply
disc-apply --dry-run
disc-apply --revert
```

| Flag | Effect |
| --- | --- |
| `--yes` | Accept every proposal without review |
| `--auto` | Apply only if every item is high confidence and none is `unknown`; otherwise leave the disc for review |
| `--reset` | Put the files back, clear your decisions, and review again |
| `--revert` | Put the files back under their original names |
| `--dry-run` | Show what would happen; change nothing |

Notes:

- The interactive review walks through each item with its evidence.
- Decisions are saved as you go, and you confirm the full list of changes before anything moves.
- Rejected files are moved to `rejected/`, not deleted.
- `--revert` restores every file to its original name and location.

### disc-transcode

Encodes the remaining titles using the video_transcoding tools (`transcode-video.rb` for 1080p and below, `hevc-transcode.rb` for 4K), writing the final versions to `transcoded/` in the [expected layout](#file-naming). Retains all subtitle tracks.

```
disc-transcode
disc-transcode --dry-run
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show the commands; transcode nothing |
| `--force` | Redo files already marked done |
| `--wait` | Wait for the CPU lock instead of stepping aside |
| `--quiet` | Hide the transcoder's progress output |

Running again will only transcode incomplete files. Using `--force` will also transcode files marked done.

### disc-ship

Uses rsync to copy the contents of `transcoded/` to your media library then verify successful delivery with checksum comparison. Will not run if transcode is in progress or if library volume is unmounted.

```
disc-ship
disc-ship --dry-run
```

| Flag | Effect |
| --- | --- |
| `--dry-run` | Show what would be copied; copy nothing |
| `--force` | Overwrite files at the destination, and ship even if transcoding is unfinished |
| `--wait` | Wait for the network lock instead of stepping aside |
| `--quiet` | Hide rsync progress |

Notes:

- Files that already exist in the media library will not be overwritten. The disc is held for review instead.
- Using `--force` will overwrite existing files.
- When transferring a movie folder, if the media library already contains a single file copy of the movie, it will be relocated to the movie folder unless that would cause a collision.

### disc-status

Lists the current stage, progress, and next command or hold reason for every disc in the pipeline. Also reports remaining free space in pipeline root.

```
disc-status
disc-status --json
```

| Flag | Effect |
| --- | --- |
| `--json` | Formats output as JSON |

### disc-cleanup

An interactive review of the pipeline root that recommends files for deletion after verifying all completed stages. This is the only command that deletes anything and it requires confirmation before completing the destructive action.

```
disc-cleanup
disc-cleanup --dry-run
disc-cleanup sample-movie-f49b43
```

| Flag | Effect |
| --- | --- |
| `--verify-only` | Re-verify the media library copies; delete nothing |
| `--dry-run` | Show what would be deleted; delete nothing |

Notes:

- Each shipped disc is reviewed in three steps: the transcoded output, then the source rip, then the disc folder itself.
- 4K source rips are never offered for deletion.
- Can only delete files that (1) exist within the pipeline root and (2) were created by a pipeline script.

## Design notes

**`disc-cleanup` is the only script that can delete files.** It must be called manually, can only delete pipeline root files created by pipeline scripts, and requires a separate approval per disc stage.

**A clean exit is not always a clean rip.** MakeMKV works around bad sectors and returns 0, so `disc-rip` scans output for read errors and flags suspicious rips; `disc-verify` decodes any suspicious rips to validate success.

**Titles are verified by runtime, not index.** MakeMKV title numbers shift with the minimum-length setting, so every MakeMKV call uses the same value. Each ripped file is compared against the runtime reported by the scan and flagged as failed on a mismatch.

## License

MIT. See [LICENSE](LICENSE).
