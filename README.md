# medialnk

Scans your `/movies/` and `/tv/` folders, figures out what's what, and builds a parallel symlink tree organized the way media servers expect.

This separates your library into an immutable "source" layer and a clean "presentation" layer. Movies, TV shows, and miniseries are automatically separated and correctly restructured regardless of how disorganized the source folder is. The original (seeding) files stay exactly where they are.

Can be used as a one-time library importer, ongoing media library manager, or as a companion tool to the arr stack. Or all three at the same time.

```text
What you have (Messy Source):         What medialnk builds (Clean Symlinks):
/movies/                              /movies-linked/
  Some.Movie.2020.1080p.BluRay/         Some Movie (2020)/
  The.Matrix.1999.2160p.REMUX/            Some Movie (2020).mkv -> original
  Mini.Series.S01E01.1080p/             The Matrix (1999)/
  Kill.Bill.Part.1.1080p/                 The Matrix (1999) - 2160P.mkv -> original
                                      /tv-linked/
/tv/                                    Breaking Bad/
  Breaking.Bad.S01.1080p.BluRay/          Season 01/ -> original folder
  Breaking.Bad.S02.720p.WEB-DL/           Season 02/ -> original folder
  Breaking.Bad.S01E04.720p.mkv          Mini Series/
  Fallout.S01E05-E06.1080p.mkv            Season 01/
                                            episode.mkv -> original
```

Run medialnk, point Jellyfin at the `-linked/` directories, done.

---

## Why this is different

The standard recommendation for managing a media library is hardlinks into a structured folder. That breaks on mergerfs. When source and destination land on different physical drives under the union mount, `os.link()` returns `EXDEV: cross-device link not permitted`. Symlinks follow the unified mount path regardless of physical drive layout and always work.

Beyond that, every other tool hits at least one wall:

- **Arr stack (Radarr/Sonarr):** Great for new downloads. Importing an existing disorganized library is genuinely painful because Radarr needs a structured library to start with. It can't import what it can't parse. If you have years of scene-named torrents sitting in a flat folder, you're stuck before you begin.
- **FileBot:** Renames the actual files. Breaks seeding immediately. `--action symlink` exists but still requires you to manually pre-sort movies from TV before it can match anything.
- **rclone union and similar:** Merges paths, can't rename or restructure anything. Same mess, different mount point.
- **Manual sorting:** Sure. Spend a weekend on it, miss some, do it again next month.

medialnk's approach is to not touch your source files at all. It reads filenames, builds a clean tree of symlinks somewhere else, and that's it. Your torrent client keeps seeding from unchanged paths. Your media server gets a properly organized library. The two layers are completely independent.

---

## How it works with Radarr and Sonarr

medialnk and the arr stack are not competitors. They solve adjacent problems and work well together.

**Radarr/Sonarr handle:** Searching indexers, automating downloads, tracking quality upgrades, managing the lifecycle of content they know about. For anything Radarr manages end-to-end, Radarr is the right tool.

**medialnk handles:** Everything outside that. Manually grabbed torrents, niche releases, specific encodes, your existing library that Radarr has never seen. Content that arrived before you set up the arr stack. Anything you want to grab yourself without Radarr being involved.

In practice the clean split is:

```
/media/torrents/          <- qBittorrent downloads here (seeding source, never touched)
/media/movies-linked/     <- medialnk output (manually acquired content)
/media/tv-linked/         <- medialnk output (manually acquired TV)
/media/radarr-movies/     <- Radarr root (Radarr-managed content only)
/media/sonarr-tv/         <- Sonarr root (Sonarr-managed content only)
```

Jellyfin points at both `movies-linked/` and `radarr-movies/` as a combined library. Radarr and medialnk are drawing from the same source folder but outputting to separate places. No collisions, no duplicate files appearing in Jellyfin.

### Getting Radarr started on an existing library

This is where medialnk actually helps the arr stack directly. If you have a large existing library, Radarr's manual import tool works against the `-linked/` directories. Because medialnk has already parsed and organized everything into proper `Movie Name (Year)/` folders, Radarr can match and import the whole library in one pass. After that initial import, turn Radarr's rename setting back on and let it manage new downloads from there.

Without medialnk, this initial import step is the part that takes a weekend.

### Automated processing on download completion

The cleanest setup for an ongoing workflow is triggering medialnk automatically when a torrent completes. In qBittorrent, under "Run external program on torrent completion":

```
medialnk sync --yes
```

Radarr already notifies Jellyfin when it imports. medialnk running on torrent completion means manually grabbed content shows up in Jellyfin just as automatically. Both pipelines keep Jellyfin updated without any manual steps.

---

## Main Features

