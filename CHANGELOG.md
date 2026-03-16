## Changelog
---

### v0.24 to v0.25 (Bug fixes and improvements from test results)

**common.py:**

-   Added `RE_MULTI_EP` regex for detecting multi-episode continuation patterns (S01E05-E06)
-   Added `is_episode_strict()` which excludes Part.N from episode detection
-   Added `clean_passthrough_name()` for safe cosmetic cleanup of pass-through folder names (dots to spaces, whitespace normalization only)
-   Version bump to v0.25

**make\_tv\_links.py:**

-   **BUG-01 fix:** `handle_bare_conflicts()` now checks if season dir was already converted to real dir by a previous conflict in the same run before attempting conversion. Prevents `os.readlink()` crash on real directories.
-   **BUG-02 fix:** Added `_tmdb_word_overlap()` confidence check. Short names (1-2 words) require all parsed words present and TMDB result at most 1 word longer. Longer names require half word overlap. Rejected matches print `[TMDB] Rejected` and fall back to parsed name.
-   **BUG-03 fix:** `scan_movies_for_miniseries()` now uses `episode_info_strict()` which excludes Part.N. Multi-part films like Kill Bill are no longer falsely detected as miniseries.
-   **BUG-04 fix:** `convert_season_symlink_to_real_dir()` extracts quality from source folder name and uses it as fallback when individual filenames don't have quality tags. Consistent naming across all episodes in a converted season.
-   **BUG-05 fix:** `parse_bare_episode()` now handles Episode.N format (defaults to season 1). NofN intentionally excluded due to fragile title boundary.
-   **BUG-06 fix:** `parse_bare_episode()` returns 5-tuple with `second_ep` for multi-episode files. `build_episode_link_name()` constructs combined names like `Show.S01E05-E06 - 1080P.mkv`. All bare file tuples updated to carry `second_ep`.
-   **BUG-07 fix:** Added `resolve_duplicate_seasons()`. Prompts user to choose which quality to link when multiple folders exist for the same season number. Dry-run picks first option automatically.
-   Added `build_episode_link_name()` helper to centralize link filename construction
-   Added `episode_info_strict()` matching `is_episode_strict()` but returning (season, episode) tuple
-   Pass-through entries now use `clean_passthrough_name()` for display (dots to spaces)
-   Version bump to v0.25


## v0.23 to v0.24 (PathGuard and immutability)

**common.py:**

-   Added `SourceProtectionError` exception class
-   Added `PathGuard` class with source/output path registration, lock enforcement, and `assert_writable()` validation
-   Added `init_path_guard()`, `get_path_guard()` module-level guard management
-   Added `safe_remove()`, `safe_rmdir()`, `safe_makedirs()`, `safe_symlink()` guarded write functions
-   Added `validate_output_dir()` startup scan for real video files in output directory
-   Changed `make_symlink()` to use `safe_symlink()` internally
-   Changed `ensure_dir()` to use `safe_makedirs()` internally
-   Changed `clean_broken_symlinks()` to use guarded functions and pre-validate directory

**make\_tv\_links.py:**

-   Added `init_path_guard()` and `validate_output_dir()` calls at start of `main()`
-   Changed `convert_season_symlink_to_real_dir()`: `os.remove()` to `safe_remove()`, `os.makedirs()` to `safe_makedirs()`, `os.symlink()` to `safe_symlink()`

**make\_movies\_links.py:**

-   Added `init_path_guard()` and `validate_output_dir()` calls at start of `main()`
-   Added `_tmdb_movie_cache` dict for TMDB result caching (matching TV script pattern)

**test\_path\_guard.py (new file):**

-   41 tests: 13 unit tests for path logic, 10 guarded function integration tests, 9 output validation tests, 9 config mistake scenario tests
-   TestEnv context manager for building realistic fake media trees under /tmp/

**create\_test\_library.py (new file):**

-   Builds a 72-file fake media library covering all parsing scenarios
-   Small files (217KB total) with correct relative sizes for `largest_video()` testing


## v0.23 Changelog

### `common.py`

