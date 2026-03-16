# medialnk Project Overview

**Version:** 0.25
**Repository:** https://github.com/AnAngryGoose/medialnk
**Language:** Python 3.6+ (stdlib only, no external dependencies)


## What This Project Is

medialnk builds a clean, Jellyfin/arr-stack-compatible symlink library from a messy, unstructured media library. It reads source directories containing raw torrent downloads and creates a parallel directory tree of symlinks organized the way Jellyfin, Radarr, and Sonarr expect. The source files are never touched. Torrent seeding keeps working from the original paths.

The output directories contain only symlinks. The source directories are protected by a runtime enforcement system (PathGuard) that makes it technically impossible for the scripts to write to them, even if a code bug or config mistake points at the wrong place.


## Why This Exists (vs. Other Tools)

Every existing tool for organizing a media library hits at least one of these walls:

**Arr stack (Radarr, Sonarr)** can rename and organize files, but it needs an already-structured library to get started. If your library is a flat pile of scene-named torrents, Radarr can't even import them. Chicken and egg.

**FileBot / TinyMediaManager** rename actual files. That breaks torrent seeding because the torrent client expects the original filenames and paths. FileBot can do symlinks via `--action symlink`, but you still need to manually sort movies vs TV across thousands of files first.

**rclone union** and similar tools merge filesystem paths but can't rename, categorize, or restructure anything.

**Hardlink approaches** (the standard recommendation from TRaSH Guides) fail on mergerfs pools because source and destination can land on different underlying physical drives, causing `os.link()` to fail with `EXDEV` (cross-device link error). Symlinks follow a path through the unified mount and don't have this problem.

medialnk solves all of these:

- Reads raw scene-named folders/files and builds the right structure automatically
- Automatically detects whether content is a movie, TV show, or miniseries
- Creates symlinks, not hardlinks, so seeding and mergerfs both work
- No manual sorting needed before running
- Ambiguous cases (like multi-part films) get flagged for user confirmation
- Nothing is ever modified without the user confirming it first


## Architecture

### File Layout

```
common.py              Shared code: regex, PathGuard, filesystem helpers
make_movies_links.py   Movies script: /movies/ -> /movies-linked/
make_tv_links.py       TV script: /tv/ + /movies/ -> /tv-linked/
test_path_guard.py     41 tests for the immutability system
create_test_library.py Generates a fake library for testing
```

### Data Flow

```
Source (read-only)                Output (write-only)
/movies/  ----+                   /movies-linked/
              |-- make_movies_links.py -->  Movie Name (Year)/
              |                               Movie Name (Year).mkv -> source
              |
              +-- make_tv_links.py ----+
/tv/  --------+                        +--> /tv-linked/
                                              Show Name/
                                                Season 01/ -> source folder
                                              Miniseries/
                                                Season 01/
                                                  episode.mkv -> source
```

The movies script reads from `/movies/` only. The TV script reads from both `/tv/` and `/movies/` (to find miniseries that landed in the movies folder). Both scripts write exclusively to their respective `-linked/` directories.

### Execution Order

The movies script should run before the TV script. The TV script's `scan_movies_for_miniseries()` reads `/movies/` to find folders with episode files. If you run the TV script first, it still works, but running movies first ensures consistent routing of ambiguous content.

### Two-Pass Processing (TV Script)

The TV script processes content in two passes:

**Pass 1** handles folder-based sources. It scans `/tv/` for season folders (e.g. `Show.Name.S01.1080p.BluRay/`), groups them by show name, and creates season symlinks. It also scans `/movies/` for miniseries (folders with 2+ episode files). Folders already in Jellyfin structure are passed through. This pass produces the `grouped` dict that maps show names to their season folders.

**Pass 2** handles bare episode files sitting directly in `/tv/` with no parent folder. For each file, it parses the show name and episode info, resolves the show name via overrides/TMDB/fallback, matches against Pass 1 results, and determines whether the episode is new, a duplicate, a quality variant, or missing from an existing season. Conflicts are handled interactively.