- **Smart Movie Parsing:** Extracts titles and years from scene names, groups multiple quality versions (1080p and 2160p) into the same canonical folder.
- **TV and Bare Episode Handling:** Groups season folders and matches loose bare episode files (`S01E05`, `3x05`, `Episode.4`, etc.) into their correct season directories. Conflicts are resolved automatically where possible, and anything ambiguous prompts for confirmation.
- **Miniseries Detection:** Automatically detects folders in `/movies/` that contain episode files and routes them to the TV library instead.
- **Duplicate Handling:** When two source folders provide the same TV season at different qualities, you're prompted to choose. Or you can keep both.
- **TMDB Resolution:** Free TMDB API key resolves messy names to canonical forms. Falls back safely when confidence is low rather than making a wrong guess.
- **Source File Immutability:** medialnk functionally cannot alter, delete, move, rename, or otherwise change source media files. This is enforced at the compiler level, not just by convention. Misconfiguration cannot cause it either.
- **Pass-through for already-structured content:** Properly structured folders are passed through without modification. Running medialnk against a library that Radarr or Sonarr already manages won't break anything.

---

## What this is for

### One-time library cleanup

Run medialnk once to turn a disorganized media collection into a clean linked library for Jellyfin or Plex. Works well as a single-use organizer. Original purpose.

### Ongoing linked-library maintenance

Run medialnk repeatedly as your source library changes. Useful if you download media manually and don't want to depend on Sonarr or Radarr for everything (or anything). Quickly re-organizes as you add content. Can run as an automated service scanning for changes.

### Bootstrapping Radarr/Sonarr

Run medialnk once to produce clean structured directories, use those as the source for Radarr/Sonarr's manual import with rename turned off, then hand the ongoing management to arr. Gets you from chaos to a working arr-managed library without manually sorting thousands of files.

### Companion tool for arr stack

Manages the manually acquired content that falls outside Radarr's awareness, while Radarr handles automated downloads. Both pipelines feed Jellyfin from separate output directories. Full arr compatibility is maintained throughout.

### Safe presentation layer where hardlinks break

For mergerfs, separate media drives, pooled storage, or any setup where `os.link()` returns `EXDEV`. Symlinks work regardless of drive, filesystem, or source location.

---

## Quick Start

### Download a release binary

```bash
# Download the latest release for your platform from the releases page
# Place it somewhere in your PATH, e.g.:
mv medialnk /usr/local/bin/medialnk
chmod +x /usr/local/bin/medialnk
```

### Build from source

```bash
git clone https://github.com/AnAngryGoose/medialnk
cd medialnk
go build -o medialnk .
```

### Configure and run

```bash
cp medialnk.toml ~/.config/medialnk/medialnk.toml
# Edit paths to match your setup

medialnk sync --dry-run
medialnk sync
```

Point Jellyfin at `movies-linked/` and `tv-linked/`.

---

## Commands

```bash
medialnk sync                  # Full scan + link (movies then TV)
medialnk sync --dry-run        # Preview only
medialnk sync --yes            # Auto-accept all prompts
medialnk sync --tv-only        # Skip movies
medialnk sync --movies-only    # Skip TV
medialnk sync -v               # Verbose output
medialnk sync -vv              # Debug output
medialnk sync -q               # Quiet (errors/warnings only)

medialnk clean                 # Remove broken symlinks
medialnk clean --dry-run       # Preview what would be removed

medialnk validate              # Check config, paths, PathGuard

medialnk test-library /path    # Generate fake library for testing
medialnk test-library /path --reset
```

Global flags:
```bash
medialnk --config /path/to/medialnk.toml sync --dry-run
medialnk --version
```

---

## Configuration

Config file is searched in order:
1. `--config /path/to/medialnk.toml` (CLI flag)
2. `./medialnk.toml` (current directory)
3. `~/.config/medialnk/medialnk.toml`

```toml
[paths]
media_root_host = "/mnt/storage/data/media"
media_root_container = "/data/media"    # same as host if not using Docker
movies_source = "movies"                # relative to media_root_host
tv_source = "tv"
movies_linked = "movies-linked"
tv_linked = "tv-linked"

[tmdb]
api_key = ""                            # or TMDB_API_KEY env var
confidence_check = true

[logging]
log_dir = "logs"
verbosity = "normal"                    # quiet/normal/verbose/debug

[overrides.tv_names]
"The Office US" = "The Office (US)"

[overrides.tv_orphans]
"Season 1" = { show = "Little Bear", season = 1 }
```

Config file controls how the installation normally behaves (paths, API keys, overrides). CLI flags control how a particular run behaves (`--dry-run`, `--yes`, `-v`). CLI flags override config where they overlap.

---

## How it works

### Movies pipeline

Scans `/movies/`, extracts title and year from folder and file names, groups multi-version entries with quality suffixes, creates symlinks in `/movies-linked/`.

