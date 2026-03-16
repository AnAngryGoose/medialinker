"""
resolver.py

TMDB lookups with caching and word-overlap confidence checking.
Unified for movies and TV. Imports only from common.
"""

import json
import urllib.request
import urllib.parse

from .common import sanitize

_cache = {}


def _word_overlap(parsed, result):
    """Word-set confidence check. Short names (1-2 words): all must match
    and result can have at most 1 extra word. Longer: >= 50% overlap."""
    pw = set(parsed.lower().split())
    rw = set(result.lower().split())
    if not pw:
        return False
    overlap = pw & rw
    if len(pw) <= 2:
        return len(overlap) == len(pw) and len(rw) <= len(pw) + 1
    return len(overlap) >= len(pw) / 2


def tmdb_search_tv(name, api_key, confidence=True, log=None):
    """Search TMDB TV. Returns canonical title string or None. Cached."""
    key = f"tv:{name}"
    if key in _cache:
        return _cache[key]
    if not api_key or len(name) < 3:
        _cache[key] = None
        return None
    params = urllib.parse.urlencode({"query": name, "api_key": api_key})
    url = f"https://api.themoviedb.org/3/search/tv?{params}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            _cache[key] = None
            return None
        title = sanitize(results[0].get("name", name))
        if confidence and not _word_overlap(name, title):
            if log:
                log.verbose(f"    [TMDB] Rejected: '{name}' -> '{title}' (low confidence)")
            _cache[key] = None
            return None
        _cache[key] = title
        return title
    except Exception:
        _cache[key] = None
        return None


def tmdb_search_movie(title, api_key, confidence=True, log=None):
    """Search TMDB movie. Returns (title, year) or None. Cached."""
    key = f"movie:{title}"
    if key in _cache:
        return _cache[key]
    if not api_key or len(title) < 4:
        _cache[key] = None
        return None
    params = urllib.parse.urlencode({"query": title, "api_key": api_key})
    url = f"https://api.themoviedb.org/3/search/movie?{params}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            _cache[key] = None
            return None
        top = results[0]
        found = sanitize(top.get("title", title))
        year = top.get("release_date", "")[:4] or None
        if confidence and not _word_overlap(title, found):
            if log:
                log.verbose(f"    [TMDB] Rejected: '{title}' -> '{found}' (low confidence)")
            _cache[key] = None
            return None
        result = (found, year)
        _cache[key] = result
        return result
    except Exception:
        _cache[key] = None
        return None


def resolve_tv_name(parsed, overrides, api_key, confidence=True, log=None):
    """Override -> TMDB -> parsed fallback."""
    if parsed in overrides:
        return overrides[parsed]
    canonical = tmdb_search_tv(parsed, api_key, confidence, log)
    return canonical if canonical else parsed


def clear_cache():
    _cache.clear()