## Immutability System

### Design

The project's core rule is that source media files are never modified, moved, or deleted. This is enforced at two levels:

**Level 1: PathGuard (runtime enforcement).** Every filesystem write operation in the entire codebase flows through one of four guarded functions: `safe_remove()`, `safe_rmdir()`, `safe_makedirs()`, `safe_symlink()`. Each function calls `PathGuard.assert_writable()` before touching disk. The guard knows which paths are source (protected) and which are output (writable). Any write targeting a source path raises `SourceProtectionError` and crashes the script immediately. Any write outside all registered paths also raises, preventing accidental writes to random filesystem locations.

**Level 2: validate_output_dir (config mistake detection).** On every startup, before any writes happen, the output directory is scanned for real (non-symlink) video files. If any are found, the user is warned and prompted to confirm. This catches the case where someone configures their real media library as the output directory. The PathGuard can't detect this because the user told it the path is an output, but the content scan reveals that real media files are already there.

### Startup Sequence

```
1. init_path_guard(sources=[...], outputs=[...])
   - Creates PathGuard, registers all paths, locks it
   - Rejects if output is inside source, or output == source

2. validate_output_dir(output_dir, dry_run)
   - Walks output dir looking for real video files
   - Warns + prompts if found (blocks on 'n', default N)
   - Dry-run warns but doesn't block

3. Normal script execution begins
   - All writes go through safe_* functions
   - Guard validates every single write against registered paths
```


## Function Reference: common.py

### Regex Patterns

| Pattern | What it matches | Example |
|---------|----------------|---------|
| `RE_SXXEXX` | S01E01 format | `Breaking.Bad.S01E01.1080p.mkv` |
| `RE_XNOTATION` | 1x01 format | `Futurama.3x05.720p.mkv` |
| `RE_EPISODE` | Episode.N format | `Some.Documentary.Episode.4.mkv` |
| `RE_NOF` | NofN format | `Planet.Earth.1of6.mkv` |
| `RE_BARE_EPISODE` | Bare E01 | `pe.E01.1080p.mkv` |
| `RE_MULTI_EP` | Multi-ep continuation | `-E06` in `S01E05-E06` |
| `RE_SAMPLE` | Sample files | `sample.mkv` |
| `RE_PART` | Part.N / Pt.N | `Kill.Bill.Part.1.mkv` |
| `RE_QUALITY` | Quality tags | `1080p`, `REMUX`, `BluRay` |
| `RE_ILLEGAL_CHARS` | Illegal filename chars | `:`, `?`, `*`, etc. |

### PathGuard System

| Function | Purpose |
|----------|---------|
| `SourceProtectionError` | Exception raised when a write targets a protected path. Crashes immediately. |
| `PathGuard` | Class. Holds source/output path lists. After `lock()`, validates every write. |
| `init_path_guard(sources, outputs)` | Creates module-level guard, registers paths, locks. Called once per script. |
| `get_path_guard()` | Returns module-level guard for inspection/testing. |
| `validate_output_dir(directory, dry_run)` | Scans output dir for real video files. Catches config mistakes. |

### Guarded Write Functions

