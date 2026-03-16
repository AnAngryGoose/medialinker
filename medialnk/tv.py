"""
tv.py

TV scanning, bare file handling, conflict resolution, linking.
Reads from tv_source and movies_source, writes to tv_linked.
"""

import os
import re

from .common import (
    RE_SXXEXX, RE_BARE_EPISODE, RE_PART, RE_MULTI_EP,
    RE_XNOTATION, RE_EPISODE, RE_NOF,
    is_video, is_sample, episode_info, extract_quality, sanitize,
    make_symlink, ensure_dir, clean_passthrough_name,
    safe_remove, safe_makedirs, safe_symlink, prompt_choice,
)
from .resolver import resolve_tv_name

# TV-specific regex
SEASON_RE = re.compile(r'^(.+?)[. ]([Ss])(\d{2})([Ee]\d+.*|[. ].*)$')
RE_STRIP = re.compile(
    r'[. ]([Ss]\d{2}([Ee]\d{2})?|'
    r'\d{4}|'
    r'2160p|1080p|720p|576p|480p|'
    r'REPACK\d*|BluRay|BDRip|Blu-ray|'
    r'WEB-DL|WEBRip|AMZN|NF|HMAX|PMTP|HDTV|DVDRip|DVDrip|UHD|NTSC|PAL|'
    r'HDR\d*|DV|DDP[\d.]*|DD[\+\d.]*|DTS|FLAC[\d.]*|AAC[\d.]*|AC3|Opus|'
    r'x264|x265|H\.264|H\.265|h264|h265|AVC|HEVC|'
    r'REMASTERED|EXTENDED|UNRATED|LIMITED|DOCU|CRITERION|'
    r'[A-Z0-9]+-[A-Z][A-Za-z0-9]+)'
    r'.*$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _show_season(folder, overrides):
    """Parse 'Show.Name.S01.720p...' -> (show, season_num) or (None, None)."""
    m = SEASON_RE.match(folder)
    if not m:
        return None, None
    raw = m.group(1)
    snum = int(m.group(3))
    show = raw.replace('.', ' ').strip() if ' ' not in raw else raw.strip()
    show = re.sub(r'\s+\d{4}$', '', show)
    show = sanitize(overrides.get(show, show))
    return show, snum


def _clean_show(folder):
    name = folder
    if ' ' not in name:
        name = name.replace('.', ' ')
    name = RE_STRIP.sub('', name)
    return sanitize(name.strip(' .-_'))


def _is_bare_ep_folder(folder):
    count = 0
    with os.scandir(folder) as it:
        for e in it:
            if e.is_file() and is_video(e.name) and RE_BARE_EPISODE.search(e.name):
                count += 1
            elif e.is_dir() and RE_BARE_EPISODE.search(e.name):
                count += 1
            if count >= 2:
                return True
    return False


def parse_bare_episode(filename):
    """Returns (show, season, episode, quality, second_ep) or None.
    Handles SxxExx+multi-ep, NxNN, Episode.N."""
    name = os.path.splitext(filename)[0]

    m = RE_SXXEXX.search(name)
    if m:
        sn, en = int(m.group(1)), int(m.group(2))
        raw = name[:m.start()].strip(' .-_')
        show = raw.replace('.', ' ').strip() if ' ' not in raw else raw.strip()
        show = re.sub(r'\s+\d{4}$', '', show).strip()
        second = None
        mc = RE_MULTI_EP.match(name[m.end():])
        if mc:
            second = int(mc.group(1))
        return show, sn, en, extract_quality(name), second

    m = RE_XNOTATION.search(name)
    if m:
        parts = re.split(r'x', m.group(0), flags=re.IGNORECASE)
        sn, en = int(parts[0]), int(parts[1])
        raw = name[:m.start()].strip(' .-_')
        show = raw.replace('.', ' ').strip() if ' ' not in raw else raw.strip()
        show = re.sub(r'\s+\d{4}$', '', show).strip()
        return show, sn, en, extract_quality(name), None

    m = RE_EPISODE.search(name)
    if m:
        en = int(m.group(1))
        raw = name[:m.start()].strip(' .-_')
        show = raw.replace('.', ' ').strip() if ' ' not in raw else raw.strip()
        show = re.sub(r'\s+\d{4}$', '', show).strip()
        return show, 1, en, extract_quality(name), None

    return None


def build_link_name(show, season, ep, quality, ext, second_ep=None):
    """Standardized filename: Show.S01E05 - 1080P.mkv or S01E05-E06."""
    tag = f"S{season:02d}E{ep:02d}"
    if second_ep is not None:
        tag += f"-E{second_ep:02d}"
    q = f" - {quality.upper()}" if quality else ""
    return f"{show}.{tag}{q}{ext}"


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

def _norm_key(name):
    name = name.lower()
    name = re.sub(r"['\u2019`]", '', name)
    return re.sub(r'\s+', ' ', name).strip()


def _norm_match(name):
    name = name.lower()
    name = re.sub(r"['\u2019`]s?\b", '', name)
    name = re.sub(r'^(the|a|an)\s+', '', name)
    name = re.sub(r"^(marvels?|dcs?|disneys?|nbc|bbc)\s+", '', name)
    name = re.sub(r'\s+\d{4}$', '', name)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()


def _find_match(show, grouped, tv_linked):
    key = _norm_match(show)
    for g in grouped:
        if _norm_match(g) == key:
            return g
    if os.path.isdir(tv_linked):
        try:
            with os.scandir(tv_linked) as it:
                for e in it:
                    if e.is_dir() and _norm_match(e.name) == key:
                        return e.name
        except (PermissionError, FileNotFoundError):
            pass
    return None


# ---------------------------------------------------------------------------
# Episode state helpers
# ---------------------------------------------------------------------------

def _ep_in_folder(folder, ep, season):
    pat = re.compile(rf'[Ss]{season:02d}[Ee]{ep:02d}', re.IGNORECASE)
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_file() and is_video(e.name) and pat.search(e.name):
                    return True, extract_quality(e.name)
    except (PermissionError, FileNotFoundError):
        pass
    return False, None


def _ep_symlink_exists(season_dir, ep, season):
    pat = re.compile(rf'[Ss]{season:02d}[Ee]{ep:02d}', re.IGNORECASE)
    try:
        with os.scandir(season_dir) as it:
            for e in it:
                if os.path.islink(e.path) and pat.search(e.name):
                    return True
    except (PermissionError, FileNotFoundError):
        pass
    return False


def _convert_season(show, snum, path, cfg, dry_run, log):
    """Replace season symlink with real dir, re-link episodes.
    Quality inherited from folder name for files without their own tag."""
    try:
        ct = os.readlink(path)
        src = ct.replace(cfg.container_root, cfg.host_root, 1)
    except OSError as e:
        log.normal(f"    [ERROR] readlink: {e}")
        return False
    if not os.path.isdir(src):
        log.normal(f"    [ERROR] target missing: {src}")
        return False

    folder_q = extract_quality(os.path.basename(src))
    try:
        with os.scandir(src) as it:
            files = sorted(
                [e for e in it if e.is_file() and is_video(e.name) and not is_sample(e.name)],
                key=lambda e: e.name)
    except (PermissionError, FileNotFoundError) as e:
        log.normal(f"    [ERROR] scan: {e}")
        return False

    log.verbose(f"    Converting Season {snum:02d} -> real dir ({len(files)} episodes)")
    if not dry_run:
        safe_remove(path)
        safe_makedirs(path, exist_ok=True)

    for f in files:
        ep = parse_bare_episode(f.name)
        if ep:
            _, s, e, q, second = ep
            q = q or folder_q
            ln = build_link_name(show, s, e, q, os.path.splitext(f.name)[1], second)
        else:
            ln = f.name
        lp = os.path.join(path, ln)
        log.debug(f"      [LINK] {ln}")
        if not dry_run and not os.path.exists(lp) and not os.path.islink(lp):
            safe_symlink(f.path.replace(cfg.host_root, cfg.container_root, 1), lp)
    return True


# ---------------------------------------------------------------------------
# Pass 1 scanners
# ---------------------------------------------------------------------------

def _scan_tv(cfg):
    grouped, name_map, pt = {}, {}, []
    def canon(show):
        k = _norm_key(show)
        if k not in name_map:
            name_map[k] = show
        return name_map[k]

    with os.scandir(cfg.tv_source) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        nm = entry.name
        if nm in cfg.tv_orphan_overrides:
            show, snum = cfg.tv_orphan_overrides[nm]
            grouped.setdefault(canon(show), []).append((snum, nm))
            continue
        if not entry.is_dir():
            continue
        show, snum = _show_season(nm, cfg.tv_name_overrides)
        if show:
            grouped.setdefault(canon(show), []).append((snum, nm))
        elif _is_bare_ep_folder(entry.path):
            show = _clean_show(nm)
            show = sanitize(cfg.tv_name_overrides.get(show, show))
            grouped.setdefault(canon(show), []).append((1, nm))
        else:
            pt.append(nm)
    return grouped, pt


def _scan_miniseries(cfg):
    results = {}
    with os.scandir(cfg.movies_source) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        if not entry.is_dir():
            continue
        eps = []
        with os.scandir(entry.path) as it2:
            for f in sorted(it2, key=lambda e: e.name):
                if not f.is_file() or not is_video(f.name) or is_sample(f.name):
                    continue
                info = episode_info(f.name, include_part=False)
                if info:
                    eps.append((info[0], info[1], f.name))
        if len(eps) >= 2:
            results[_clean_show(entry.name)] = (entry.name, sorted(eps))
    return results


# ---------------------------------------------------------------------------
# Duplicate season resolution
# ---------------------------------------------------------------------------

def _resolve_dupes(show, seasons, dry_run, auto, log):
    by_s = {}
    for sn, folder in seasons:
        by_s.setdefault(sn, []).append(folder)
    resolved = []
    for sn in sorted(by_s):
        folders = by_s[sn]
        if len(folders) == 1:
            resolved.append((sn, folders[0]))
            continue
        log.normal(f"    [DUPLICATE] {show} S{sn:02d}: {len(folders)} sources")
        for i, f in enumerate(folders, 1):
            q = extract_quality(f) or "unknown"
            log.normal(f"      [{i}] {f}  ({q})")
        if dry_run or auto:
            log.normal(f"      ({'dry-run' if dry_run else 'auto'}: first)")
            resolved.append((sn, folders[0]))
        else:
            while True:
                c = input(f"      Choose [1-{len(folders)}]: ").strip()
                if c.isdigit() and 1 <= int(c) <= len(folders):
                    resolved.append((sn, folders[int(c) - 1]))
                    break
    return resolved


# ---------------------------------------------------------------------------
# Pass 2: bare files
# ---------------------------------------------------------------------------

def _scan_bare(grouped, cfg, log):
    new, conflicts, unmatched = [], [], []
    with os.scandir(cfg.tv_source) as it:
        entries = sorted(it, key=lambda e: e.name)

    for entry in entries:
        if not entry.is_file() or not is_video(entry.name) or is_sample(entry.name):
            continue
        r = parse_bare_episode(entry.name)
        if not r:
            unmatched.append(entry.name)
            continue

        raw_show, sn, en, q, second = r
        show = sanitize(resolve_tv_name(
            raw_show, cfg.tv_name_overrides, cfg.tmdb_api_key, cfg.tmdb_confidence, log))
        matched = _find_match(show, grouped, cfg.tv_linked)
        if matched and matched != show:
            show = matched

        sp = os.path.join(cfg.tv_linked, show, f"Season {sn:02d}")
        canon = matched if matched in grouped else None

        if canon is None:
            if os.path.isdir(sp) and not os.path.islink(sp):
                if _ep_symlink_exists(sp, en, sn):
                    continue
                conflicts.append((show, sn, en, q, entry.path, 'bare_dir', sp, second))
            else:
                new.append((show, sn, en, q, entry.path, second))
        else:
            sfolder = next((sf for s, sf in grouped[canon] if s == sn), None)
            if sfolder is None:
                new.append((show, sn, en, q, entry.path, second))
                continue
            src_path = os.path.join(cfg.tv_source, sfolder)
            exists, eq = _ep_in_folder(src_path, en, sn)
            if exists:
                if eq and q and eq.upper() != q.upper():
                    if os.path.isdir(sp) and not os.path.islink(sp):
                        exp = build_link_name(show, sn, en, q, os.path.splitext(entry.name)[1], second)
                        if os.path.islink(os.path.join(sp, exp)):
                            continue
                        conflicts.append((show, sn, en, q, entry.path, 'bare_dir', sp, second))
                    else:
                        conflicts.append((show, sn, en, q, entry.path, 'quality',
                                          {'folder': sfolder, 'quality': eq}, second))
            else:
                if os.path.isdir(sp) and not os.path.islink(sp):
                    if _ep_symlink_exists(sp, en, sn):
                        continue
                    conflicts.append((show, sn, en, q, entry.path, 'bare_dir', sp, second))
                else:
                    conflicts.append((show, sn, en, q, entry.path, 'missing',
                                      {'folder': sfolder}, second))

    return new, conflicts, unmatched


def _handle_new(new, cfg, dry_run, log):
    if not new:
        return 0
    by_show = {}
    for show, sn, en, q, fp, second in new:
        by_show.setdefault((show, sn), []).append((en, q, fp, second))
    count = 0
    for (show, sn), eps in sorted(by_show.items()):
        sl = f"Season {sn:02d}"
        sd = os.path.join(cfg.tv_linked, show, sl)
        log.verbose(f"  {show} / {sl}  ({len(eps)} ep(s))")
        ensure_dir(os.path.join(cfg.tv_linked, show), dry_run)
        ensure_dir(sd, dry_run)
        for en, q, fp, second in sorted(eps):
            ext = os.path.splitext(fp)[1]
            ln = build_link_name(show, sn, en, q, ext, second)
            lp = os.path.join(sd, ln)
            if os.path.islink(lp):
                continue
            if make_symlink(lp, fp, dry_run, cfg.host_root, cfg.container_root):
                log.verbose(f"    [LINK] {ln}")
                count += 1
    return count


def _handle_conflicts(conflicts, cfg, dry_run, auto, log):
    if not conflicts:
        return 0
    if dry_run:
        for show, sn, en, q, fp, ctype, info, second in conflicts:
            ep = f"E{en:02d}" + (f"-E{second:02d}" if second else "")
            log.verbose(f"  {show} S{sn:02d}{ep} [{q or '?'}] ({ctype})")
        log.normal(f"  {len(conflicts)} conflict(s) (use sync without --dry-run)")
        return 0

    resolved = 0
    for show, sn, en, q, fp, ctype, info, second in conflicts:
        sl = f"Season {sn:02d}"
        ext = os.path.splitext(fp)[1]
        ln = build_link_name(show, sn, en, q, ext, second)
        sp = os.path.join(cfg.tv_linked, show, sl)

        if ctype in ('quality', 'missing'):
            # Already converted by earlier conflict this run?
            if os.path.isdir(sp) and not os.path.islink(sp):
                log.verbose(f"  {show} S{sn:02d}E{en:02d}: already converted, adding")
                lp = os.path.join(sp, ln)
                if make_symlink(lp, fp, dry_run, cfg.host_root, cfg.container_root):
                    resolved += 1
                continue
            if not auto:
                log.normal(f"\n  {show} / {sl} / E{en:02d}")
                log.normal(f"    File: {os.path.basename(fp)}")
                if ctype == 'quality':
                    log.normal(f"    Existing: {info['quality']}, this: {q}")
                else:
                    log.normal(f"    Not in folder: {info['folder']}")
                log.normal(f"    Requires converting season symlink to real dir.")
                print("    [1] Convert and add  [s] Skip")
                c = prompt_choice("    Choice: ", ("1", "s"))
                if c == "s":
                    continue
            ok = _convert_season(show, sn, sp, cfg, dry_run, log)
            if ok:
                lp = os.path.join(sp, ln)
                if make_symlink(lp, fp, dry_run, cfg.host_root, cfg.container_root):
                    resolved += 1

        elif ctype == 'bare_dir':
            if auto:
                lp = os.path.join(sp, ln)
                if make_symlink(lp, fp, dry_run, cfg.host_root, cfg.container_root):
                    resolved += 1
            else:
                log.normal(f"\n  {show} / {sl} / E{en:02d} (season dir exists)")
                print("    [1] Add  [s] Skip")
                c = prompt_choice("    Choice: ", ("1", "s"))
                if c == "1":
                    lp = os.path.join(sp, ln)
                    if make_symlink(lp, fp, dry_run, cfg.host_root, cfg.container_root):
                        resolved += 1
    return resolved


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------

def _norm_compare(name):
    name = re.sub(r'\{[^}]+\}', '', name)
    name = re.sub(r'\(\d{4}\)', '', name)
    name = _clean_show(name)
    return name.lower().strip()


def _warnings(grouped, pt):
    w = []
    for show, seasons in grouped.items():
        seen = {}
        for sn, folder in seasons:
            if sn in seen:
                w.append(f"Duplicate season: {show} S{sn:02d} in '{seen[sn]}' and '{folder}'")
            else:
                seen[sn] = folder
    gn = {_norm_compare(n): n for n in grouped}
    for p in pt:
        n = _norm_compare(p)
        if n in gn:
            w.append(f"Name overlap: '{gn[n]}' and pass-through '{p}'")
    return w


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(cfg, dry_run=False, auto=False, log=None):
    ensure_dir(cfg.tv_linked, dry_run)

    grouped, pt = _scan_tv(cfg)
    mini = _scan_miniseries(cfg)

    # Pass 1: season folders
    shows, seasons_linked = 0, 0
    for show, seasons in sorted(grouped.items()):
        ss = sorted(seasons, key=lambda x: x[0])
        ss = _resolve_dupes(show, ss, dry_run, auto, log)
        shows += 1
        show_dir = os.path.join(cfg.tv_linked, show)
        ensure_dir(show_dir, dry_run)
        strs = ", ".join(f"S{s:02d}" for s, _ in ss)
        log.verbose(f"  {show}  ({strs})")
        for sn, folder in ss:
            lp = os.path.join(cfg.tv_linked, show, f"Season {sn:02d}")
            tgt = os.path.join(cfg.tv_source, folder)
            if make_symlink(lp, tgt, dry_run, cfg.host_root, cfg.container_root):
                seasons_linked += 1

    # Pass-through
    pt_count = 0
    for entry in sorted(pt):
        cn = clean_passthrough_name(entry)
        lp = os.path.join(cfg.tv_linked, cn)
        tgt = os.path.join(cfg.tv_source, entry)
        if make_symlink(lp, tgt, dry_run, cfg.host_root, cfg.container_root):
            log.verbose(f"  [PASS] {cn}")
            pt_count += 1

    # Miniseries
    mini_count = 0
    for show, (folder, eps) in sorted(mini.items()):
        log.verbose(f"  [MINI] {show}  ({len(eps)} eps)")
        sn = eps[0][0]
        sd = os.path.join(cfg.tv_linked, show, f"Season {sn:02d}")
        ensure_dir(sd, dry_run)
        for s, en, fn in eps:
            op = os.path.join(cfg.movies_source, folder, fn)
            ext = os.path.splitext(fn)[1]
            ln = fn if RE_SXXEXX.search(fn) else f"{show}.S{s:02d}E{en:02d}{ext}"
            lp = os.path.join(sd, ln)
            if make_symlink(lp, op, dry_run, cfg.host_root, cfg.container_root):
                mini_count += 1

    # Pass 2: bare files
    new, conflicts, unmatched = _scan_bare(grouped, cfg, log)
    new_count = _handle_new(new, cfg, dry_run, log)
    conflict_count = _handle_conflicts(conflicts, cfg, dry_run, auto, log)

    if unmatched:
        log.normal(f"  [UNMATCHED] {len(unmatched)} bare file(s):")
        for fn in unmatched:
            log.verbose(f"    {fn}")

    for w in _warnings(grouped, pt):
        log.normal(f"  [WARN] {w}")

    log.normal(
        f"[TV] {shows} shows ({seasons_linked} seasons), "
        f"{pt_count} pass-through, {mini_count} miniseries, "
        f"{new_count} bare new, {conflict_count} conflicts, "
        f"{len(unmatched)} unmatched"
    )

    return {"shows": shows, "seasons": seasons_linked, "passthrough": pt_count,
            "miniseries": mini_count, "bare_new": new_count,
            "conflicts": conflict_count, "unmatched": len(unmatched)}
