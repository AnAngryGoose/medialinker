"""
common.py

Shared regex patterns, PathGuard immutability system, filesystem helpers.
Foundation layer for the entire package. No TV-specific or movie-specific
parsing logic lives here.
"""

import os
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".ts", ".m4v"}

# ---------------------------------------------------------------------------
# Regex patterns (shared)
# ---------------------------------------------------------------------------

RE_SXXEXX       = re.compile(r'[Ss](\d{1,2})[Ee](\d{2})', re.IGNORECASE)
RE_XNOTATION    = re.compile(r'\d{1,2}x\d{2}', re.IGNORECASE)
RE_EPISODE      = re.compile(r'[Ee]pisode[. _](\d{1,3})', re.IGNORECASE)
RE_NOF          = re.compile(r'[\(]?(\d{1,2})of(\d{1,2})[\)]?', re.IGNORECASE)
RE_BARE_EPISODE = re.compile(r'(?<![Ss\d])E(\d{2,3})\b')
RE_MULTI_EP     = re.compile(r'[-.]?[Ee](\d{2})', re.IGNORECASE)
RE_PART         = re.compile(r'[.\s\-_](?:Part|Pt)[.\s\-_]?(\d{1,2})\b', re.IGNORECASE)
RE_SAMPLE       = re.compile(r'\bsample\b', re.IGNORECASE)
RE_ILLEGAL      = re.compile(r'[/:\\?*"<>|]')
RE_QUALITY      = re.compile(
    r'(2160p|1080p|720p|576p|480p|REMUX|BluRay|BDRip|WEB-DL|WEBRip|HDTV|UHD)',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# PathGuard
# ---------------------------------------------------------------------------

class SourceProtectionError(Exception):
    """Write operation targeted a protected source path. Hard stop."""
    pass


class PathGuard:
    """Enforces that writes stay inside output directories and never
    touch source media paths. Single enforcement point for the core rule:
    source files are never modified, moved, or deleted."""

    def __init__(self):
        self._sources = []
        self._outputs = []
        self._locked = False

    def register_source(self, path):
        if self._locked:
            raise RuntimeError("PathGuard is locked.")
        p = os.path.abspath(path)
        if p not in self._sources:
            self._sources.append(p)

    def register_output(self, path):
        if self._locked:
            raise RuntimeError("PathGuard is locked.")
        p = os.path.abspath(path)
        if p not in self._outputs:
            self._outputs.append(p)

    def lock(self):
        for o in self._outputs:
            for s in self._sources:
                if o == s or o.startswith(s + os.sep):
                    raise SourceProtectionError(
                        f"Output inside source.\n  Out: {o}\n  Src: {s}")
        self._locked = True

    def assert_writable(self, path):
        if not self._locked:
            raise RuntimeError("PathGuard not locked.")
        p = os.path.abspath(path)
        for s in self._sources:
            if p == s or p.startswith(s + os.sep):
                raise SourceProtectionError(
                    f"BLOCKED: write to source.\n  {p}\n  Source: {s}")
        for o in self._outputs:
            if p == o or p.startswith(o + os.sep):
                return
        raise SourceProtectionError(
            f"BLOCKED: write outside registered outputs.\n  {p}")

    @property
    def is_locked(self):
        return self._locked


_guard = PathGuard()


def init_guard(sources, outputs):
    global _guard
    _guard = PathGuard()
    for s in sources:
        _guard.register_source(s)
    for o in outputs:
        _guard.register_output(o)
    _guard.lock()


def get_guard():
    return _guard


# ---------------------------------------------------------------------------
# Guarded filesystem ops (the ONLY write functions in the codebase)
# ---------------------------------------------------------------------------

def safe_remove(path):
    _guard.assert_writable(path)
    os.remove(path)

def safe_rmdir(path):
    _guard.assert_writable(path)
    os.rmdir(path)

def safe_makedirs(path, exist_ok=True):
    _guard.assert_writable(path)
    os.makedirs(path, exist_ok=exist_ok)

def safe_symlink(target, link_path):
    _guard.assert_writable(link_path)
    os.symlink(target, link_path)

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def is_video(filename):
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTS

def is_sample(filename):
    return bool(RE_SAMPLE.search(filename))

def episode_info(filename, include_part=True):
    """(season, episode) or None. include_part=False excludes Part.N."""
    m = RE_SXXEXX.search(filename)
    if m: return int(m.group(1)), int(m.group(2))
    m = RE_XNOTATION.search(filename)
    if m:
        parts = re.split(r'x', m.group(0), flags=re.IGNORECASE)
        return int(parts[0]), int(parts[1])
    m = RE_EPISODE.search(filename)
    if m: return 1, int(m.group(1))
    m = RE_BARE_EPISODE.search(filename)
    if m: return 1, int(m.group(1))
    m = RE_NOF.search(filename)
    if m: return 1, int(m.group(1))
    if include_part:
        m = RE_PART.search(filename)
        if m: return 1, int(m.group(1))
    return None

def is_episode_file(filename, include_part=True):
    return episode_info(filename, include_part=include_part) is not None

def extract_quality(name):
    m = RE_QUALITY.search(name)
    return m.group(1).upper() if m else None

def sanitize(name):
    return RE_ILLEGAL.sub('-', name)

def clean_passthrough_name(folder_name):
    """Safe cosmetic cleanup: dots to spaces (when no spaces exist),
    whitespace normalization. No year/metadata stripping."""
    name = folder_name
    if ' ' not in name:
        name = name.replace('.', ' ')
    return re.sub(r'\s+', ' ', name).strip()

# ---------------------------------------------------------------------------
# Symlink / directory helpers
# ---------------------------------------------------------------------------

def host_to_container(path, host_root, container_root):
    return path.replace(host_root, container_root, 1)

def make_symlink(link_path, target_host_path, dry_run, host_root, container_root):
    """Create absolute container-side symlink. Returns True if created, False if skipped."""
    if os.path.exists(link_path) or os.path.islink(link_path):
        return False
    container_target = host_to_container(target_host_path, host_root, container_root)
    if not dry_run:
        safe_symlink(container_target, link_path)
    return True

def ensure_dir(path, dry_run):
    if not dry_run:
        safe_makedirs(path, exist_ok=True)

def symlink_target_exists(link_path, host_root, container_root):
    if not os.path.islink(link_path):
        return True
    target = os.readlink(link_path)
    if host_root and container_root and target.startswith(container_root):
        target = host_root + target[len(container_root):]
    return os.path.exists(target)

def clean_broken_symlinks(directory, host_root=None, container_root=None):
    """Remove broken symlinks and prune empty dirs. Returns count removed."""
    _guard.assert_writable(directory)
    removed = 0
    for dirpath, _, filenames in os.walk(directory):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            if os.path.islink(fp) and not symlink_target_exists(fp, host_root, container_root):
                safe_remove(fp)
                removed += 1
    for dirpath, dirnames, _ in os.walk(directory):
        for dname in dirnames:
            dp = os.path.join(dirpath, dname)
            if os.path.islink(dp) and not symlink_target_exists(dp, host_root, container_root):
                safe_remove(dp)
                removed += 1
    for dirpath, _, _ in os.walk(directory, topdown=False):
        if dirpath != directory and not os.listdir(dirpath):
            safe_rmdir(dirpath)
    return removed

def validate_output_dir(directory, dry_run=False):
    """Scan output dir for real video files. Returns count.
    Raises SourceProtectionError if user declines."""
    if not os.path.isdir(directory):
        return 0
    real = []
    for dp, _, fns in os.walk(directory):
        for fn in fns:
            fp = os.path.join(dp, fn)
            if is_video(fn) and not os.path.islink(fp):
                real.append(fp)
    if not real:
        return 0
    print(f"\n[WARNING] {len(real)} real video file(s) in output dir:")
    for f in real[:10]:
        print(f"  {f}")
    if len(real) > 10:
        print(f"  ... ({len(real) - 10} more)")
    print("\n  Output dirs should only contain symlinks.")
    print("  If this IS your real library, your config is wrong.")
    if dry_run:
        print("  (dry-run, continuing)\n")
        return len(real)
    print()
    while True:
        c = input("  Continue anyway? [y/N] ").strip().lower()
        if c in ('n', ''):
            raise SourceProtectionError("Aborted by user.")
        if c == 'y':
            return len(real)

def find_videos(folder, exclude_episodes=True, exclude_samples=True):
    vids = []
    with os.scandir(folder) as it:
        for f in it:
            if not f.is_file() or not is_video(f.name):
                continue
            if exclude_samples and is_sample(f.name):
                continue
            if exclude_episodes and is_episode_file(f.name):
                continue
            vids.append(f)
    return vids

def largest_video(videos):
    return max(videos, key=lambda f: f.stat().st_size)

def prompt_choice(message, valid):
    """Loop until user enters a valid choice."""
    while True:
        c = input(message).strip().lower()
        if c in valid:
            return c
        print(f"    Enter one of: {', '.join(valid)}")
