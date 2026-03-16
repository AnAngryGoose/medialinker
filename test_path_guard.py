#!/usr/bin/env python3
"""
test_path_guard.py

Tests for the PathGuard immutability system and output directory validation
in common.py.

Uses a TestEnv context manager that builds realistic fake media directory
trees under /tmp/. All paths are configurable through TestEnv rather than
hardcoded per test. Every test cleans up after itself. Nothing outside
/tmp/ is ever touched.

Run:
    python3 test_path_guard.py
"""

import os
import sys
import io
import tempfile

# Add the project dir to the path so we can import common
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    PathGuard, SourceProtectionError,
    init_path_guard, get_path_guard,
    safe_remove, safe_rmdir, safe_makedirs, safe_symlink,
    ensure_dir, make_symlink, clean_broken_symlinks,
    validate_output_dir, is_video,
)

# ---------------------------------------------------------------------------
# Test environment
# ---------------------------------------------------------------------------

class TestEnv:
    """Builds a fake media directory tree under /tmp/ for testing.

    Creates the same directory structure the real scripts operate on:
    a media root with source dirs and output dirs. Provides helpers to
    populate source dirs with fake video files and output dirs with
    symlinks or real files to simulate both correct operation and
    misconfiguration.

    Use as a context manager:

        with TestEnv() as env:
            init_path_guard(
                sources=[env.movies_source, env.tv_source],
                outputs=[env.movies_linked, env.tv_linked],
            )
            # env.movies_source is e.g. /tmp/xxx/media/movies
            # files created with env.add_source_video(...) are real files
            # files created with env.add_output_symlink(...) are symlinks

    All paths are under a single tempdir that gets deleted on exit.
    """

    def __init__(self):
        self._tmpdir = None
        self.root = None

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="medialn_test_")
        self.root = os.path.join(self._tmpdir, "media")

        # Source dirs (where real media files live)
        self.movies_source = os.path.join(self.root, "movies")
        self.tv_source     = os.path.join(self.root, "tv")

        # Output dirs (where medialn writes symlinks)
        self.movies_linked = os.path.join(self.root, "movies-linked")
        self.tv_linked     = os.path.join(self.root, "tv-linked")

        # Create all four dirs
        for d in [self.movies_source, self.tv_source,
                  self.movies_linked, self.tv_linked]:
            os.makedirs(d)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._tmpdir and os.path.isdir(self._tmpdir):
            # Walk bottom-up and force-remove everything. Some tests create
            # symlinks that point to nonexistent targets, which is fine.
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        return False

    # -- Populate source dirs with fake video files -----------------------

    def add_source_video(self, relative_path, source="movies", size_bytes=1024):
        """Create a fake video file in a source directory.

        relative_path: path relative to the source dir, e.g.
            "Movie.2024.1080p/Movie.2024.1080p.mkv"
            or just "bare_file.mkv" for a file at the source root.
        source: "movies" or "tv"
        """
        base = self.movies_source if source == "movies" else self.tv_source
        full_path = os.path.join(base, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(b'\x00' * size_bytes)
        return full_path

    # -- Populate output dirs with symlinks (correct state) ---------------

    def add_output_symlink(self, relative_path, target, output="movies-linked"):
        """Create a symlink in an output directory pointing at target.

        relative_path: path relative to the output dir, e.g.
            "Movie (2024)/Movie (2024).mkv"
        target: what the symlink points at (absolute path)
        output: "movies-linked" or "tv-linked"
        """
        base = self.movies_linked if output == "movies-linked" else self.tv_linked
        full_path = os.path.join(base, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        os.symlink(target, full_path)
        return full_path

    # -- Populate output dirs with real files (misconfigured state) -------

    def add_output_real_video(self, relative_path, output="movies-linked", size_bytes=1024):
        """Create a real (non-symlink) video file in an output directory.

        This simulates a misconfiguration where the output dir is
        actually a real media library. Used to test validate_output_dir().
        """
        base = self.movies_linked if output == "movies-linked" else self.tv_linked
        full_path = os.path.join(base, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(b'\x00' * size_bytes)
        return full_path

    # -- Build a populated fake library -----------------------------------

    def populate_source_library(self):
        """Fill source dirs with a small realistic fake media library.

        Creates enough structure to simulate what a real library looks like
        so tests for config mistakes have something to find.
        """
        # Movies
        self.add_source_video("Dune.2021.1080p.BluRay/Dune.2021.1080p.BluRay.mkv")
        self.add_source_video("Dune.Part.Two.2024.2160p/Dune.Part.Two.2024.2160p.mkv")
        self.add_source_video("The.Matrix.1999.1080p/The.Matrix.1999.1080p.mkv")
        self.add_source_video("Oppenheimer.2023.REMUX/Oppenheimer.2023.REMUX.mkv")
        self.add_source_video("bare.movie.2020.720p.mkv")

        # TV
        self.add_source_video("Breaking.Bad.S01.1080p/Breaking.Bad.S01E01.mkv", source="tv")
        self.add_source_video("Breaking.Bad.S01.1080p/Breaking.Bad.S01E02.mkv", source="tv")
        self.add_source_video("Fallout.S01.2160p/Fallout.S01E01.mkv", source="tv")
        self.add_source_video("Fallout.S01.2160p/Fallout.S01E02.mkv", source="tv")

    def populate_correct_output(self):
        """Fill output dirs with symlinks pointing at source files.

        This is what the output should look like after a normal medialn run.
        """
        self.populate_source_library()

        self.add_output_symlink(
            "Dune (2021)/Dune (2021).mkv",
            os.path.join(self.movies_source, "Dune.2021.1080p.BluRay/Dune.2021.1080p.BluRay.mkv"),
        )
        self.add_output_symlink(
            "The Matrix (1999)/The Matrix (1999).mkv",
            os.path.join(self.movies_source, "The.Matrix.1999.1080p/The.Matrix.1999.1080p.mkv"),
        )
        self.add_output_symlink(
            "Breaking Bad/Season 01",
            os.path.join(self.tv_source, "Breaking.Bad.S01.1080p"),
            output="tv-linked",
        )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

passed = 0
failed = 0


def test(name, fn):
    """Run a single test function and report pass/fail."""
    global passed, failed
    try:
        fn()
        print(f"  [PASS] {name}")
        passed += 1
    except AssertionError as e:
        print(f"  [FAIL] {name}")
        print(f"         {e}")
        failed += 1
    except Exception as e:
        print(f"  [FAIL] {name}")
        print(f"         Unexpected error: {type(e).__name__}: {e}")
        failed += 1


def expect_blocked(fn, msg="Expected SourceProtectionError"):
    """Assert that fn() raises SourceProtectionError."""
    try:
        fn()
        raise AssertionError(msg)
    except SourceProtectionError:
        pass  # Expected


def expect_runtime_error(fn, msg="Expected RuntimeError"):
    """Assert that fn() raises RuntimeError."""
    try:
        fn()
        raise AssertionError(msg)
    except RuntimeError:
        pass  # Expected


def suppress_stdout():
    """Return (old_stdout, captured) for muting print output during tests."""
    old = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    return old, captured


def mock_stdin(text):
    """Replace stdin with a StringIO containing text. Returns old stdin."""
    old = sys.stdin
    sys.stdin = io.StringIO(text)
    return old


# ---------------------------------------------------------------------------
# PathGuard unit tests
# ---------------------------------------------------------------------------

def test_basic_source_blocked():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        expect_blocked(lambda: g.assert_writable(
            os.path.join(env.movies_source, "somefile.mkv")
        ))


def test_basic_output_allowed():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        # Should not raise
        g.assert_writable(os.path.join(env.movies_linked, "Movie Name", "file.mkv"))


def test_nested_source_blocked():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        expect_blocked(lambda: g.assert_writable(
            os.path.join(env.movies_source, "subfolder", "deep", "file.mkv")
        ))


def test_source_dir_itself_blocked():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        expect_blocked(lambda: g.assert_writable(env.movies_source))


def test_output_dir_itself_allowed():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        g.assert_writable(env.movies_linked)


def test_unregistered_path_blocked():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        expect_blocked(lambda: g.assert_writable("/tmp/random/unregistered/path"))


def test_similar_prefix_not_blocked():
    """'movies-linked' should NOT be blocked by source 'movies'.
    The guard checks for exact path + os.sep prefix, not string prefix."""
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        g.assert_writable(os.path.join(env.movies_linked, "test.mkv"))


def test_multiple_sources():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_source(env.tv_source)
        g.register_output(env.movies_linked)
        g.register_output(env.tv_linked)
        g.lock()

        expect_blocked(lambda: g.assert_writable(
            os.path.join(env.movies_source, "file.mkv")))
        expect_blocked(lambda: g.assert_writable(
            os.path.join(env.tv_source, "file.mkv")))
        g.assert_writable(os.path.join(env.movies_linked, "file.mkv"))
        g.assert_writable(os.path.join(env.tv_linked, "file.mkv"))


def test_output_inside_source_rejected():
    """Registering an output dir inside a source dir should fail at lock time."""
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.root)
        g.register_output(os.path.join(env.root, "nested-output"))

        expect_blocked(lambda: g.lock())


def test_lock_prevents_registration():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        g.lock()

        expect_runtime_error(lambda: g.register_source(env.tv_source))
        expect_runtime_error(lambda: g.register_output(env.tv_linked))


def test_unlocked_guard_rejects_writes():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_linked)
        # Deliberately NOT calling g.lock()

        expect_runtime_error(lambda: g.assert_writable(
            os.path.join(env.movies_linked, "test")
        ))


def test_duplicate_registration_harmless():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_source(env.movies_source)  # duplicate
        g.register_output(env.movies_linked)
        g.register_output(env.movies_linked)  # duplicate
        g.lock()

        assert len(g._sources) == 1
        assert len(g._outputs) == 1


def test_guard_with_trailing_slashes():
    with TestEnv() as env:
        g = PathGuard()
        g.register_source(env.movies_source + "/")
        g.register_output(env.movies_linked + "/")
        g.lock()

        expect_blocked(lambda: g.assert_writable(
            os.path.join(env.movies_source, "file.mkv")))
        g.assert_writable(os.path.join(env.movies_linked, "file.mkv"))


# ---------------------------------------------------------------------------
# Guarded function integration tests
# ---------------------------------------------------------------------------

def test_safe_remove_blocks_source():
    """safe_remove() should refuse to delete a file under a source dir."""
    with TestEnv() as env:
        source_file = env.add_source_video("precious.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: safe_remove(source_file))

        assert os.path.exists(source_file), "Source file was deleted!"


def test_safe_remove_allows_output():
    """safe_remove() should work for files under an output dir."""
    with TestEnv() as env:
        output_link = os.path.join(env.movies_linked, "link.mkv")
        os.symlink("/nonexistent/target", output_link)

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        safe_remove(output_link)

        assert not os.path.exists(output_link), "Output symlink was not removed"


def test_safe_makedirs_blocks_source():
    """safe_makedirs() should refuse to create dirs under a source dir."""
    with TestEnv() as env:
        new_dir = os.path.join(env.movies_source, "Show Name", "Season 01")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: safe_makedirs(new_dir))

        assert not os.path.exists(new_dir), "Directory was created in source!"


def test_safe_symlink_blocks_source():
    """safe_symlink() should refuse to create a symlink under a source dir."""
    with TestEnv() as env:
        link_in_source = os.path.join(env.movies_source, "bad_link.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: safe_symlink("/some/target", link_in_source))

        assert not os.path.islink(link_in_source), "Symlink was created in source!"


def test_safe_symlink_allows_output():
    """safe_symlink() should work when link_path is under an output dir.
    Target can point at a source file -- that's the whole idea."""
    with TestEnv() as env:
        source_file = env.add_source_video("movie.mkv")
        link_in_output = os.path.join(env.movies_linked, "good_link.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        safe_symlink(source_file, link_in_output)

        assert os.path.islink(link_in_output), "Symlink was not created in output"


def test_ensure_dir_blocks_source():
    with TestEnv() as env:
        new_dir = os.path.join(env.tv_source, "ShowName")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: ensure_dir(new_dir, dry_run=False))


def test_clean_broken_symlinks_blocks_source():
    """clean_broken_symlinks() should refuse to operate on a source dir."""
    with TestEnv() as env:
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: clean_broken_symlinks(env.movies_source))


def test_clean_broken_symlinks_works_on_output():
    """clean_broken_symlinks() should remove broken links and keep good ones."""
    with TestEnv() as env:
        source_file = env.add_source_video("real.mkv")

        # Good symlink in output (points to real file)
        good_link = os.path.join(env.movies_linked, "good.mkv")
        os.symlink(source_file, good_link)

        # Broken symlink in output (points to nothing)
        broken_link = os.path.join(env.movies_linked, "broken.mkv")
        os.symlink("/nonexistent/file.mkv", broken_link)

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        clean_broken_symlinks(env.movies_linked)

        assert os.path.islink(good_link), "Good symlink was incorrectly removed"
        assert not os.path.islink(broken_link), "Broken symlink was not removed"
        assert os.path.exists(source_file), "Source file was modified!"


def test_safe_rmdir_blocks_source():
    with TestEnv() as env:
        empty_dir = os.path.join(env.movies_source, "empty_show")
        os.makedirs(empty_dir)

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        expect_blocked(lambda: safe_rmdir(empty_dir))

        assert os.path.isdir(empty_dir), "Source directory was removed!"


def test_make_symlink_blocks_source():
    """make_symlink() should go through the guard for the link_path."""
    with TestEnv() as env:
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )

        link_in_source = os.path.join(env.movies_source, "bad.mkv")
        expect_blocked(lambda: make_symlink(
            link_in_source, "/some/target", False,
            env.movies_source, env.movies_source,
        ))


