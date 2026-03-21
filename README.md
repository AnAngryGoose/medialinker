# medialnk

Scans your `/movies/` and `/tv/` source folders, parses scene-named files and folders, and builds a clean symlink tree organized the way Jellyfin and Plex expect. Your original files are never touched.

```
Source (messy, seeding):              Presentation layer (clean symlinks):

/movies/                              /movies-linked/
  Some.Movie.2020.1080p.BluRay/         Some Movie (2020)/
  The.Matrix.1999.2160p.REMUX/            Some Movie (2020).mkv -> source
  Mini.Series.S01E01.1080p/             The Matrix (1999)/
                                           The Matrix (1999) - 2160P.mkv -> source
/tv/                                  /tv-linked/
  Breaking.Bad.S01.1080p.BluRay/        Breaking Bad/
  Breaking.Bad.S02.720p.WEB-DL/           Season 01/ -> source folder
  Breaking.Bad.S01E04.720p.mkv             Season 02/ -> source folder
  Futurama.3x05.720p.mkv               Mini Series/
                                          Season 01/
                                            Mini.Series.S01E01 - 1080P.mkv -> source
```

Point Jellyfin at `movies-linked/` and `tv-linked/`. Done.

---

## Why

**Symlinks over hardlinks.** Hardlinks break on mergerfs when source and destination land on different physical drives (`EXDEV: cross-device link not permitted`). Symlinks follow the union mount path and always work.

**Source files are immutable.** Torrents keep seeding from unchanged paths. The presentation layer is entirely disposable. Delete it and rebuild in seconds. This is enforced at the compiler level via `SafePath` — write functions cannot accept raw string paths, so source directories are unreachable by construction, not by convention.

**Fills the arr gap.** Radarr and Sonarr manage content they downloaded. They cannot import a years-old disorganized library without something else first organizing it. medialnk handles everything outside arr's awareness: manually grabbed torrents, legacy libraries, specific encodes. Radarr manages its own downloads into its own output directory. medialnk manages everything else into a separate output directory. Jellyfin points at both. No collisions.

---

## Install

**Download a release binary:**
```bash
mv medialnk /usr/local/bin/medialnk
chmod +x /usr/local/bin/medialnk
```

**Build from source:**
```bash
git clone https://github.com/AnAngryGoose/medialnk
cd medialnk
go build -o medialnk .
```

---

## Quick Start

```bash
cp medialnk.toml ~/.config/medialnk/medialnk.toml
# Edit paths to match your setup

medialnk sync --dry-run -v    # preview first
medialnk sync                  # run for real
```

Recommended workflow: dry run, review the output, add any needed overrides to config, repeat until clean, then run live.

---

## Commands

```bash
medialnk sync                  # Full scan and link
medialnk sync --dry-run        # Preview only, nothing written
medialnk sync --yes            # Auto-accept all prompts
medialnk sync --tv-only        # Skip movies pipeline
medialnk sync --movies-only    # Skip TV pipeline
medialnk sync -v / -vv         # Verbose / debug output
medialnk sync -q               # Quiet (errors and warnings only)

medialnk clean                 # Remove broken symlinks from output dirs
medialnk clean --dry-run

medialnk validate              # Check config, paths, and PathGuard

medialnk test-library /path    # Generate a fake library for testing
medialnk test-library /path --reset

medialnk --config /path/to/medialnk.toml sync --dry-run
medialnk --version
```

---

## Configuration

Config is searched in order: `--config` flag, `./medialnk.toml`, `~/.config/medialnk/medialnk.toml`.

```toml
[paths]
media_root_host = "/mnt/storage/data/media"
media_root_container = "/data/media"    # same as host if not using Docker
movies_source = "movies"
tv_source = "tv"
movies_linked = "movies-linked"
tv_linked = "tv-linked"

[tmdb]
api_key = ""                            # optional, or set TMDB_API_KEY env var
confidence_check = true

[logging]
log_dir = "logs"
verbosity = "normal"                    # quiet / normal / verbose / debug

[overrides.movie_titles]
"Some Parsed Title" = "Correct Title"

[overrides.tv_names]
"The Office US" = "The Office (US)"

[overrides.tv_orphans]
"Season 1" = { show = "Little Bear", season = 1 }
```

---

## What it handles

**Movies:** Parses scene names for title and year, groups multi-quality versions under one canonical folder, detects miniseries misplaced in `/movies/` and routes them to TV. Yearless entries are resolved via TMDB. Part.N folders are flagged as ambiguous and prompted.

**TV:** Two-pass pipeline. Pass 1 handles season folders and multi-season packs. Pass 2 handles bare episode files scattered in the source directory. Both passes resolve show names via TMDB with configurable overrides. Duplicate seasons at different qualities prompt for a choice.

**Episode formats supported:** `S01E05`, `S01E05-E06` (multi-ep), `3x05`, `Episode.4`, folder-level `1of6` and `E01` detection.

**State tracking:** After each real sync, a `.medialnk-state.json` file is written to each output directory recording everything linked, skipped, flagged, and unmatched that run. Dry runs do not write state. This is the foundation for future status reporting, orphan detection, and diff/rollback.

**Source protection:** `SafePath` is a Go type whose constructor validates that a path is under a registered output root. All write functions accept only `SafePath`. Raw string paths cannot reach write functions. This is a compile-time constraint, not a runtime check. Misconfiguration cannot bypass it.

---

## Overrides

For show names that parse wrong:
```toml
[overrides.tv_names]
"Mystery Science Theater" = "Mystery Science Theater 3000"
```

For bare `Season N` orphan folders with no parseable show name:
```toml
[overrides.tv_orphans]
"Season 1" = { show = "Little Bear", season = 1 }
```

Run `medialnk sync --dry-run -v` to identify what needs overrides.

---

## Automated runs

```bash
# qBittorrent completion hook:
medialnk sync --yes -q

# Per-run logs are always written to log_dir regardless of console verbosity
```

---

## Testing

```bash
medialnk test-library /tmp/test-lib
medialnk --config /tmp/test-lib/medialnk.toml sync --dry-run -v
medialnk --config /tmp/test-lib/medialnk.toml sync --yes -v
medialnk --config /tmp/test-lib/medialnk.toml sync --dry-run -v    # idempotency check
```

The test library covers multi-version movies, miniseries, Part.N ambiguity, duplicate seasons, bare episode files in all supported formats, pass-through folders, and orphan overrides.

---

## More detail

Architecture, pipeline internals, function reference, and the full planned roadmap are in `OVERVIEW.md`.