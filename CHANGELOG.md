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