| Function | What it does |
|----------|-------------|
| `safe_remove(path)` | `assert_writable()` then `os.remove()`. Only file removal function. |
| `safe_rmdir(path)` | `assert_writable()` then `os.rmdir()`. Only dir removal function. |
| `safe_makedirs(path)` | `assert_writable()` then `os.makedirs()`. Only dir creation function. |
| `safe_symlink(target, link_path)` | Guards `link_path` only. `target` can point at source (that's the point). |

### Detection Functions

| Function | Purpose | Notes |
|----------|---------|-------|
| `is_video(filename)` | True if extension is in VIDEO_EXTS | .mkv, .mp4, .avi, .ts, .m4v |
| `is_sample(filename)` | True if "sample" appears as word boundary | Prevents false positive on "example.mkv" |
| `is_episode(filename)` | True if any episode pattern matches | Includes Part.N as last resort |
| `is_episode_strict(filename)` | Same but excludes Part.N | For miniseries scanning (avoids Kill Bill false positive) |
| `extract_quality(name)` | Returns first quality tag, uppercased | "1080P", "REMUX", etc. or None |

### Utility Functions

| Function | Purpose |
|----------|---------|
| `sanitize_filename(name)` | Replaces Windows-illegal chars with `-` |
| `clean_passthrough_name(folder_name)` | Safe cosmetic cleanup only: dots to spaces, whitespace normalization. Does NOT strip years, metadata, or canonicalize. |
| `host_to_container(path, host_root, container_root)` | Translates host path to Docker container path for symlink targets |
| `make_symlink(link_path, target, dry_run, host_root, container_root)` | Creates absolute container-side symlink. Skips if exists. |
| `ensure_dir(path, dry_run)` | Creates directory + parents. No-op in dry-run. |
| `_symlink_target_exists(link_path, host_root, container_root)` | Checks symlink target existence with container-to-host translation |
| `clean_broken_symlinks(directory, host_root, container_root)` | Removes broken symlinks + prunes empty dirs in output |
| `find_videos_in_folder(folder_path, exclude_episodes, exclude_samples)` | Lists video files in a folder with optional filtering |
| `largest_video(videos)` | Returns largest file by st_size from DirEntry list |


## Function Reference: make_tv_links.py

### Episode Parsing

| Function | Purpose |
|----------|---------|
| `episode_info(filename)` | Returns (season, episode) from any pattern including Part.N |
| `episode_info_strict(filename)` | Same but excludes Part.N. For miniseries scanning. |
| `parse_bare_episode(filename)` | Returns 5-tuple: (show, season, episode, quality, second_ep). Handles SxxExx+multi-ep, NxNN, Episode.N. Returns None for unparseable. |
| `build_episode_link_name(show, season, episode, quality, ext, second_ep)` | Builds standardized symlink filename. Handles multi-ep naming (S01E05-E06). |

### Name Resolution

| Function | Purpose |
|----------|---------|
| `normalize_show_key(name)` | Light normalization for Pass 1 grouping (case, apostrophes) |
| `normalize_for_match(name)` | Aggressive normalization for cross-source matching (articles, studios, years, punctuation) |
| `extract_show_and_season(folder_name)` | Parses "Show.Name.S01.720p..." into ("Show Name", 1) |
| `clean_show_name(folder_name)` | Strips quality/codec tokens for display name |
| `tmdb_search_tv(parsed_name)` | TMDB lookup with caching and confidence check |
| `_tmdb_word_overlap(parsed, tmdb)` | Word-set comparison. Short names: all words + length check. Long names: 50% overlap. |
| `resolve_show_name(parsed_name)` | Chain: NAME_OVERRIDES -> TMDB -> parsed fallback |
| `find_matching_show(show_name, grouped)` | Fuzzy match against Pass 1 results + disk scan |

### Season/Episode State

| Function | Purpose |
|----------|---------|
| `episode_exists_in_folder(path, ep, season)` | Checks if episode exists in source folder. Returns (exists, quality). |
| `_find_episode_symlink(season_dir, ep, season)` | Checks for existing episode symlink in converted season dir. For idempotency. |
| `is_bare_episode_folder(folder_path)` | True if 2+ bare E\d+ entries. Detects non-standard episode folders. |
| `convert_season_symlink_to_real_dir(show, season, path, dry_run)` | Replaces season symlink with real dir. Re-links episodes with quality inheritance from folder name. |
| `resolve_duplicate_seasons(show, seasons, dry_run)` | Prompts user to choose quality when duplicate season folders exist. |

### Scanners and Handlers

| Function | Purpose |
|----------|---------|
| `scan_tv_source()` | Pass 1: groups season folders, identifies pass-through and bare episode folders |
| `scan_movies_for_miniseries()` | Scans /movies/ for 2+ episode folders (excludes Part.N) |
| `scan_tv_bare_files(grouped)` | Pass 2: categorizes bare files as new/conflict/unmatched |
| `handle_bare_new(bare_new, dry_run)` | Creates show/season dirs and symlinks for new content |
| `handle_bare_conflicts(bare_conflicts, dry_run)` | Interactive conflict resolution. Handles already-converted seasons. |
| `collect_warnings(grouped, passthrough)` | Detects duplicate seasons and name overlaps |


## Function Reference: make_movies_links.py

| Function | Purpose |
|----------|---------|
| `extract_year(name)` | Year extraction requiring preceding separator (prevents "1917" misread) |
| `clean_title(name)` | Aggressive title cleaning for movie names |
| `is_miniseries_folder(path)` | True if 2+ episode files. Used to skip miniseries. |
| `is_ambiguous_parts_folder(path)` | True if 2+ Part.N files with no real episode markers |
| `scan_movies()` | Categorizes entries into movies/flagged/skipped/ambiguous |
| `_resolve_versions(seen)` | Multi-version grouping with quality suffixes and .2/.3 for duplicates |
| `tmdb_search(title)` | TMDB movie lookup with caching |
| `resolve_flagged_via_tmdb(flagged, dry_run)` | Concurrent TMDB lookup for yearless entries |
| `handle_ambiguous(ambiguous, dry_run)` | Prompts user to route Part.N folders as movie or TV |
| `_route_ambiguous_as_movie(entry, title, year, parts, dry_run)` | Symlinks ambiguous folder as movie (largest file) |


## Bare File Handling Matrix

### Formats Parsed by parse_bare_episode()

| # | Format | Source file | Output file | Status |
|---|--------|------------|-------------|--------|
| 1 | SxxExx | `Breaking.Bad.S01E01.720p.WEB-DL.mkv` | `Breaking Bad.S01E01 - 720P.mkv` | Working |
| 2 | SxxExx (no quality) | `Show.Name.S02E03.mkv` | `Show Name.S02E03.mkv` | Working |
| 3 | Multi-ep S01E05-E06 | `Fallout.S01E05-E06.1080p.mkv` | `Fallout.S01E05-E06 - 1080P.mkv` | Working (v0.25) |
| 4 | Multi-ep S01E05E06 | `Show.S01E05E06.1080p.mkv` | `Show.S01E05-E06 - 1080P.mkv` | Working (v0.25) |
| 5 | NxNN | `Futurama.3x05.720p.mkv` | `Futurama.S03E05 - 720P.mkv` | Working |
| 6 | Episode.N | `Some.Documentary.Episode.4.1080p.mkv` | `Some Documentary.S01E04 - 1080P.mkv` | Working (v0.25) |
| 7 | Trailing year stripped | `Bluey.2018.S01E05.1080p.mkv` | `Bluey.S01E05 - 1080P.mkv` | Working |
| 8 | NAME_OVERRIDE | `The.Office.US.S01E01.720p.mkv` | `The Office (US).S01E01 - 720P.mkv` | Working |
| 9 | TMDB resolution | `A.Knight.of.the.Seven.Kingdoms.S01E06.1080p.WEB-DL.mkv` | `A Knight of the Seven Kingdoms.S01E06 - 1080P.mkv` | Working |
| 10 | Studio prefix (matching) | `Marvels.Spidey.and.His.Amazing.Friends.S01E01.1080p.mkv` | `Spidey and His Amazing Friends.S01E01 - 1080P.mkv` | Working |
| 11 | .ts extension | `Old.Show.S01E01.HDTV.ts` | `Old Show.S01E01 - HDTV.ts` | Working |
| 12 | .m4v extension | `Retro.Show.S02E03.480p.m4v` | `Retro Show.S02E03 - 480P.m4v` | Working |

### Formats NOT Parsed (Land in UNMATCHED)

| # | Format | Source file | Why | Workaround |
|---|--------|------------|-----|------------|
| 13 | NofN | `Planet.Earth.1of6.720p.mkv` | Title boundary ambiguous | NAME_OVERRIDE or manual |
| 14 | No pattern | `random_video_no_pattern.mkv` | No episode marker | Manual placement |
| 15 | sample.mkv | `sample.mkv` | Filtered by is_sample() | Expected behavior |

### Conflict Scenarios

| # | Scenario | What happens | Status |
|---|----------|-------------|--------|
| 16 | Same quality, covered | Silently skipped | Working |
| 17 | Different quality | Prompt to convert season, add variant | Working |
| 18 | Missing episode | Prompt to convert season, add episode | Working |
| 19 | Multiple conflicts, same season | First converts, rest add directly (no crash) | Working (v0.25) |
| 20 | Re-run after conversion | Detected as bare_dir_episode, adds directly | Working |
| 21 | Duplicate season (diff quality) | User prompted to choose quality | Working (v0.25) |

### TMDB Confidence Check

| Parsed name | TMDB result | Accepted? | Why |
|------------|-------------|-----------|-----|
| "Fallout" | "Fallout" | Yes | Exact match |
| "The Office" | "The Office US" | Yes | All words + 1 extra (allowed) |
| "Retro Show" | "Super Maximum Retro Show" | No | TMDB 4 words > 2+1=3, too long |
| "Retro Show" | "Amazing World of Gumball" | No | 0 word overlap |


## Planned Work (Priority Order)

### High Priority

1. **Unified entry point + config file.** Single `medialn.py` with YAML/TOML config. Eliminates duplicated path settings, enforces run order, single PathGuard init.

2. **TITLE_OVERRIDES for movies script.** Same pattern as TV's NAME_OVERRIDES. Corrects titles and years before symlink creation.

3. **Orphan scan script.** Walks source dirs, checks for corresponding symlinks in -linked/, reports orphaned source files.

### Medium Priority

4. **NofN bare file parsing.** Dedicated regex for "1of6" style patterns with explicit title boundary detection.

5. **TMDB confidence improvements.** Levenshtein distance, word order weighting, optional user confirmation.

6. **Verbose/quiet output modes.** `--verbose` logs skipped duplicates. `--quiet` for cron/scheduled runs.

### Lower Priority

7. **Config-controlled pass-through cleanup.** `CLEAN_PASSTHROUGH_NAMES = True/False` setting.

8. **Hardlink mode.** For single-filesystem users who want hardlinks for arr compatibility.

9. **Watch mode / inotify.** Auto-re-run when new files appear.

10. **Web UI.** View library state, resolve conflicts, manage overrides.


## Design Decisions Log

| Decision | Rationale |
|----------|-----------|
| Symlinks not hardlinks | MergerFS EXDEV. Symlinks follow unified mount paths. |
| Absolute container paths | Relative symlinks break when container working directory differs from host. |
| Movies script runs first | TV script reads /movies/ for miniseries. Consistent routing. |
| Part.N excluded from miniseries | Could be multi-part film or miniseries. Heuristics break. Human routing only. |
| Arr rename OFF during import | Arr rename renames symlink entries, not source files. Causes mismatches during bulk import. |
| Season symlink -> real dir for variants | Can't write into a symlink without writing into source. Real dir allows mixed content. |
| normalize_for_match() vs normalize_show_key() | Pass 1 grouping needs light normalization. Cross-source matching needs aggressive normalization. |
| TMDB word-overlap check | Blind acceptance causes false matches on short titles. |
| Safe pass-through cleanup only | Aggressive cleanup could break already-structured folders. |
| PathGuard as runtime enforcement | Convention is not enforcement. Guard makes bad writes a crash, not silent data loss. |
| validate_output_dir on every startup | Sentinel files miss config changes between runs. Content scan checks what's actually there. |
| Multi-ep combined naming | Jellyfin/Sonarr recognize S01E05-E06. Two separate symlinks for same file looks wrong. |
| User prompt for duplicate quality | Auto-merge confuses Sonarr. User knows which quality they want. | 
