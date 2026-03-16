"""
common.py [v0.25]

Shared utilities for medialn scripts (make_movies_links.py, make_tv_links.py).

Contains regex patterns, filesystem helpers, symlink logic, and the PathGuard
immutability system used by both scripts. Keeps everything in one place so the
two scripts stay in sync.
"""

import os
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".ts", ".m4v"}

# ---------------------------------------------------------------------------
# Regex patterns (shared across both scripts)
# ---------------------------------------------------------------------------

# Episode detection patterns
RE_SXXEXX       = re.compile(r'[Ss](\d{1,2})[Ee](\d{2})', re.IGNORECASE)
RE_XNOTATION    = re.compile(r'\d{1,2}x\d{2}', re.IGNORECASE)
RE_EPISODE      = re.compile(r'[Ee]pisode[. _](\d{1,3})', re.IGNORECASE)
RE_NOF          = re.compile(r'[\(]?(\d{1,2})of(\d{1,2})[\)]?', re.IGNORECASE)
RE_BARE_EPISODE = re.compile(r'(?<![Ss\d])E(\d{2,3})\b')

# Multi-episode continuation after an SxxExx match (e.g. S01E05-E06, S01E05E06)
RE_MULTI_EP = re.compile(r'[-.]?[Ee](\d{2})', re.IGNORECASE)

# Sample file detection - word-boundary match avoids false positives like "example.mkv"
RE_SAMPLE = re.compile(r'\bsample\b', re.IGNORECASE)

# Characters illegal on Windows/network mounts
RE_ILLEGAL_CHARS = re.compile(r'[/:\\?*"<>|]')

# Part.N detection - matches ".Part.1", ".Part1", " Part 2" etc.
# \d{1,2} intentionally excludes 4-digit years (e.g. "Bande a part 1964").
RE_PART = re.compile(r'[.\s\-_](?:Part|Pt)[.\s\-_]?(\d{1,2})\b', re.IGNORECASE)

