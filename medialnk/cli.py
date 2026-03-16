"""
cli.py

Subcommand handlers, logging, argument parsing.
"""

import os
import sys
import argparse
import datetime
import shutil

from . import __version__
from .config import load_config
from .common import (
    init_guard, validate_output_dir, clean_broken_symlinks,
    ensure_dir, symlink_target_exists, is_video,
)
from . import movies
from . import tv


class Logger:
    """Respects verbosity levels. Log file always gets verbose detail."""
    LEVELS = {"quiet": 0, "normal": 1, "verbose": 2, "debug": 3}

    def __init__(self, level="normal", log_file=None):
        self._level = self.LEVELS.get(level, 1)
        self._fh = None
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            self._fh = open(log_file, 'w')

    def _w(self, msg, min_lv):
        if self._level >= min_lv:
            print(msg)
        if self._fh:
            self._fh.write(msg + "\n")

    def quiet(self, msg):   self._w(msg, 0)
    def normal(self, msg):  self._w(msg, 1)
    def verbose(self, msg): self._w(msg, 2)
    def debug(self, msg):   self._w(msg, 3)

    def close(self):
        if self._fh:
            self._fh.close()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_sync(args):
    cfg, cfg_path = load_config(args.config)

    v = cfg.verbosity
    if args.verbose == 1: v = "verbose"
    elif args.verbose and args.verbose >= 2: v = "debug"
    if args.quiet: v = "quiet"

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    lf = os.path.join(cfg.log_dir, f"{ts}_sync.log") if not args.dry_run else None
    log = Logger(level=v, log_file=lf)

    log.normal(f"medialnk v{__version__} sync")
    log.normal(f"Config: {cfg_path}")
    if args.dry_run:
        log.normal("[DRY RUN]")
    log.verbose(cfg.summary())
    log.normal("")

    errs = cfg.validate()
    if errs:
        for e in errs:
            log.quiet(f"[ERROR] {e}")
        log.close()
        sys.exit(1)

    init_guard(cfg.source_dirs, cfg.output_dirs)
    log.verbose(f"[GUARD] {len(cfg.source_dirs)} source(s), {len(cfg.output_dirs)} output(s)")

    for d in cfg.output_dirs:
        validate_output_dir(d, args.dry_run)

    if not args.tv_only:
        movies.run(cfg, args.dry_run, args.yes, log)

    if not args.movies_only:
        tv.run(cfg, args.dry_run, args.yes, log)

    log.normal("")
    log.normal("Dry run complete." if args.dry_run else f"Sync complete. Log: {lf}")
    log.close()


def cmd_clean(args):
    cfg, _ = load_config(args.config)
    v = "verbose" if args.verbose else "normal"
    log = Logger(level=v)
    log.normal(f"medialnk v{__version__} clean")

    errs = cfg.validate()
    if errs:
        for e in errs:
            log.quiet(f"[ERROR] {e}")
        sys.exit(1)

    init_guard(cfg.source_dirs, cfg.output_dirs)
    total = 0
    for d in cfg.output_dirs:
        if not os.path.isdir(d):
            log.normal(f"  {d}: does not exist")
            continue
        if args.dry_run:
            c = 0
            for dp, dns, fns in os.walk(d):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    if os.path.islink(fp) and not symlink_target_exists(fp, cfg.host_root, cfg.container_root):
                        log.verbose(f"  [BROKEN] {fp}")
                        c += 1
            log.normal(f"  {d}: {c} broken")
            total += c
        else:
            log.normal(f"  Cleaning {d}...")
            r = clean_broken_symlinks(d, cfg.host_root, cfg.container_root)
            total += r
            log.normal(f"  Removed {r}")

    action = "Would remove" if args.dry_run else "Removed"
    log.normal(f"\n{action} {total} broken symlink(s).")
    log.close()


def cmd_validate(args):
    cfg, cfg_path = load_config(args.config)
    log = Logger(level="verbose")
    log.normal(f"medialnk v{__version__} validate")
    log.normal(f"Config: {cfg_path}\n")
    log.normal(cfg.summary())
    log.normal("")

    ok = True
    errs = cfg.validate()
    if errs:
        for e in errs:
            log.quiet(f"[FAIL] {e}")
        ok = False
    else:
        log.normal("[PASS] Source directories exist.")

    for d in cfg.output_dirs:
        if os.path.isdir(d):
            c = sum(1 for dp, _, fns in os.walk(d) for fn in fns
                    if is_video(fn) and not os.path.islink(os.path.join(dp, fn)))
            if c:
                log.quiet(f"[WARN] {d}: {c} real video file(s)")
            else:
                log.normal(f"[PASS] {d}: clean")
        else:
            log.normal(f"[INFO] {d}: not created yet")

    try:
        init_guard(cfg.source_dirs, cfg.output_dirs)
        log.normal("[PASS] PathGuard valid.")
    except Exception as e:
        log.quiet(f"[FAIL] PathGuard: {e}")
        ok = False

    log.close()
    sys.exit(0 if ok else 1)


def cmd_test_library(args):
    target = os.path.abspath(args.path)
    if args.reset and os.path.exists(target):
        print(f"[RESET] Removing {target}")
        shutil.rmtree(target)
    if os.path.exists(os.path.join(target, "movies")) or os.path.exists(os.path.join(target, "tv")):
        print(f"[ERROR] {target} already has media dirs. Use --reset.")
        sys.exit(1)
    from .test_library import build
    build(target)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="medialnk", description="Symlink-based media library manager.")
    p.add_argument("--version", action="version", version=f"medialnk {__version__}")
    p.add_argument("--config", metavar="PATH", help="Config file path")
    sp = p.add_subparsers(dest="command", help="Commands")

    s = sp.add_parser("sync", help="Scan and link")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--yes", "-y", action="store_true", help="Auto-accept prompts")
    s.add_argument("--tv-only", action="store_true")
    s.add_argument("--movies-only", action="store_true")
    s.add_argument("-v", "--verbose", action="count", default=0)
    s.add_argument("-q", "--quiet", action="store_true")

    c = sp.add_parser("clean", help="Remove broken symlinks")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("-v", "--verbose", action="count", default=0)

    sp.add_parser("validate", help="Check config and paths")

    t = sp.add_parser("test-library", help="Generate fake test library")
    t.add_argument("path", help="Target directory")
    t.add_argument("--reset", action="store_true")

    return p


def main():
    p = build_parser()
    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(0)
    {"sync": cmd_sync, "clean": cmd_clean, "validate": cmd_validate,
     "test-library": cmd_test_library}[args.command](args)