**`clean_broken_symlinks()` incorrectly treating all medialn symlinks as broken**
- `os.path.exists()` follows symlinks and checks if the target exists at the literal path
- medialn writes symlinks using container-side paths (`/data/media/...`) — those paths don't exist on the host (`/mnt/storage/data/media/...`), so every symlink was being treated as broken
- `--clean` was removing all episode symlinks inside converted real directories, causing empty dirs to be pruned and Pass 1 to recreate them as folder symlinks on rebuild — this is what caused the quality conflict prompt to reappear on re-run
- New `_symlink_target_exists()` helper added — reads symlink target, translates container path to host path if roots are provided, then checks existence against the translated path
- `clean_broken_symlinks()` now accepts `host_root` and `container_root` optional parameters and uses `_symlink_target_exists()` for all existence checks

---

### `make_tv_links.py`

**Quality conflict resolution re-prompted on subsequent runs and crashed on confirmation**
- After a `quality_variant` conflict was resolved (season symlink converted to real dir, variant linked), re-running showed the same prompt again with incorrect message `"Season Season 01 is currently a folder symlink"`
- Root cause: `scan_tv_bare_files()` detected a quality variant by checking the source folder contents — which always shows different qualities — without checking the actual state of the season directory in `tv-linked/`
- On confirmation at the re-prompt, `convert_season_symlink_to_real_dir()` called `os.readlink()` against the now-real directory, which is an invalid operation on Linux — `[ERROR] Could not read symlink: Invalid argument`
- Fix: in the `quality_variant` branch, check whether `season_path` is already a real directory before classifying the conflict
    - If real dir exists and the variant symlink is already inside it — skip silently
    - If real dir exists but variant not yet inside it — reroute to `bare_dir_episode` conflict type, which adds the symlink directly without attempting conversion
- Same fix applied to `missing_episode` branch — identical root cause, same incorrect behavior would occur on re-run after conversion

**`clean_broken_symlinks()` call updated**
- `clean_broken_symlinks(TV_LINKED)` → `clean_broken_symlinks(TV_LINKED, MEDIA_ROOT_HOST, MEDIA_ROOT_CONTAINER)`

---

### `make_movies_links.py`

**`clean_broken_symlinks()` call updated**
- `clean_broken_symlinks(MOVIES_LINKED)` → `clean_broken_symlinks(MOVIES_LINKED, MEDIA_ROOT_HOST, MEDIA_ROOT_CONTAINER)`

**Local `RE_QUALITY` and `extract_quality()` removed**
- Both were defined locally as duplicates of the versions now in `common.py`
- `RE_QUALITY` local definition removed
- `extract_quality()` local definition removed
- `extract_quality` added to the `from common import (...)` block

**Hardcoded TMDB API key removed**
- Private fork API key was present in the uploaded file — reverted to `os.environ.get("TMDB_API_KEY", "")` for the public version

**Dead variable removed**
- `raw_entries = []` in `scan_movies()` was assigned but never used — removed

###  TV Script testing

