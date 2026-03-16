# Changelog

## v1.0.0 -- Unified package release

Complete restructure from two standalone scripts into a unified Python package with TOML config, subcommands, and per-run logging.

### Architecture

- **Package structure.** `medialnk/` directory with 7 modules replacing 3 standalone scripts. Runs as `python3 -m medialnk`.
- **TOML config.** All paths, API keys, overrides, and settings in one `medialnk.toml` file. No more editing Python variables at the top of scripts. Requires Python 3.11+ for stdlib `tomllib`.
- **Subcommands.** `sync`, `clean`, `validate`, `test-library` replace the old `make_movies_links.py` / `make_tv_links.py` / `create_test_library.py` scripts.
- **Single entry point.** `medialnk sync` runs both movies and TV pipelines in the correct order with one PathGuard init. `--tv-only` and `--movies-only` for selective runs.
- **Auto-accept mode.** `medialnk sync --yes` accepts all prompts automatically. Picks first option for duplicate seasons, accepts all conflict conversions, routes ambiguous Part.N as movies. Combined with `-q` for cron-friendly operation.
- **Verbosity levels.** quiet/normal/verbose/debug. Default shows summary counts. `-v` shows every link. `-vv` shows regex decisions and TMDB calls. `-q` shows only errors and warnings.
- **Per-run log files.** Written to configured `log_dir` on every live sync (not dry-run). Log always gets verbose-level detail regardless of console verbosity.
- **Unified resolver.** `resolver.py` combines the previously separate movie and TV TMDB implementations. Single cache, shared confidence checking, no code duplication.
- **Code reduction.** ~2,300 lines across 3 files -> ~1,500 lines across 7 files. Duplicate main() flows, config variables, TMDB code, and wrapper functions eliminated.

### Config

- Config file searched at `./medialnk.toml`, then `~/.config/medialnk/medialnk.toml`. Override with `--config`.
- Relative paths resolved against `media_root_host`.
- TMDB API key via config or `TMDB_API_KEY` env var.
- TV name overrides and orphan overrides as TOML tables.
- Movie title overrides table (planned, not yet implemented).

### Migration from v0.25

- Move `MEDIA_ROOT_HOST`, `MEDIA_ROOT_CONTAINER` from script tops to `[paths]` in `medialnk.toml`.
- Move `NAME_OVERRIDES` dict to `[overrides.tv_names]` table.
- Move `ORPHAN_OVERRIDES` dict to `[overrides.tv_orphans]` table (format: `"folder" = { show = "Name", season = 1 }`).
- Move `TMDB_API_KEY` to `[tmdb]` section or keep as env var.
- Replace `python3 make_tv_links.py --dry-run` with `medialnk sync --dry-run --tv-only`.
- Replace `python3 make_movies_links.py --dry-run` with `medialnk sync --dry-run --movies-only`.
- Old scripts remain usable but are no longer maintained.

---

## v0.25 -- Bug fixes from real-world testing

Seven bugs fixed from test library results, plus improvements.

### Bug fixes

- **BUG-01 (critical): Season conversion crash on subsequent conflicts.** When multiple bare files conflicted with the same season (e.g. Breaking Bad E01 quality variant + E07 missing + E08 missing), the first conflict converted the season symlink to a real directory. The second and third then called `os.readlink()` on the now-real directory, crashing with EINVAL. Fix: before attempting conversion, check if the season dir was already converted by a prior conflict in the same run and add the episode directly.

- **BUG-02: TMDB false match on short/generic titles.** "Retro Show" parsed from filename, TMDB returned "Super Maximum Retro Show". Fix: `_word_overlap()` confidence check. Short names (1-2 words) require all parsed words present and TMDB result at most 1 word longer. Longer names require 50%+ word overlap. Rejected matches print `[TMDB] Rejected` and fall back to parsed name.

- **BUG-03: Kill Bill Part.N treated as miniseries.** `scan_movies_for_miniseries()` used `episode_info()` which includes `RE_PART`. Kill Bill Part.1 and Part.2 matched, bypassing the movies script's ambiguity prompt. Fix: miniseries scanning uses `episode_info(include_part=False)`. Part.N-only folders left for movies script's prompt.