# ---------------------------------------------------------------------------
# Output directory validation tests
# ---------------------------------------------------------------------------

def test_validate_empty_dir_passes():
    """An empty output dir should pass without any warning."""
    with TestEnv() as env:
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdout, _ = suppress_stdout()
        try:
            validate_output_dir(env.movies_linked, dry_run=False)
        finally:
            sys.stdout = old_stdout


def test_validate_nonexistent_dir_passes():
    """A nonexistent output dir should pass (hasn't been created yet)."""
    with TestEnv() as env:
        nonexistent = os.path.join(env.root, "does-not-exist")
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[nonexistent],
        )
        validate_output_dir(nonexistent, dry_run=False)


def test_validate_symlinks_only_passes():
    """An output dir with only symlinks should pass cleanly."""
    with TestEnv() as env:
        env.populate_correct_output()

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdout, _ = suppress_stdout()
        try:
            validate_output_dir(env.movies_linked, dry_run=False)
        finally:
            sys.stdout = old_stdout


def test_validate_real_video_warns_dryrun():
    """Real video files in output dir should warn in dry-run but not block."""
    with TestEnv() as env:
        env.add_output_real_video("Some Movie/movie.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdout, captured = suppress_stdout()
        try:
            validate_output_dir(env.movies_linked, dry_run=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        assert "WARNING" in output, "Expected warning about real video files"
        assert "movie.mkv" in output, "Expected filename in warning"
        assert "dry-run" in output.lower(), "Expected dry-run note"


def test_validate_real_video_blocks_on_no():
    """Real video files + user entering 'n' should abort."""
    with TestEnv() as env:
        env.add_output_real_video("movie.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdin = mock_stdin("n\n")
        old_stdout, _ = suppress_stdout()
        try:
            expect_blocked(lambda: validate_output_dir(env.movies_linked, dry_run=False))
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout


def test_validate_real_video_blocks_on_empty():
    """Real video files + pressing Enter (default N) should abort."""
    with TestEnv() as env:
        env.add_output_real_video("movie.mp4")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdin = mock_stdin("\n")
        old_stdout, _ = suppress_stdout()
        try:
            expect_blocked(lambda: validate_output_dir(env.movies_linked, dry_run=False))
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout


def test_validate_real_video_continues_on_yes():
    """Real video files + user entering 'y' should allow continuation."""
    with TestEnv() as env:
        env.add_output_real_video("movie.mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdin = mock_stdin("y\n")
        old_stdout, _ = suppress_stdout()
        try:
            validate_output_dir(env.movies_linked, dry_run=False)
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout


def test_validate_nested_real_video_detected():
    """Real video files nested in subdirectories should still be caught."""
    with TestEnv() as env:
        env.add_output_real_video("Movie Name (2024)/Movie Name (2024).mkv")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdin = mock_stdin("n\n")
        old_stdout, _ = suppress_stdout()
        try:
            expect_blocked(lambda: validate_output_dir(env.movies_linked, dry_run=False))
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout


def test_validate_non_video_files_ignored():
    """Non-video real files (nfo, srt, jpg) should not trigger the warning."""
    with TestEnv() as env:
        for name in ["movie.nfo", "movie.srt", "notes.txt", "poster.jpg"]:
            path = os.path.join(env.movies_linked, name)
            with open(path, 'w') as f:
                f.write("metadata")

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )
        old_stdout, _ = suppress_stdout()
        try:
            validate_output_dir(env.movies_linked, dry_run=False)
        finally:
            sys.stdout = old_stdout


# ---------------------------------------------------------------------------
# Config mistake scenario tests
#
# These simulate the actual user errors that the safeguards exist to catch.
# ---------------------------------------------------------------------------

def test_scenario_output_equals_source_same_path():
    """User sets MOVIES_LINKED to the same path as MOVIES_SOURCE.

    PathGuard.lock() should reject this because the output dir is
    identical to a source dir (output == source is a subset of
    output-inside-source).
    """
    with TestEnv() as env:
        env.populate_source_library()

        g = PathGuard()
        g.register_source(env.movies_source)
        g.register_output(env.movies_source)  # same path as source

        expect_blocked(lambda: g.lock())


def test_scenario_output_equals_source_via_init():
    """Same as above but through init_path_guard() to test the real call path."""
    with TestEnv() as env:
        env.populate_source_library()

        expect_blocked(lambda: init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_source],  # oops -- same as source
        ))


def test_scenario_output_is_source_subdir():
    """User sets MOVIES_LINKED to a subdirectory inside MOVIES_SOURCE.

    PathGuard.lock() should reject this because the output is nested
    inside a source.
    """
    with TestEnv() as env:
        env.populate_source_library()
        nested_output = os.path.join(env.movies_source, "linked")
        os.makedirs(nested_output)

        expect_blocked(lambda: init_path_guard(
            sources=[env.movies_source],
            outputs=[nested_output],
        ))


def test_scenario_output_points_at_real_library():
    """User points MOVIES_LINKED at a directory full of real media files
    that is NOT registered as a source (e.g. a second drive, a backup).

    PathGuard can't catch this at lock time because the path is not a
    registered source. validate_output_dir() catches it by scanning for
    real video files and prompting before any work begins.

    With default 'n', the script should abort.
    """
    with TestEnv() as env:
        # Create a "real library" dir that isn't registered as source
        real_library = os.path.join(env.root, "other-drive-movies")
        os.makedirs(real_library)

        # Fill it with real video files like an actual media library
        for name in [
            "Dune.2021.1080p/Dune.2021.1080p.mkv",
            "Matrix.1999.720p/Matrix.1999.720p.mkv",
            "Inception.2010/Inception.2010.mkv",
            "bare_movie.mp4",
        ]:
            full = os.path.join(real_library, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as f:
                f.write(b'\x00' * 512)

        # User mistakenly registers this real library as the output
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[real_library],
        )

        # validate_output_dir should find the real video files and prompt
        old_stdin = mock_stdin("n\n")
        old_stdout, captured = suppress_stdout()
        try:
            expect_blocked(
                lambda: validate_output_dir(real_library, dry_run=False),
                msg="validate_output_dir should have blocked -- real video files in output"
            )
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        output = captured.getvalue()
        assert "WARNING" in output, "Expected warning about real video files"
        assert "4 real video file" in output, f"Expected count of 4 real files, got: {output}"


def test_scenario_clean_on_real_library_blocked():
    """Full scenario: user misconfigures output as a real library, then
    runs --clean. Both validate_output_dir and PathGuard should prevent
    any source files from being removed.

    Step 1: validate_output_dir prompts and user says 'n' -- blocked.
    Step 2: Even if validate were bypassed, clean_broken_symlinks on the
            registered output should not remove real files (they aren't
            broken symlinks), but any broken symlinks it does find are
            safe to remove since the dir is registered as output.
    """
    with TestEnv() as env:
        # User's real library with a mix of real files and a broken symlink
        real_library = os.path.join(env.root, "real-library")
        os.makedirs(real_library)

        real_file = os.path.join(real_library, "precious_movie.mkv")
        with open(real_file, 'wb') as f:
            f.write(b'\x00' * 1024)

        broken_link = os.path.join(real_library, "broken.mkv")
        os.symlink("/nonexistent/deleted.mkv", broken_link)

        # Register the real library as output (the mistake)
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[real_library],
        )

        # Step 1: validate should catch it
        old_stdin = mock_stdin("n\n")
        old_stdout, _ = suppress_stdout()
        try:
            expect_blocked(
                lambda: validate_output_dir(real_library, dry_run=False),
                msg="Should have blocked on real video files"
            )
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        # Step 2: Even if user somehow bypasses validate (says 'y'),
        # clean_broken_symlinks should only remove the broken symlink,
        # not the real file
        old_stdout, _ = suppress_stdout()
        try:
            clean_broken_symlinks(real_library)
        finally:
            sys.stdout = old_stdout

        assert os.path.exists(real_file), (
            "CRITICAL: Real media file was deleted by clean_broken_symlinks!"
        )
        assert not os.path.islink(broken_link), (
            "Broken symlink should have been cleaned"
        )