-   **Pass 1 folder grouping** - season folders grouped, named, symlinked correctly
-   **Pass-through** - already-structured folders symlinked as-is
-   **Miniseries from /movies/** - correctly detected and routed to tv-linked
-   **Bare file new show/season** - real dir created, episodes linked, idempotent
-   **Bare file quality variant** - conflict detected, prompt works, season converted, both qualities coexist, no re-prompt
-   **Bare file missing episode** - conflict detected, prompt works, season converted, episode added, no re-prompt
-   **Sonarr hardlink collision** - script skips existing hardlinks, link count intact
-   **`--clean`** - only removes genuinely broken symlinks, container path translation working correctly, real dirs and their contents preserved
-   **Idempotency** - re-runs fully silent on already-linked content
-   **Name resolution** - fuzzy matching working across TMDB/folder parse differences, trailing year stripping working, apostrophe normalization correct




## v0.22 

### Bug fix - duplicate show folders from name mismatch between Pass 1 and Pass 2

**The problem:** When a bare episode file arrives for a show that already has season folders linked, the two passes could produce different canonical names for the same show. Pass 1 parses folder names directly. Pass 2 goes through TMDB. TMDB doesn't always return the same string that folder parsing produces. "Marvel's Spidey and His Amazing Friends" from a folder became "Spidey and His Amazing Friends" from TMDB, and the normalized key comparison failed to match them, creating a second show folder on disk.

**The fix:** New `normalize_for_match()` function used exclusively for cross-source comparison. It strips leading articles (the, a, an), studio prefixes (Marvel's, DC's, Disney's, BBC, NBC), possessives, trailing years, and all remaining punctuation before comparing. This is intentionally more aggressive than `normalize_show_key()`, which is still used for grouping Pass 1 folders where light normalization is correct.

New `find_matching_show()` function replaces the inline key lookup in `scan_tv_bare_files()`. It runs two stages: first checks the Pass 1 grouped dict using fuzzy matching, then falls back to scanning existing folders in `tv-linked/` on disk. The disk fallback catches cases where a show was created in a previous run and isn't in the current run's grouped dict.

When a fuzzy match succeeds, the bare file adopts the already-established name rather than creating a new one.

---

### Bug fix - trailing year in filename producing split show folders

**The problem:** Files named `Fallout.2024.S01E01.mkv` produced raw show name `"Fallout 2024"` from `parse_bare_episode()`. Pass 1 already stripped trailing years via `extract_show_and_season()`. Pass 2 did not, so the normalized keys never matched and a second `Fallout 2024` folder appeared alongside the existing `Fallout` folder.

**The fix:** `parse_bare_episode()` now strips trailing four-digit years from the parsed show name before returning, matching the same logic Pass 1 already applies to folder names.

---

### New function: `normalize_for_match()`

Separate normalization path for cross-source name comparison only. Never used for display names or folder creation. The distinction between this and `normalize_show_key()` is intentional and documented in both functions.

### New function: `find_matching_show()`

Two-stage show name lookup: grouped dict first, disk scan second. Centralizes the matching logic that was previously inline in `scan_tv_bare_files()` and makes it testable in isolation.


**v.21**

### New — bare episode file handling (TV script)

The TV script now handles video files sitting directly in `/tv/` with no parent folder. Previously these were silently ignored.

**Name resolution**

-   Show names are resolved automatically via TMDB TV search before falling back to the parsed filename title
-   `NAME_OVERRIDES` take priority over TMDB — existing overrides are unaffected
-   TMDB results are cached per run so each unique show name only hits the API once

**New output section: `[BARE FILES - NEW]`** Episodes with no existing season structure are linked automatically with no prompts. Show and season directories are created as real directories (not symlinks) with individual episode symlinks inside.

**New output section: `[BARE FILES - CONFLICTS]`** Episodes that collide with existing season structure are flagged interactively:

-   Episode already covered at same quality: silently skipped
-   Episode exists in folder at different quality: prompts to convert season symlink to real dir and add quality variant
-   Episode missing from existing season folder: prompts to convert and add
-   Season real dir exists from previous run, episode not yet linked: prompts to add

**New output section: `[BARE FILES - UNMATCHED]`** Files that couldn't be parsed into show/season/episode are listed at the end for manual handling.

**Idempotent** Re-running after bare files have been linked skips already-linked episodes silently. Safe to run repeatedly.

* * *

### Bug fix — duplicate regex definitions (TV script)

`RE_XNOTATION`, `RE_EPISODE`, and `RE_NOF` were defined locally in the TV script despite already existing in `common.py`. The local definitions are removed and the TV script now imports them from common along with the rest of the shared patterns. Behavior is identical but the two scripts are now properly in sync — a pattern change in `common.py` will apply to both scripts.

* * *

### common.py — extract\_quality() added

`extract_quality()` and its `RE_QUALITY` pattern moved into `common.py` and are now shared across both scripts. The TV script imports it from common. The movies script still has a local copy pending cleanup.

* * *

### New imports (TV script)

`json`, `urllib.request`, `urllib.parse` added to support TMDB TV lookup.

* * *

### Known pending

-   `make_movies_links.py` local `extract_quality()` not yet removed — carry forward to next update



**v.20:**
- Extracted shared code into `common.py` - both scripts now import from the same place instead of duplicating logic
- Removed dead code (`is_episode()` was defined but unused in the TV script)
- Extracted interactive Part.N routing out of `main()` into its own function
- Cleaned up multi-version resolution logic (was re-parsing a string it had just built)
- `clean_broken_symlinks` now checks both file and directory symlinks everywhere (the movies version was only checking files)
- Video-finding logic consolidated into shared helpers instead of being repeated in multiple places
- General cleanup: comments, docstrings, formatting

**v.12:**
- Added Part.N detection and ambiguous folder handling to movies script
- Added Part.N as last-resort episode pattern in TV script
- Interactive prompt for routing ambiguous Part.N folders as movie or TV