- **BUG-04: Inconsistent naming after season conversion.** Bluey Season 01 had mixed quality tags after conversion (folder episodes had none, bare file had one). Fix: `convert_season_to_real_dir()` extracts quality from source folder name and uses it as fallback for files without their own quality tag.

- **BUG-05: Episode.N format not parsed by bare file scanner.** `Some.Documentary.Episode.4.1080p.mkv` landed in UNMATCHED. Fix: `parse_bare_episode()` now handles Episode.N format (season defaults to 1). NofN intentionally excluded (fragile title boundary).

- **BUG-06: Double-episode files only linked first episode.** `Fallout.S01E05-E06.1080p.mkv` only created E05 link. Fix: `parse_bare_episode()` returns 5-tuple with `second_ep`. `build_link_name()` constructs combined names: `Show.S01E05-E06 - 1080P.mkv`. Jellyfin and Sonarr recognize this format.

- **BUG-07: Duplicate season quality variant silently lost.** Fallout S01 at 1080p and 2160p; only first was linked. Fix: `resolve_duplicate_seasons()` prompts user to choose which quality to link. Dry-run and auto modes pick first option.

### Improvements

- **Pass-through name cleaning.** `clean_passthrough_name()` converts dots to spaces for scene-named pass-through folders. Does not strip years, metadata, or canonicalize.
- **Centralized link name building.** `build_link_name()` constructs all episode symlink filenames, eliminating inconsistencies between different code paths.

---

## v0.24 -- PathGuard immutability system

Runtime enforcement that source media files can never be modified.

### PathGuard

- `PathGuard` class validates every filesystem write against registered source and output paths.
- Four guarded functions (`safe_remove`, `safe_rmdir`, `safe_makedirs`, `safe_symlink`) are the only write operations in the codebase.
- Writes to source dirs raise `SourceProtectionError` (hard crash).
- Writes outside all registered dirs also raise (prevents random filesystem writes).
- Output-inside-source and output-equals-source rejected at lock time.
- Guard initialized once at startup, locked, immutable.

### Output directory validation

- `validate_output_dir()` scans output dirs for real (non-symlink) video files on every startup.
- Catches config mistakes where the output is actually a real media library.
- Warns, lists files, prompts user. Default is abort.
- Dry-run warns but does not block.

### Test suite

- 41 tests covering path logic, guarded functions, output validation, and config mistake scenarios.
- `TestEnv` context manager builds realistic fake media trees under `/tmp/`.
- Tests include: output==source rejected, output-inside-source rejected, swapped paths caught, every safe_* function blocked on source, clean preserves source, random path writes blocked, file count stability.

---

## v0.23 -- Symlink target translation fix

### common.py

- `clean_broken_symlinks()` was incorrectly treating all medialnk symlinks as broken. Container-side symlink targets (`/data/media/...`) don't exist at that path on the host. New `_symlink_target_exists()` translates container paths to host paths before checking existence.

### make_tv_links.py

- Quality conflict resolution crash on re-run fixed. After converting a season symlink to a real dir, re-running showed the same prompt and crashed on `os.readlink()` against the real directory. Fix: check actual state of the season dir before classifying conflicts.

---

## v0.22 -- Fuzzy name matching

- `normalize_for_match()` for cross-source name comparison. Strips articles, studio prefixes, possessives, trailing years, punctuation.
- `find_matching_show()` two-stage lookup: grouped dict then disk scan.
- Prevents duplicate show folders when TMDB and folder parsing produce different canonical names.
- Trailing year stripping in `parse_bare_episode()` to match Pass 1 behavior.

---

## v0.21 -- Bare episode file handling

- Pass 2 scanner for video files sitting directly in `/tv/`.
- TMDB TV search with caching for automatic show name resolution.
- Interactive conflict resolution: quality variants, missing episodes, season symlink conversion.
- Idempotent re-runs (already-linked episodes silently skipped).

---

## v0.20 -- Code extraction

- Shared code extracted into `common.py`.
- Interactive Part.N routing extracted from `main()`.
- `clean_broken_symlinks` handles both file and directory symlinks.

---

## v0.12 -- Part.N detection

- Part.N as last-resort episode pattern.
- Ambiguous Part.N folder routing (movie vs TV prompt).