def test_scenario_source_files_survive_full_clean():
    """Populate a full fake library, create correct output with symlinks,
    then run clean_broken_symlinks. All source files must survive."""
    with TestEnv() as env:
        env.populate_correct_output()

        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )

        # Add a broken symlink to output
        broken = os.path.join(env.movies_linked, "Gone Movie (2020)", "Gone Movie (2020).mkv")
        os.makedirs(os.path.dirname(broken), exist_ok=True)
        os.symlink("/nonexistent/path.mkv", broken)

        old_stdout, _ = suppress_stdout()
        try:
            clean_broken_symlinks(env.movies_linked)
        finally:
            sys.stdout = old_stdout

        # Every source file must still exist
        for dirpath, _, filenames in os.walk(env.movies_source):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                assert os.path.exists(fpath), f"Source file deleted: {fpath}"

        for dirpath, _, filenames in os.walk(env.tv_source):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                assert os.path.exists(fpath), f"Source file deleted: {fpath}"


def test_scenario_write_attempt_to_source_after_config_swap():
    """Simulate: user changes config between runs so a path that was
    previously an output is now a source. All writes should be blocked."""
    with TestEnv() as env:
        env.populate_source_library()

        # "New" config where movies_source is (correctly) protected
        init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_linked],
        )

        # Try every write operation against the source
        test_file = os.path.join(env.movies_source, "Dune.2021.1080p.BluRay",
                                 "Dune.2021.1080p.BluRay.mkv")

        expect_blocked(lambda: safe_remove(test_file))
        assert os.path.exists(test_file), "Source file was removed!"

        expect_blocked(lambda: safe_makedirs(
            os.path.join(env.movies_source, "new_dir")))

        expect_blocked(lambda: safe_symlink(
            "/some/target",
            os.path.join(env.movies_source, "new_link.mkv")))

        expect_blocked(lambda: safe_rmdir(env.movies_source))

        expect_blocked(lambda: clean_broken_symlinks(env.movies_source))

        expect_blocked(lambda: ensure_dir(
            os.path.join(env.tv_source, "new_show"), dry_run=False))