# Quality tag extraction - used by both scripts for multi-version naming
RE_QUALITY = re.compile(
    r'(2160p|1080p|720p|576p|480p|REMUX|BluRay|BDRip|WEB-DL|WEBRip|HDTV|UHD)',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# PathGuard -- immutability enforcement
# ---------------------------------------------------------------------------

class SourceProtectionError(Exception):
    """Raised when a write operation targets a protected source directory.

    This is a hard stop. If this fires, something went wrong with path
    construction and the script must abort rather than risk modifying
    source media files.
    """
    pass


class PathGuard:
    """Enforces that all filesystem write operations stay inside output
    directories and never touch source media paths.

    Every function in medialn that creates, removes, or modifies anything on
    disk goes through this guard. Source directories are registered as
    protected. Output directories are registered as writable. Any write
    targeting a protected path raises SourceProtectionError immediately.
    Any write targeting a path outside all registered directories also raises,
    preventing accidental writes to random filesystem locations.

    This is the single enforcement point for the project's core rule: source
    media files are never modified, moved, or deleted under any circumstance.

    Usage:
        guard = PathGuard()
        guard.register_source("/mnt/storage/data/media/movies")
        guard.register_source("/mnt/storage/data/media/tv")
        guard.register_output("/mnt/storage/data/media/movies-linked")
        guard.register_output("/mnt/storage/data/media/tv-linked")
        guard.lock()

        guard.assert_writable(some_path)  # raises if path is under source
    """

    def __init__(self):
        self._sources = []   # absolute paths of protected source dirs
        self._outputs = []   # absolute paths of allowed output dirs
        self._locked = False

    def register_source(self, path):
        """Mark a directory as protected. Writes under this path will be
        blocked. Must be called before lock()."""
        if self._locked:
            raise RuntimeError("PathGuard is locked. Cannot register new paths after lock().")
        abspath = os.path.abspath(path)
        if abspath not in self._sources:
            self._sources.append(abspath)

    def register_output(self, path):
        """Mark a directory as writable. Writes are only allowed under
        registered output paths. Must be called before lock()."""
        if self._locked:
            raise RuntimeError("PathGuard is locked. Cannot register new paths after lock().")
        abspath = os.path.abspath(path)
        if abspath not in self._outputs:
            self._outputs.append(abspath)

    def lock(self):
        """Finalize the guard. After this, no new paths can be registered
        and the guard is ready for enforcement.

        Validates that no output directory is inside a source directory,
        which would create an unresolvable conflict.
        """
        for out in self._outputs:
            for src in self._sources:
                if out == src or out.startswith(src + os.sep):
                    raise SourceProtectionError(
                        f"Output directory is inside a source directory. "
                        f"This is not allowed.\n"
                        f"  Output: {out}\n"
                        f"  Source: {src}"
                    )
        self._locked = True

    def assert_writable(self, path):
        """Check that a path is safe to write to. Raises SourceProtectionError
        if the path is under a protected source directory, or if it is not
        under any registered output directory.

        Call this before any os.remove, os.rmdir, os.makedirs, os.symlink,
        or any other operation that modifies the filesystem.
        """
        if not self._locked:
            raise RuntimeError(
                "PathGuard has not been locked. Call lock() after registering "
                "all paths and before any filesystem operations."
            )

        abspath = os.path.abspath(path)

        # Check source protection first. This is the critical safety check.
        for src in self._sources:
            if abspath == src or abspath.startswith(src + os.sep):
                raise SourceProtectionError(
                    f"BLOCKED: Write operation targets a protected source path.\n"
                    f"  Target: {path}\n"
                    f"  Resolved: {abspath}\n"
                    f"  Protected source: {src}\n"
                    f"This would modify original media files. Aborting."
                )

        # Check that the path is under a registered output directory.
        for out in self._outputs:
            if abspath == out or abspath.startswith(out + os.sep):
                return  # Safe -- under a registered output dir

        raise SourceProtectionError(
            f"BLOCKED: Write operation targets a path outside all registered "
            f"output directories.\n"
            f"  Target: {path}\n"
            f"  Resolved: {abspath}\n"
            f"  Registered outputs: {self._outputs}\n"
            f"Refusing to write to an unregistered location."
        )

    @property
    def is_locked(self):
        return self._locked

    def summary(self):
        """Return a human-readable summary of registered paths."""
        lines = ["PathGuard configuration:"]
        lines.append(f"  Locked: {self._locked}")
        lines.append(f"  Protected source paths ({len(self._sources)}):")
        for s in self._sources:
            lines.append(f"    {s}")
        lines.append(f"  Allowed output paths ({len(self._outputs)}):")
        for o in self._outputs:
            lines.append(f"    {o}")
        return "\n".join(lines)


# Module-level guard instance. Initialized by each script's main() before
# any filesystem operations happen.
_guard = PathGuard()


def init_path_guard(sources, outputs):
    """Initialize the module-level PathGuard with source and output paths.

    Must be called exactly once, at the start of main(), before any functions
    that write to the filesystem. After this call the guard is locked and
    enforcing.

    Args:
        sources: list of source directory paths (protected, read-only)
        outputs: list of output directory paths (writable)
    """
    global _guard
    _guard = PathGuard()
    for s in sources:
        _guard.register_source(s)
    for o in outputs:
        _guard.register_output(o)
    _guard.lock()
    print(f"[GUARD] Source protection active. "
          f"{len(sources)} source(s) locked, "
          f"{len(outputs)} output(s) registered.")


def get_path_guard():
    """Return the module-level PathGuard instance for inspection or testing."""
    return _guard


def validate_output_dir(directory, dry_run=False):
    """Check an output directory for real (non-symlink) video files.

    A legitimate medialn output directory should only contain symlinks to
    video files, real directories (from season conversions), and possibly
    files placed by Arr (hardlinked). It should never be the user's actual
    media library.

    If real video files are found, prints a warning listing up to 10 of
    them and prompts the user to confirm before continuing. In dry-run
    mode the warning is printed but no confirmation is required since
    dry-run cannot modify anything.

    Call this right after init_path_guard() and before any writes.
    """
    if not os.path.isdir(directory):
        return  # Directory doesn't exist yet, nothing to check

    real_videos = []
    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if is_video(fname) and not os.path.islink(fpath):
                real_videos.append(fpath)

    if not real_videos:
        return

    print(f"\n[WARNING] {len(real_videos)} real video file(s) found in output directory:")
    show = real_videos[:10]
    for f in show:
        print(f"  {f}")
    if len(real_videos) > 10:
        print(f"  ... ({len(real_videos) - 10} more)")

    print()
    print("  Real media files should not exist in the output directory.")
    print("  medialn output directories should only contain symlinks to")
    print("  your actual media library, not the media files themselves.")
    print()
    print("  If this directory IS your real media library, your config is")
    print("  wrong. Check MEDIA_ROOT_HOST and your LINKED path settings")
    print("  before running again.")

    if dry_run:
        print()
        print("  (dry-run mode -- continuing without confirmation)")
        print()
        return

    print()
    while True:
        choice = input("  Continue anyway? [y/N] ").strip().lower()
        if choice in ('n', ''):
            raise SourceProtectionError(
                "Aborted by user. Fix output directory config and try again."
            )
        if choice == 'y':
            print()
            return
        print("  Enter 'y' to continue or 'n' to abort.")


# ---------------------------------------------------------------------------
# Guarded filesystem operations
#
# These are the ONLY functions in the entire codebase that perform write
# operations on the filesystem. Every write goes through assert_writable()
# before touching disk. No other code in medialn should call os.remove,
# os.rmdir, os.makedirs, or os.symlink directly.
# ---------------------------------------------------------------------------

def safe_remove(path):
    """Remove a file or symlink. Guarded: refuses if path is under a source dir."""
    _guard.assert_writable(path)
    os.remove(path)


def safe_rmdir(path):
    """Remove an empty directory. Guarded: refuses if path is under a source dir."""
    _guard.assert_writable(path)
    os.rmdir(path)


def safe_makedirs(path, exist_ok=True):
    """Create a directory and parents. Guarded: refuses if path is under a source dir."""
    _guard.assert_writable(path)
    os.makedirs(path, exist_ok=exist_ok)


def safe_symlink(target, link_path):
    """Create a symlink at link_path pointing to target.

    Only link_path is guarded (that's where the symlink file gets created).
    target is the string stored inside the symlink and can point anywhere,
    including source directories. This is the whole point of symlinks:
    they reference source files without modifying them.
    """
    _guard.assert_writable(link_path)
    os.symlink(target, link_path)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def is_video(filename):
    """Check if filename has a recognized video extension."""
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTS


def is_sample(filename):
    """Check if filename looks like a sample file."""
    return bool(RE_SAMPLE.search(filename))


def is_episode(filename):
    """Check if filename matches any known episode naming pattern.
    Includes Part.N as a last-resort match. Used for general episode
    detection in both scripts."""
    return (RE_SXXEXX.search(filename) or
            RE_XNOTATION.search(filename) or
            RE_EPISODE.search(filename) or
            RE_NOF.search(filename) or
            RE_BARE_EPISODE.search(filename) or
            RE_PART.search(filename))


def is_episode_strict(filename):
    """Check if filename matches a real episode pattern, excluding Part.N.

    Used by scan_movies_for_miniseries() to avoid false-positiving on
    multi-part films like Kill Bill. Part.N files could be either episodes
    or movie parts, so they get routed to the movies script's ambiguity
    prompt instead of being auto-detected as miniseries.
    """
    return (RE_SXXEXX.search(filename) or
            RE_XNOTATION.search(filename) or
            RE_EPISODE.search(filename) or
            RE_NOF.search(filename) or
            RE_BARE_EPISODE.search(filename))


def extract_quality(name):
    """Extract a short quality label from a name (e.g. '1080P', '720P').
    Returns uppercased label or None if not found."""
    m = RE_QUALITY.search(name)
    return m.group(1).upper() if m else None


def sanitize_filename(name):
    """Replace characters illegal on Windows/network mounts with '-'."""
    return RE_ILLEGAL_CHARS.sub('-', name)


def clean_passthrough_name(folder_name):
    """Safe cosmetic cleanup for pass-through folder names.

    Only does non-destructive transformations:
      - Replaces dots with spaces (when no spaces exist in the name)
      - Normalizes whitespace
      - Strips leading/trailing junk characters

    Does NOT strip years, remove bracketed metadata, change season
    notation, or do any canonical renaming. Those belong in the
    parser/normalization layer, not in generic pass-through cleanup.
    """
    name = folder_name
    # Only dot-to-space if the name has no spaces at all (scene naming)
    if ' ' not in name:
        name = name.replace('.', ' ')
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def host_to_container(path, host_root, container_root):
    """Translate a host-side absolute path to its container-side equivalent."""
    return path.replace(host_root, container_root, 1)


def make_symlink(link_path, target_host_path, dry_run, host_root, container_root):
    """Create an absolute container-side symlink. Skips if link already exists.

    Uses safe_symlink() internally, so the link creation path is validated
    against the PathGuard before any write happens.
    """
    if os.path.exists(link_path) or os.path.islink(link_path):
        print(f"    [SKIP] {os.path.basename(link_path)}")
        return
    container_target = host_to_container(target_host_path, host_root, container_root)
    print(f"    [LINK] {os.path.basename(link_path)}")
    print(f"        -> {container_target}")
    if not dry_run:
        safe_symlink(container_target, link_path)


def ensure_dir(path, dry_run):
    """Create directory (and parents) if not in dry-run mode.

    Uses safe_makedirs() internally, so the path is validated against the
    PathGuard before any write happens.
    """
    if not dry_run:
        safe_makedirs(path, exist_ok=True)


def _symlink_target_exists(link_path, host_root, container_root):
    """Check whether a symlink's target actually exists on disk.

    Symlinks created by medialn use container-side paths (e.g. /data/media/...).
    When the script runs on the host, those paths don't exist at the container
    path - they exist at the translated host path. This function reads the
    symlink target and translates it before checking existence, so container-path
    symlinks are not incorrectly treated as broken.
    """
    if not os.path.islink(link_path):
        return True
    target = os.readlink(link_path)
    if host_root and container_root and target.startswith(container_root):
        target = host_root + target[len(container_root):]
    return os.path.exists(target)


def clean_broken_symlinks(directory, host_root=None, container_root=None):
    """Remove broken file and directory symlinks, then prune empty directories.

    Only operates on the directory passed in, which must be a registered output
    directory. Uses safe_remove() and safe_rmdir() internally, so every
    deletion is validated against the PathGuard.

    host_root and container_root are used to translate symlink targets before
    checking existence. Without these, container-path symlinks (e.g. pointing
    to /data/media/...) would be incorrectly treated as broken when running on
    the host where those paths don't exist directly.
    """
    # Validate the top-level directory before walking it. Catches misuse
    # early rather than failing on the first broken symlink found.
    _guard.assert_writable(directory)

    removed = 0

    # Broken file symlinks
    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if (os.path.islink(fpath) and
                    not _symlink_target_exists(fpath, host_root, container_root)):
                print(f"  [REMOVE] {fpath}")
                safe_remove(fpath)
                removed += 1

    # Broken directory symlinks (e.g. season folder symlinks in tv-linked)
    for dirpath, dirnames, _ in os.walk(directory):
        for dname in dirnames:
            dpath = os.path.join(dirpath, dname)
            if (os.path.islink(dpath) and
                    not _symlink_target_exists(dpath, host_root, container_root)):
                print(f"  [REMOVE] {dpath}")
                safe_remove(dpath)
                removed += 1

    # Remove empty directories left behind
    for dirpath, _, _ in os.walk(directory, topdown=False):
        if dirpath == directory:
            continue
        if not os.listdir(dirpath):
            safe_rmdir(dirpath)

    print(f"  Removed {removed} broken symlink(s).\n")


def find_videos_in_folder(folder_path, exclude_episodes=True, exclude_samples=True):
    """Scan a folder for video files, with optional episode/sample filtering."""
    videos = []
    with os.scandir(folder_path) as it:
        for f in it:
            if not f.is_file() or not is_video(f.name):
                continue
            if exclude_samples and is_sample(f.name):
                continue
            if exclude_episodes and is_episode(f.name):
                continue
            videos.append(f)
    return videos


def largest_video(videos):
    """Return the largest video file from a list of DirEntry objects."""
    return max(videos, key=lambda f: f.stat().st_size)
