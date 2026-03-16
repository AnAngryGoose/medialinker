#!/usr/bin/env python3
"""
create_test_library.py

Builds a fake media library under a target directory covering every scenario
that make_movies_links.py and make_tv_links.py handle. Files are small (a few
KB each) since the scripts only look at filenames, extensions, and relative
file sizes. Total disk usage is under 1 MB.

Where largest_video() picking matters (multi-file folders, sample exclusion),
the primary file is larger than the others so the correct one gets selected.

Usage:
    python3 create_test_library.py /path/to/test/media

    This creates:
        /path/to/test/media/movies/          (populated)
        /path/to/test/media/tv/              (populated)
        /path/to/test/media/movies-linked/   (empty, ready for script output)
        /path/to/test/media/tv-linked/       (empty, ready for script output)

    Then point the scripts at this directory to test every code path.

    To wipe and recreate:
        python3 create_test_library.py --reset /path/to/test/media
"""

import os
import argparse
import shutil


def fake_file(path, size=1024):
    """Create a small file at path with the given byte count.

    The actual content doesn't matter. The scripts never read file contents,
    only filenames and st_size. Relative sizes matter for largest_video().
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x00' * size)


def build_movies(root):
    """Populate movies/ with every scenario the movies script handles."""
    m = os.path.join(root, "movies")

    # -----------------------------------------------------------------
    # Standard single-version movie in folder
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Dune.2021.1080p.BluRay.x264-GROUP",
        "Dune.2021.1080p.BluRay.x264-GROUP.mkv"), 4000)

    # -----------------------------------------------------------------
    # Multi-version: same title, different quality
    # Tests quality suffix tagging (- 1080P vs - 2160P)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "The.Matrix.1999.1080p.BluRay.x264-GROUP",
        "The.Matrix.1999.1080p.BluRay.mkv"), 8000)
    fake_file(os.path.join(
        m, "The.Matrix.1999.2160p.UHD.REMUX",
        "The.Matrix.1999.2160p.UHD.REMUX.mkv"), 9000)

    # -----------------------------------------------------------------
    # Multi-version: same title, same quality (needs .2 duplicate suffix)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Alien.1979.1080p.BluRay.x264-FIRST",
        "Alien.1979.1080p.BluRay.x264-FIRST.mkv"), 9000)
    fake_file(os.path.join(
        m, "Alien.1979.1080p.BluRay.x265-SECOND",
        "Alien.1979.1080p.BluRay.x265-SECOND.mkv"), 7000)

    # -----------------------------------------------------------------
    # Bare video file at movies root (no parent folder)
    # -----------------------------------------------------------------
    fake_file(os.path.join(m, "Barbie.2023.720p.WEBRip.mkv"), 2000)

    # -----------------------------------------------------------------
    # Folder with sample file (sample must be smaller than primary)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Inception.2010.1080p.BluRay",
        "Inception.2010.1080p.BluRay.mkv"), 8000)
    fake_file(os.path.join(
        m, "Inception.2010.1080p.BluRay",
        "sample.mkv"), 500)

    # -----------------------------------------------------------------
    # No video file in folder (flagged: "no video file found")
    # -----------------------------------------------------------------
    folder = os.path.join(m, "Empty.Movie.2022.1080p")
    os.makedirs(folder, exist_ok=True)
    fake_file(os.path.join(folder, "movie.nfo"), 100)
    fake_file(os.path.join(folder, "poster.jpg"), 200)

    # -----------------------------------------------------------------
    # No year in folder name (flagged: "no year found", TMDB candidate)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Some.Obscure.Documentary.720p.WEB-DL",
        "Some.Obscure.Documentary.720p.WEB-DL.mkv"), 3000)

    # -----------------------------------------------------------------
    # Miniseries in movies folder: 2+ episode files
    # Skipped by movies script, picked up by TV script
    # -----------------------------------------------------------------
    for ep in range(1, 9):
        fake_file(os.path.join(
            m, "The.Night.Of.2016.1080p.BluRay",
            f"The.Night.Of.S01E{ep:02d}.1080p.mkv"), 3000)

    # -----------------------------------------------------------------
    # Ambiguous Part.N folder: 2+ Part files, no episode markers
    # User gets prompted to route as movie or TV
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Kill.Bill.2003.1080p.BluRay",
        "Kill.Bill.Part.1.1080p.mkv"), 6000)
    fake_file(os.path.join(
        m, "Kill.Bill.2003.1080p.BluRay",
        "Kill.Bill.Part.2.1080p.mkv"), 5500)

    # -----------------------------------------------------------------
    # Bare episode file at movies root (skipped by movies script)
    # -----------------------------------------------------------------
    fake_file(os.path.join(m, "Random.Show.S02E05.720p.mkv"), 1000)

    # -----------------------------------------------------------------
    # Title starts with a year-like number
    # "1917" should not be extracted as year; "2019" should
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "1917.2019.1080p.BluRay",
        "1917.2019.1080p.BluRay.mkv"), 8000)

    # -----------------------------------------------------------------
    # RE_BARE_EPISODE false positive risk
    # "E20" in filename could match bare episode pattern
    # Should be treated as a movie, not flagged as episode
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "The.E20.Experience.2013.1080p",
        "The.E20.Experience.2013.1080p.mkv"), 4000)

    # -----------------------------------------------------------------
    # Movie with "Part" in actual title but only one file (not ambiguous)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Bande.a.part.1964.720p.BluRay",
        "Bande.a.part.1964.720p.BluRay.mkv"), 5000)

    # -----------------------------------------------------------------
    # Leading date prefix in filename
    # Date should be stripped during title cleaning
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "2011.12.31.New.Years.Concert.1080p",
        "2011.12.31.New.Years.Concert.1080p.mkv"), 6000)

    # -----------------------------------------------------------------
    # .ts extension coverage
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Old.Movie.2005.HDTV",
        "Old.Movie.2005.HDTV.ts"), 2000)

    # -----------------------------------------------------------------
    # .m4v extension coverage
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        m, "Another.Film.2018.720p",
        "Another.Film.2018.720p.m4v"), 3000)

    # -----------------------------------------------------------------
    # Miniseries using NxNN naming (episode_info coverage)
    # Skipped by movies, routed to TV
    # -----------------------------------------------------------------
    for ep in range(1, 4):
        fake_file(os.path.join(
            m, "Some.Mini.2020.720p",
            f"Some.Mini.1x{ep:02d}.720p.mkv"), 2000)


def build_tv(root):
    """Populate tv/ with every scenario the TV script handles."""
    t = os.path.join(root, "tv")

    # =================================================================
    # PASS 1: SEASON FOLDERS
    # =================================================================

    # -----------------------------------------------------------------
    # Standard multi-season show
    # -----------------------------------------------------------------
    for ep in range(1, 4):
        fake_file(os.path.join(
            t, "Breaking.Bad.S01.1080p.BluRay.x264-GROUP",
            f"Breaking.Bad.S01E{ep:02d}.1080p.mkv"), 3000)
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Breaking.Bad.S02.1080p.BluRay.x264-GROUP",
            f"Breaking.Bad.S02E{ep:02d}.1080p.mkv"), 3000)

    # -----------------------------------------------------------------
    # Apostrophe variation (grouping test)
    # Both should land under the same show name
    # -----------------------------------------------------------------
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Schitts.Creek.S01.1080p.WEB-DL",
            f"Schitts.Creek.S01E{ep:02d}.mkv"), 2000)
    fake_file(os.path.join(
        t, "Schitt's Creek.S02.720p.WEB-DL",
        "Schitt's.Creek.S02E01.mkv"), 1500)

    # -----------------------------------------------------------------
    # Duplicate season warning: same show + season from two sources
    # -----------------------------------------------------------------
    for ep in range(1, 4):
        fake_file(os.path.join(
            t, "Fallout.S01.1080p.BluRay",
            f"Fallout.S01E{ep:02d}.1080p.mkv"), 4000)
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Fallout.S01.2160p.WEB-DL",
            f"Fallout.S01E{ep:02d}.2160p.mkv"), 8000)

    # -----------------------------------------------------------------
    # Trailing year in folder name (stripped from show name)
    # -----------------------------------------------------------------
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Bluey.2018.S01.1080p.WEB-DL",
            f"Bluey.S01E{ep:02d}.mkv"), 500)

    # =================================================================
    # PASS 1: PASS-THROUGH
    # =================================================================

    # -----------------------------------------------------------------
    # Already Jellyfin-structured (symlinked as-is)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "The Simpsons (1989) {tvdb-71663}",
        "Season 01",
        "The Simpsons - S01E01 - Simpsons Roasting on an Open Fire.mkv"), 1000)
    fake_file(os.path.join(
        t, "The Simpsons (1989) {tvdb-71663}",
        "Season 02",
        "The Simpsons - S02E01 - Bart Gets an F.mkv"), 1000)

    # -----------------------------------------------------------------
    # Pass-through overlapping a grouped show name (triggers warning)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Fallout (2024) {tvdb-12345}",
        "Season 01",
        "Fallout.S01E01.mkv"), 3000)

    # =================================================================
    # PASS 1: BARE EPISODE FOLDERS
    # =================================================================

    # -----------------------------------------------------------------
    # Folder with bare E01/E02 naming (no SxxExx prefix)
    # -----------------------------------------------------------------
    for ep in range(1, 4):
        fake_file(os.path.join(
            t, "Planet.Earth.1080p.BluRay",
            f"pe.E{ep:02d}.1080p.mkv"), 5000)

    # =================================================================
    # PASS 1: ORPHANS (require ORPHAN_OVERRIDES)
    # =================================================================

    # -----------------------------------------------------------------
    # Bare "Season N" folder with no show name
    # -----------------------------------------------------------------
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Season 1",
            f"S01E{ep:02d}.Little.Bear.mkv"), 500)

    # -----------------------------------------------------------------
    # "Season.N" dot-naming variant
    # -----------------------------------------------------------------
    for ep in range(1, 3):
        fake_file(os.path.join(
            t, "Wild.Kratts.Season.4",
            f"Wild.Kratts.S04E{ep:02d}.mkv"), 800)

    # =================================================================
    # PASS 2: BARE EPISODE FILES
    # =================================================================

    # -----------------------------------------------------------------
    # Outcome 1: New show, no existing structure
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "A.Knight.of.the.Seven.Kingdoms.S01E06.1080p.WEB-DL.mkv"), 3000)

    # -----------------------------------------------------------------
    # Outcome 2: Same quality as existing season folder (silent skip)
    # Episode already exists inside Breaking.Bad.S01 at 1080p
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Breaking.Bad.S01E01.1080p.mkv"), 3000)

    # -----------------------------------------------------------------
    # Outcome 3: Different quality from existing season (quality variant)
    # S01 folder has 1080p, this is 720p -- triggers conversion prompt
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Breaking.Bad.S01E01.720p.WEB-DL.mkv"), 1500)

    # -----------------------------------------------------------------
    # Outcome 4: Episode missing from existing season folder
    # S01 has E01-E03, not E07 -- triggers conversion prompt
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Breaking.Bad.S01E07.1080p.mkv"), 3000)

    # -----------------------------------------------------------------
    # Outcome 5: Episode for season already converted to real dir
    # (test by running twice: first converts S01, second adds this)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Breaking.Bad.S01E08.1080p.mkv"), 3000)

    # -----------------------------------------------------------------
    # Unmatched bare file (no parseable pattern)
    # -----------------------------------------------------------------
    fake_file(os.path.join(t, "random_video_no_pattern.mkv"), 500)

    # -----------------------------------------------------------------
    # Needs NAME_OVERRIDES: "The Office US" -> "The Office (US)"
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "The.Office.US.S01E01.720p.mkv"), 1000)

    # -----------------------------------------------------------------
    # NxNN episode format
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Futurama.3x05.720p.mkv"), 1000)

    # -----------------------------------------------------------------
    # "Episode.N" format
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Some.Documentary.Episode.4.1080p.mkv"), 2000)

    # -----------------------------------------------------------------
    # "NofN" format
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Planet.Earth.1of6.720p.mkv"), 2500)

    # -----------------------------------------------------------------
    # Double-episode file (known: only first ep number gets linked)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Fallout.S01E05-E06.1080p.mkv"), 5000)

    # -----------------------------------------------------------------
    # Studio prefix in name (fuzzy match stripping test)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Marvels.Spidey.and.His.Amazing.Friends.S01E01.1080p.mkv"), 1000)

    # -----------------------------------------------------------------
    # Trailing year in bare filename (stripped to match folder show name)
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Bluey.2018.S01E05.1080p.mkv"), 500)

    # -----------------------------------------------------------------
    # Sample file at root (ignored entirely)
    # -----------------------------------------------------------------
    fake_file(os.path.join(t, "sample.mkv"), 50)

    # -----------------------------------------------------------------
    # .ts extension coverage
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Old.Show.S01E01.HDTV.ts"), 1500)

    # -----------------------------------------------------------------
    # .m4v extension coverage
    # -----------------------------------------------------------------
    fake_file(os.path.join(
        t, "Retro.Show.S02E03.480p.m4v"), 800)


def main():
    parser = argparse.ArgumentParser(
        description="Create a fake media library for testing medialn."
    )
    parser.add_argument("target",
        help="Root directory to create the test library in")
    parser.add_argument("--reset", action="store_true",
        help="Wipe the target directory first if it exists")
    args = parser.parse_args()

    target = os.path.abspath(args.target)

    if args.reset and os.path.exists(target):
        print(f"[RESET] Removing {target}")
        shutil.rmtree(target)

    if os.path.exists(os.path.join(target, "movies")) or \
       os.path.exists(os.path.join(target, "tv")):
        print(f"[ERROR] {target} already has movies/ or tv/ directories.")
        print(f"        Use --reset to wipe and recreate, or pick a different path.")
        return

    print(f"Creating test library in: {target}\n")

    build_movies(target)
    build_tv(target)

    # Create empty output directories
    os.makedirs(os.path.join(target, "movies-linked"), exist_ok=True)
    os.makedirs(os.path.join(target, "tv-linked"), exist_ok=True)

    # Count what we created
    file_count = 0
    dir_count = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(target):
        dir_count += len(dirnames)
        for fname in filenames:
            file_count += 1
            total_bytes += os.path.getsize(os.path.join(dirpath, fname))

    print(f"Created {file_count} files in {dir_count} directories.")
    print(f"Total disk usage: {total_bytes / 1024:.1f} KB\n")

    print("Directory layout:")
    print(f"  {target}/")
    print(f"    movies/         source (read-only to medialn)")
    print(f"    tv/             source (read-only to medialn)")
    print(f"    movies-linked/  output (medialn writes here)")
    print(f"    tv-linked/      output (medialn writes here)")

    print(f"\nTo test, update the scripts' config to point at this directory:")
    print(f'  MEDIA_ROOT_HOST      = "{target}"')
    print(f'  MEDIA_ROOT_CONTAINER = "{target}"')
    print(f"\nThen run:")
    print(f"  python3 make_movies_links.py --dry-run")
    print(f"  python3 make_tv_links.py --dry-run")

    print(f"\nRequired ORPHAN_OVERRIDES for full TV test coverage:")
    print(f'  "Season 1": ("Little Bear", 1),')
    print(f'  "Wild.Kratts.Season.4": ("Wild Kratts", 4),')
    print(f"\nRequired NAME_OVERRIDES for full TV test coverage:")
    print(f'  "The Office US": "The Office (US)",')


if __name__ == "__main__":
    main()