- Skips miniseries folders (2+ episode files) and routes them to TV
- Flags Part.N folders as ambiguous and prompts for movie vs TV routing
- TMDB auto-lookup for entries missing a year
- Multi-version output: `Movie (Year) - 1080P.mkv`, `Movie (Year) - 2160P.mkv`

### TV pipeline (two passes)

**Pass 1:** Scans `/tv/` for season folders, groups by show name, creates season symlinks. Scans `/movies/` for miniseries. Passes through already-structured folders. Prompts on duplicate seasons at different qualities.

**Pass 2:** Handles bare episode files in `/tv/` with no parent folder. Parses show name, resolves via overrides/TMDB/fallback, matches against Pass 1 results. Handles conflicts interactively.

### Episode format support

| Format | Example | Status |
|--------|---------|--------|
| SxxExx | `Show.S01E05.mkv` | Supported |
| Multi-ep | `Show.S01E05-E06.mkv` | Supported (combined name) |
| NxNN | `Futurama.3x05.mkv` | Supported |
| Episode.N | `Documentary.Episode.4.mkv` | Supported |
| NofN | `Planet.Earth.1of6.mkv` | Folder scan only |
| Bare E01 | `pe.E01.mkv` | Folder detection only |
| Part.N | `Kill.Bill.Part.1.mkv` | Ambiguity prompt (not auto-routed) |

### TMDB confidence checking

Results are validated before acceptance. Short parsed names (1-2 words) require all words present in the TMDB result with at most 1 extra word. Longer names require 50%+ word overlap. Rejected matches fall back to the parsed name.

### Source protection

Two independent layers prevent source files from being modified:

1. **Compiler-enforced path guard:** All filesystem write functions accept only `SafePath`, never raw string paths. `SafePath` can only be constructed by `NewSafePath()`, which validates the path is under a registered output root. A raw string path cannot reach a write function — this is a compile error, not a runtime crash. Misconfiguration cannot bypass it.
2. **Output validation on startup:** Output directories are scanned for real video files on every run. If found, you're warned and prompted before anything proceeds.

Source files are never read for content, only filenames and sizes.

---

## Manual Overrides

### TV name overrides

```toml
[overrides.tv_names]
"The Office US" = "The Office (US)"
"Mystery Science Theater" = "Mystery Science Theater 3000"
```

### TV orphan overrides

For bare `Season N` folders with no show name context:

```toml
[overrides.tv_orphans]
"Season 1" = { show = "Little Bear", season = 1 }
"dvdrip_full_season" = { show = "Good Eats", season = 4 }
```

Run `medialnk sync --dry-run -v` to identify what needs overrides.

---

## Recommended workflow

```bash
# Preview first
medialnk sync --dry-run -v > dry-run.txt

# Review, add overrides to medialnk.toml, repeat until clean

# Run for real
medialnk sync

# Point Jellyfin/Plex at movies-linked/ and tv-linked/

# For arr import: manual import against linked dirs with rename OFF
# Re-enable rename after initial import completes
```

### Automated/scheduled runs

```bash
medialnk sync --yes -q    # auto-accept, quiet output
```

Per-run logs are written to the configured `log_dir` regardless of console verbosity.

---

## Testing

```bash
# Generate a test library
medialnk test-library /tmp/test-lib

# Dry run against it
medialnk --config /tmp/test-lib/medialnk.toml sync --dry-run -v

# Live run
medialnk --config /tmp/test-lib/medialnk.toml sync --yes -v

# Validate
medialnk --config /tmp/test-lib/medialnk.toml validate
```

The test library covers all parsing scenarios: multi-version movies, miniseries, Part.N ambiguity, duplicate seasons, bare episode files in every supported format, apostrophe variations, trailing years, pass-through folders, orphan overrides, and all recognized video extensions.

---

## File structure

```
medialnk/
  cmd/
    root.go          # cobra root, global flags, version
    sync.go          # sync subcommand
    clean.go         # clean subcommand
    validate.go      # validate subcommand
    watch.go         # watch subcommand (stub)
    testlib.go       # test-library subcommand
  internal/
    config/
      config.go      # TOML loading, validation, path resolution
    common/
      pathguard.go   # SafePath type, NewSafePath, write functions
      symlink.go     # symlink helpers
      video.go       # video extension list, file detection
    movies/
      movies.go      # movie scanning + linking
      parse.go       # scene name parsing
    tv/
      tv.go          # TV scanning + linking
      parse.go       # show name extraction
      episodes.go    # episode format regexes
    resolver/
      tmdb.go        # TMDB lookups via stdlib net/http
      confidence.go  # word overlap, confidence checking
    testlib/
      generate.go    # fake library generator
  main.go
  medialnk.toml      # default config template
```
