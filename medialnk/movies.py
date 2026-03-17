"""
movies.py [v1.0.1]

Movies scanning, categorization, and symlink creation.
Reads from movies_source, writes to movies_linked.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .common import (
    RE_PART, is_video, is_sample, is_episode_file, extract_quality,
    sanitize, make_symlink, ensure_dir, find_videos, largest_video,
    prompt_choice,
)
from .resolver import tmdb_search_movie

# Movies-specific regex
RE_YEAR = re.compile(r'(?<=[.\s\[\(])((?:19|20)\d{2})(?=[.\s\]\)]|$)')
RE_STRIP = re.compile(
    r'[. \(](?:'
    r'(?:19|20)\d{2}|'
    r'2160p|1080p|720p|576p|480p|'
    r'REPACK\d*|BluRay|BDRip|Blu-ray|'
    r'WEB-DL|WEBRip|AMZN|NF|HMAX|PMTP|HDTV|DVDRip|DVDrip|UHD|VHS|'
    r'HDR\d*|DV|DDP[\d.]*|DD[\+\d.]*|DTS|FLAC[\d.]*|AAC[\d.]*|AC3|Opus|'
    r'x264|x265|H\.264|H\.265|h264|h265|AVC|HEVC|'
    r'REMASTERED|EXTENDED|UNRATED|LIMITED|DOCU|CRITERION|PROPER|Uncut|'
    r'(?-i:[A-Z]{2,}-[A-Z][A-Za-z0-9]+))'
    r'.*$',
    re.IGNORECASE,
)


def _normalize(name):
    """Treat underscores as word separators before any parsing.

    Some filenames (especially older scene releases and VHS rips) use
    underscores as separators instead of dots or spaces. Without this,
    RE_YEAR lookbehind misses years in _1995_ and RE_STRIP never fires
    because it requires a dot or space prefix.
    """
    return name.replace('_', '.')


def _year(name):
    m = RE_YEAR.search(_normalize(name))
    return m.group(1) if m else None


def _title(name):
    name = os.path.splitext(_normalize(name))[0]
    s = RE_STRIP.sub('', name)
    if ' ' not in s:
        s = s.replace('.', ' ')
    s = re.sub(r'^\d{4}[\s.]\d{2}[\s.]\d{2}[\s.]+', '', s)
    s = re.sub(r'[\[\(][^\[\(]*$', '', s)
    return s.strip(' .-_[]()').strip()


def _is_miniseries(folder):
    count = 0
    with os.scandir(folder) as it:
        for e in it:
            if e.is_file() and is_video(e.name) and is_episode_file(e.name):
                count += 1
            if count >= 2:
                return True
    return False


def _is_ambiguous_parts(folder):
    parts = []
    with os.scandir(folder) as it:
        for e in it:
            if (e.is_file() and is_video(e.name) and not is_sample(e.name)
                    and not is_episode_file(e.name, include_part=False)
                    and RE_PART.search(e.name)):
                parts.append(e.name)
    parts.sort()
    return len(parts) >= 2, parts


def scan(cfg):
    """Categorize movies_source entries. Returns (movies, flagged, skipped, ambiguous)."""
    seen = {}
    flagged, skipped, ambiguous = [], [], []

    with os.scandir(cfg.movies_source) as it:
        entries = sorted(it, key=lambda e: e.name)

    for entry in entries:
        if entry.is_file():
            if not is_video(entry.name) or is_sample(entry.name):
                continue
            if is_episode_file(entry.name):
                skipped.append(entry.name)
                continue
            year, title = _year(entry.name), _title(entry.name)
            quality, video_path = extract_quality(entry.name), entry.path
        elif entry.is_dir():
            is_parts, part_files = _is_ambiguous_parts(entry.path)
            if is_parts:
                ambiguous.append((entry.name, part_files))
                continue
            if _is_miniseries(entry.path):
                skipped.append(entry.name)
                continue
            vids = find_videos(entry.path)
            if not vids:
                flagged.append((entry.name, "no video file"))
                continue
            primary = largest_video(vids)
            video_path = primary.path
            year = _year(entry.name) or _year(primary.name)
            title = _title(entry.name)
            quality = extract_quality(entry.name) or extract_quality(primary.name)
        else:
            continue

        if not title:
            flagged.append((entry.name, "no title parsed"))
            continue
        if not year:
            flagged.append((entry.name, "no year found"))
            continue

        key = f"{title} ({year})"
        seen.setdefault(key, []).append((entry.name, title, year, video_path, quality))

    return _resolve_versions(seen), flagged, skipped, ambiguous


def _resolve_versions(seen):
    movies = []
    for _, versions in seen.items():
        if len(versions) == 1:
            e, t, y, vp, _ = versions[0]
            movies.append((e, t, y, vp, None))
            continue
        resolved = []
        for e, t, y, vp, q in versions:
            resolved.append((e, t, y, vp, q or extract_quality(os.path.basename(vp)) or "UNKNOWN"))
        qcount = {}
        for _, _, _, _, q in resolved:
            qcount[q] = qcount.get(q, 0) + 1
        qseen = {}
        for e, t, y, vp, q in resolved:
            if qcount[q] == 1:
                label = q
            else:
                qseen[q] = qseen.get(q, 0) + 1
                label = q if qseen[q] == 1 else f"{q}.{qseen[q]}"
            movies.append((e, t, y, vp, label))
    movies.sort(key=lambda x: (x[1].lower(), x[2]))
    return movies


def run(cfg, dry_run=False, auto=False, log=None):
    """Full movies pipeline. Returns counts dict."""
    ensure_dir(cfg.movies_linked, dry_run)
    movies_list, flagged, skipped, ambiguous = scan(cfg)

    linked = 0
    for entry, title, year, video_path, quality in movies_list:
        folder = f"{title} ({year})"
        ext = os.path.splitext(video_path)[1]
        link_name = f"{folder} - {quality}{ext}" if quality else f"{folder}{ext}"
        link_dir = os.path.join(cfg.movies_linked, folder)
        link_path = os.path.join(link_dir, link_name)
        log.verbose(f"  {folder}{f'  [{quality}]' if quality else ''}")
        ensure_dir(link_dir, dry_run)
        if make_symlink(link_path, video_path, dry_run, cfg.host_root, cfg.container_root):
            linked += 1

    # Flagged
    no_year = [(e, r) for e, r in flagged if r == "no year found"]
    for e, r in flagged:
        log.verbose(f"  [FLAG] {e}: {r}")

    # Skipped miniseries
    for e in skipped:
        log.debug(f"  [SKIP] {e}")

    # Ambiguous Part.N
    if ambiguous:
        log.normal(f"  [AMBIGUOUS] {len(ambiguous)} Part.N folders")
        if not dry_run:
            for entry, parts in ambiguous:
                t, y = _title(entry), _year(entry)
                label = f"{t} ({y})" if y else t
                if auto:
                    log.verbose(f"    [AUTO] {label} -> movie")
                    _route_movie(entry, t, y, cfg, dry_run, log)
                else:
                    log.normal(f"    {label} ({len(parts)} parts)")
                    print("    [1] Movie  [2] TV (skip)  [s] Skip")
                    c = prompt_choice("    Choice: ", ("1", "2", "s"))
                    if c == "1":
                        _route_movie(entry, t, y, cfg, dry_run, log)

    # TMDB for yearless
    tmdb_count = 0
    if no_year and cfg.tmdb_api_key and (auto or not dry_run):
        tmdb_count = _tmdb_resolve(no_year, cfg, dry_run, log)

    log.normal(
        f"[MOVIES] {len(movies_list)} entries: {linked} linked, "
        f"{len(flagged)} flagged, {len(skipped)} skipped, "
        f"{len(ambiguous)} ambiguous, {tmdb_count} TMDB resolved"
    )
    return {"total": len(movies_list), "linked": linked, "flagged": len(flagged),
            "skipped": len(skipped), "ambiguous": len(ambiguous)}


def _route_movie(entry, title, year, cfg, dry_run, log):
    folder = os.path.join(cfg.movies_source, entry)
    vids = find_videos(folder, exclude_episodes=False)
    if not vids:
        log.normal(f"    [FAIL] No video files in {entry}")
        return
    primary = largest_video(vids)
    y = year or _year(primary.name)
    t = title or _title(primary.name)
    q = extract_quality(entry) or extract_quality(primary.name)
    if not y:
        log.normal(f"    [WARN] No year for {t}")
        return
    folder_name = f"{t} ({y})"
    ext = os.path.splitext(primary.path)[1]
    link_name = f"{folder_name} - {q}{ext}" if q else f"{folder_name}{ext}"
    link_dir = os.path.join(cfg.movies_linked, folder_name)
    ensure_dir(link_dir, dry_run)
    make_symlink(os.path.join(link_dir, link_name), primary.path, dry_run,
                 cfg.host_root, cfg.container_root)


def _tmdb_resolve(no_year, cfg, dry_run, log):
    log.normal(f"  [TMDB] Resolving {len(no_year)} yearless entries...")
    count = 0
    def _lookup(entry):
        t = _title(entry)
        if not t or len(t) < 4:
            return entry, None, None
        r = tmdb_search_movie(t, cfg.tmdb_api_key, cfg.tmdb_confidence, log)
        if not r:
            return entry, None, None
        return entry, r[0], r[1]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_lookup, e): e for e, _ in no_year}
        for f in as_completed(futs):
            entry, found, year = f.result()
            if not found:
                log.verbose(f"    [MISS] {entry}")
                continue
            ep = os.path.join(cfg.movies_source, entry)
            vp = ep if os.path.isfile(ep) else (
                largest_video(find_videos(ep)).path if find_videos(ep) else None)
            if not vp:
                continue
            folder = f"{found} ({year})" if year else found
            ext = os.path.splitext(vp)[1]
            link_dir = os.path.join(cfg.movies_linked, folder)
            ensure_dir(link_dir, dry_run)
            if make_symlink(os.path.join(link_dir, f"{folder}{ext}"), vp, dry_run,
                            cfg.host_root, cfg.container_root):
                count += 1
    return count