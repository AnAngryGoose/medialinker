"""
config.py

TOML config loading, validation, path resolution.
Requires Python 3.11+ for tomllib.
"""

import os
import sys

try:
    import tomllib
except ModuleNotFoundError:
    print("medialnk requires Python 3.11+ (for tomllib).")
    sys.exit(1)


class Config:
    """Resolved configuration for a medialnk run."""

    def __init__(self, raw):
        paths = raw.get("paths", {})
        tmdb = raw.get("tmdb", {})
        log_cfg = raw.get("logging", {})
        overrides = raw.get("overrides", {})

        self.host_root = paths.get("media_root_host", "")
        self.container_root = paths.get("media_root_container", "") or self.host_root

        if not self.host_root:
            raise ValueError("paths.media_root_host is required.")

        def _resolve(key, default):
            val = paths.get(key, default)
            if not os.path.isabs(val):
                return os.path.join(self.host_root, val)
            return val

        self.movies_source = _resolve("movies_source", "movies")
        self.tv_source = _resolve("tv_source", "tv")
        self.movies_linked = _resolve("movies_linked", "movies-linked")
        self.tv_linked = _resolve("tv_linked", "tv-linked")

        self.tmdb_api_key = os.environ.get("TMDB_API_KEY", "") or tmdb.get("api_key", "")
        self.tmdb_confidence = tmdb.get("confidence_check", True)

        log_dir = log_cfg.get("log_dir", "logs")
        self.log_dir = log_dir if os.path.isabs(log_dir) else os.path.join(self.host_root, log_dir)
        self.verbosity = log_cfg.get("verbosity", "normal")

        self.tv_name_overrides = overrides.get("tv_names", {})
        self.tv_orphan_overrides = {}
        for k, v in overrides.get("tv_orphans", {}).items():
            if isinstance(v, dict):
                self.tv_orphan_overrides[k] = (v["show"], v["season"])
            elif isinstance(v, list) and len(v) == 2:
                self.tv_orphan_overrides[k] = (v[0], v[1])
        self.movie_title_overrides = overrides.get("movie_titles", {})

        self.source_dirs = [self.movies_source, self.tv_source]
        self.output_dirs = [self.movies_linked, self.tv_linked]

    def validate(self):
        errors = []
        if not os.path.isdir(self.host_root):
            errors.append(f"media_root_host not found: {self.host_root}")
        for name, path in [("movies_source", self.movies_source),
                           ("tv_source", self.tv_source)]:
            if not os.path.isdir(path):
                errors.append(f"{name} not found: {path}")
        return errors

    def summary(self):
        return (
            f"  Host root:      {self.host_root}\n"
            f"  Container root: {self.container_root}\n"
            f"  Movies source:  {self.movies_source}\n"
            f"  TV source:      {self.tv_source}\n"
            f"  Movies linked:  {self.movies_linked}\n"
            f"  TV linked:      {self.tv_linked}\n"
            f"  TMDB key:       {'set' if self.tmdb_api_key else 'not set'}\n"
            f"  TV overrides:   {len(self.tv_name_overrides)} names, "
            f"{len(self.tv_orphan_overrides)} orphans"
        )


def find_config(cli_path=None):
    if cli_path:
        if os.path.isfile(cli_path):
            return cli_path
        print(f"Config not found: {cli_path}")
        sys.exit(1)
    for candidate in [
        os.path.join(os.getcwd(), "medialnk.toml"),
        os.path.expanduser("~/.config/medialnk/medialnk.toml"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def load_config(cli_path=None):
    """Returns (Config, config_path)."""
    path = find_config(cli_path)
    if path is None:
        print("No config file found. Create medialnk.toml or use --config.")
        sys.exit(1)
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(raw), path
