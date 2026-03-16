"""
test_library.py

Builds a fake media library covering every scenario the scan/link
pipelines handle. Small files with correct relative sizes.
"""

import os


def _f(path, size=1024):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x00' * size)


def build(target):
    m = os.path.join(target, "movies")
    t = os.path.join(target, "tv")

    # Movies
    _f(os.path.join(m, "Dune.2021.1080p.BluRay.x264-GROUP", "Dune.2021.1080p.BluRay.x264-GROUP.mkv"), 4000)
    _f(os.path.join(m, "The.Matrix.1999.1080p.BluRay.x264-GROUP", "The.Matrix.1999.1080p.BluRay.mkv"), 8000)
    _f(os.path.join(m, "The.Matrix.1999.2160p.UHD.REMUX", "The.Matrix.1999.2160p.UHD.REMUX.mkv"), 9000)
    _f(os.path.join(m, "Alien.1979.1080p.BluRay.x264-FIRST", "Alien.1979.1080p.BluRay.x264-FIRST.mkv"), 9000)
    _f(os.path.join(m, "Alien.1979.1080p.BluRay.x265-SECOND", "Alien.1979.1080p.BluRay.x265-SECOND.mkv"), 7000)
    _f(os.path.join(m, "Barbie.2023.720p.WEBRip.mkv"), 2000)
    _f(os.path.join(m, "Inception.2010.1080p.BluRay", "Inception.2010.1080p.BluRay.mkv"), 8000)
    _f(os.path.join(m, "Inception.2010.1080p.BluRay", "sample.mkv"), 500)
    os.makedirs(os.path.join(m, "Empty.Movie.2022.1080p"), exist_ok=True)
    _f(os.path.join(m, "Empty.Movie.2022.1080p", "movie.nfo"), 100)
    _f(os.path.join(m, "Empty.Movie.2022.1080p", "poster.jpg"), 200)
    _f(os.path.join(m, "Some.Obscure.Documentary.720p.WEB-DL", "Some.Obscure.Documentary.720p.WEB-DL.mkv"), 3000)
    for ep in range(1, 9):
        _f(os.path.join(m, "The.Night.Of.2016.1080p.BluRay", f"The.Night.Of.S01E{ep:02d}.1080p.mkv"), 3000)
    _f(os.path.join(m, "Kill.Bill.2003.1080p.BluRay", "Kill.Bill.Part.1.1080p.mkv"), 6000)
    _f(os.path.join(m, "Kill.Bill.2003.1080p.BluRay", "Kill.Bill.Part.2.1080p.mkv"), 5500)
    _f(os.path.join(m, "Random.Show.S02E05.720p.mkv"), 1000)
    _f(os.path.join(m, "1917.2019.1080p.BluRay", "1917.2019.1080p.BluRay.mkv"), 8000)
    _f(os.path.join(m, "The.E20.Experience.2013.1080p", "The.E20.Experience.2013.1080p.mkv"), 4000)
    _f(os.path.join(m, "Bande.a.part.1964.720p.BluRay", "Bande.a.part.1964.720p.BluRay.mkv"), 5000)
    _f(os.path.join(m, "2011.12.31.New.Years.Concert.1080p", "2011.12.31.New.Years.Concert.1080p.mkv"), 6000)
    _f(os.path.join(m, "Old.Movie.2005.HDTV", "Old.Movie.2005.HDTV.ts"), 2000)
    _f(os.path.join(m, "Another.Film.2018.720p", "Another.Film.2018.720p.m4v"), 3000)
    for ep in range(1, 4):
        _f(os.path.join(m, "Some.Mini.2020.720p", f"Some.Mini.1x{ep:02d}.720p.mkv"), 2000)

    # TV season folders
    for ep in range(1, 4):
        _f(os.path.join(t, "Breaking.Bad.S01.1080p.BluRay.x264-GROUP", f"Breaking.Bad.S01E{ep:02d}.1080p.mkv"), 3000)
    for ep in range(1, 3):
        _f(os.path.join(t, "Breaking.Bad.S02.1080p.BluRay.x264-GROUP", f"Breaking.Bad.S02E{ep:02d}.1080p.mkv"), 3000)
    for ep in range(1, 3):
        _f(os.path.join(t, "Schitts.Creek.S01.1080p.WEB-DL", f"Schitts.Creek.S01E{ep:02d}.mkv"), 2000)
    _f(os.path.join(t, "Schitt's Creek.S02.720p.WEB-DL", "Schitt's.Creek.S02E01.mkv"), 1500)
    for ep in range(1, 4):
        _f(os.path.join(t, "Fallout.S01.1080p.BluRay", f"Fallout.S01E{ep:02d}.1080p.mkv"), 4000)
    for ep in range(1, 3):
        _f(os.path.join(t, "Fallout.S01.2160p.WEB-DL", f"Fallout.S01E{ep:02d}.2160p.mkv"), 8000)
    for ep in range(1, 3):
        _f(os.path.join(t, "Bluey.2018.S01.1080p.WEB-DL", f"Bluey.S01E{ep:02d}.mkv"), 500)
    _f(os.path.join(t, "The Simpsons (1989) {tvdb-71663}", "Season 01", "The Simpsons - S01E01 - Simpsons Roasting on an Open Fire.mkv"), 1000)
    _f(os.path.join(t, "The Simpsons (1989) {tvdb-71663}", "Season 02", "The Simpsons - S02E01 - Bart Gets an F.mkv"), 1000)
    _f(os.path.join(t, "Fallout (2024) {tvdb-12345}", "Season 01", "Fallout.S01E01.mkv"), 3000)
    for ep in range(1, 4):
        _f(os.path.join(t, "Planet.Earth.1080p.BluRay", f"pe.E{ep:02d}.1080p.mkv"), 5000)
    for ep in range(1, 3):
        _f(os.path.join(t, "Season 1", f"S01E{ep:02d}.Little.Bear.mkv"), 500)
    for ep in range(1, 3):
        _f(os.path.join(t, "Wild.Kratts.Season.4", f"Wild.Kratts.S04E{ep:02d}.mkv"), 800)

    # TV bare files
    _f(os.path.join(t, "A.Knight.of.the.Seven.Kingdoms.S01E06.1080p.WEB-DL.mkv"), 3000)
    _f(os.path.join(t, "Breaking.Bad.S01E01.1080p.mkv"), 3000)
    _f(os.path.join(t, "Breaking.Bad.S01E01.720p.WEB-DL.mkv"), 1500)
    _f(os.path.join(t, "Breaking.Bad.S01E07.1080p.mkv"), 3000)
    _f(os.path.join(t, "Breaking.Bad.S01E08.1080p.mkv"), 3000)
    _f(os.path.join(t, "random_video_no_pattern.mkv"), 500)
    _f(os.path.join(t, "The.Office.US.S01E01.720p.mkv"), 1000)
    _f(os.path.join(t, "Futurama.3x05.720p.mkv"), 1000)
    _f(os.path.join(t, "Some.Documentary.Episode.4.1080p.mkv"), 2000)
    _f(os.path.join(t, "Planet.Earth.1of6.720p.mkv"), 2500)
    _f(os.path.join(t, "Fallout.S01E05-E06.1080p.mkv"), 5000)
    _f(os.path.join(t, "Marvels.Spidey.and.His.Amazing.Friends.S01E01.1080p.mkv"), 1000)
    _f(os.path.join(t, "Bluey.2018.S01E05.1080p.mkv"), 500)
    _f(os.path.join(t, "sample.mkv"), 50)
    _f(os.path.join(t, "Old.Show.S01E01.HDTV.ts"), 1500)
    _f(os.path.join(t, "Retro.Show.S02E03.480p.m4v"), 800)

    os.makedirs(os.path.join(target, "movies-linked"), exist_ok=True)
    os.makedirs(os.path.join(target, "tv-linked"), exist_ok=True)

    # Count
    fc = sum(len(fns) for _, _, fns in os.walk(target))
    print(f"Test library: {target}  ({fc} files)")

    # Auto-generate config
    toml = os.path.join(target, "medialnk.toml")
    with open(toml, 'w') as f:
        f.write(f'[paths]\nmedia_root_host = "{target}"\nmedia_root_container = "{target}"\n\n')
        f.write('[tmdb]\napi_key = ""\n\n')
        f.write('[overrides.tv_names]\n"The Office US" = "The Office (US)"\n\n')
        f.write('[overrides.tv_orphans]\n')
        f.write('"Season 1" = { show = "Little Bear", season = 1 }\n')
        f.write('"Wild.Kratts.Season.4" = { show = "Wild Kratts", season = 4 }\n')
    print(f"Config: {toml}")
    print(f"\nTest: python3 -m medialnk --config {toml} sync --dry-run")