def test_scenario_tv_linked_equals_tv_source():
    """User sets TV_LINKED to the same path as TV_SOURCE."""
    with TestEnv() as env:
        env.populate_source_library()

        expect_blocked(lambda: init_path_guard(
            sources=[env.movies_source, env.tv_source],
            outputs=[env.movies_linked, env.tv_source],  # tv output == tv source
        ))


def test_scenario_validate_catches_populated_tv_source_as_output():
    """User accidentally swaps tv-linked and tv source paths.
    PathGuard won't catch it (tv source is registered as output, not source).
    validate_output_dir should catch the real video files."""
    with TestEnv() as env:
        env.populate_source_library()

        # Incorrect config: tv_source registered as output, tv_linked as source
        # (user swapped the paths)
        init_path_guard(
            sources=[env.movies_source, env.tv_linked],  # wrong
            outputs=[env.movies_linked, env.tv_source],   # wrong -- real files here
        )

        old_stdin = mock_stdin("n\n")
        old_stdout, captured = suppress_stdout()
        try:
            expect_blocked(
                lambda: validate_output_dir(env.tv_source, dry_run=False),
                msg="Should catch real video files in tv_source used as output"
            )
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        output = captured.getvalue()
        assert "WARNING" in output
        assert "real video file" in output.lower()


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nPathGuard test suite")
    print("=" * 60)

    print("\nUnit tests (path logic):")
    test("Source path blocked", test_basic_source_blocked)
    test("Output path allowed", test_basic_output_allowed)
    test("Nested source path blocked", test_nested_source_blocked)
    test("Source dir itself blocked", test_source_dir_itself_blocked)
    test("Output dir itself allowed", test_output_dir_itself_allowed)
    test("Unregistered path blocked", test_unregistered_path_blocked)
    test("Similar prefix not blocked (movies vs movies-linked)", test_similar_prefix_not_blocked)
    test("Multiple sources and outputs", test_multiple_sources)
    test("Output inside source rejected at lock", test_output_inside_source_rejected)
    test("Lock prevents further registration", test_lock_prevents_registration)
    test("Unlocked guard rejects writes", test_unlocked_guard_rejects_writes)
    test("Duplicate registration harmless", test_duplicate_registration_harmless)
    test("Trailing slashes handled", test_guard_with_trailing_slashes)

    print("\nGuarded function integration tests:")
    test("safe_remove blocks source", test_safe_remove_blocks_source)
    test("safe_remove allows output", test_safe_remove_allows_output)
    test("safe_makedirs blocks source", test_safe_makedirs_blocks_source)
    test("safe_symlink blocks source", test_safe_symlink_blocks_source)
    test("safe_symlink allows output", test_safe_symlink_allows_output)
    test("ensure_dir blocks source", test_ensure_dir_blocks_source)
    test("clean_broken_symlinks blocks source", test_clean_broken_symlinks_blocks_source)
    test("clean_broken_symlinks works on output", test_clean_broken_symlinks_works_on_output)
    test("safe_rmdir blocks source", test_safe_rmdir_blocks_source)
    test("make_symlink blocks source", test_make_symlink_blocks_source)

    print("\nOutput directory validation tests:")
    test("Empty output dir passes", test_validate_empty_dir_passes)
    test("Nonexistent output dir passes", test_validate_nonexistent_dir_passes)
    test("Symlinks-only output dir passes", test_validate_symlinks_only_passes)
    test("Real video file warns in dry-run", test_validate_real_video_warns_dryrun)
    test("Real video file blocks on 'n'", test_validate_real_video_blocks_on_no)
    test("Real video file blocks on empty (default N)", test_validate_real_video_blocks_on_empty)
    test("Real video file continues on 'y'", test_validate_real_video_continues_on_yes)
    test("Nested real video file detected", test_validate_nested_real_video_detected)
    test("Non-video files ignored", test_validate_non_video_files_ignored)

    print("\nConfig mistake scenarios:")
    test("Output == source (same path)", test_scenario_output_equals_source_same_path)
    test("Output == source via init_path_guard()", test_scenario_output_equals_source_via_init)
    test("Output is subdirectory of source", test_scenario_output_is_source_subdir)
    test("Output points at real media library", test_scenario_output_points_at_real_library)
    test("--clean on misconfigured real library", test_scenario_clean_on_real_library_blocked)
    test("Source files survive full clean cycle", test_scenario_source_files_survive_full_clean)
    test("All writes blocked after config swap", test_scenario_write_attempt_to_source_after_config_swap)
    test("TV_LINKED == TV_SOURCE blocked", test_scenario_tv_linked_equals_tv_source)
    test("Swapped paths caught by validate", test_scenario_validate_catches_populated_tv_source_as_output)

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)
