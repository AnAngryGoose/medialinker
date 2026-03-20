// Package testlib generates a fake media library covering all parsing scenarios.
// Small binary files with correct relative sizes are created — no real media content.
package testlib

import (
	"fmt"
	"os"
	"path/filepath"
)

// writeFile creates a file of the given byte size at path, creating parent dirs as needed.
func writeFile(path string, size int) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	if size > 0 {
		buf := make([]byte, size)
		f.Write(buf)
	}
	return nil
}

// Build creates the full test library at target.
// If reset is true, the target directory is removed and recreated first.
func Build(target string, reset bool) error {
	if reset {
		if err := os.RemoveAll(target); err != nil {
			return fmt.Errorf("reset: %w", err)
		}
	}
	m := filepath.Join(target, "movies")
	t := filepath.Join(target, "tv")

	type entry struct {
		path string
		size int
	}

	files := []entry{
		// --- Movies ---
		{filepath.Join(m, "Dune.2021.1080p.BluRay.x264-GROUP", "Dune.2021.1080p.BluRay.x264-GROUP.mkv"), 4000},
		{filepath.Join(m, "The.Matrix.1999.1080p.BluRay.x264-GROUP", "The.Matrix.1999.1080p.BluRay.mkv"), 8000},
		{filepath.Join(m, "The.Matrix.1999.2160p.UHD.REMUX", "The.Matrix.1999.2160p.UHD.REMUX.mkv"), 9000},
		{filepath.Join(m, "Alien.1979.1080p.BluRay.x264-FIRST", "Alien.1979.1080p.BluRay.x264-FIRST.mkv"), 9000},
		{filepath.Join(m, "Alien.1979.1080p.BluRay.x265-SECOND", "Alien.1979.1080p.BluRay.x265-SECOND.mkv"), 7000},
		{filepath.Join(m, "Barbie.2023.720p.WEBRip.mkv"), 2000},
		{filepath.Join(m, "Inception.2010.1080p.BluRay", "Inception.2010.1080p.BluRay.mkv"), 8000},
		{filepath.Join(m, "Inception.2010.1080p.BluRay", "sample.mkv"), 500},
		{filepath.Join(m, "Empty.Movie.2022.1080p", "movie.nfo"), 100},
		{filepath.Join(m, "Empty.Movie.2022.1080p", "poster.jpg"), 200},
		{filepath.Join(m, "Some.Obscure.Documentary.720p.WEB-DL", "Some.Obscure.Documentary.720p.WEB-DL.mkv"), 3000},
		{filepath.Join(m, "Kill.Bill.2003.1080p.BluRay", "Kill.Bill.Part.1.1080p.mkv"), 6000},
		{filepath.Join(m, "Kill.Bill.2003.1080p.BluRay", "Kill.Bill.Part.2.1080p.mkv"), 5500},
		{filepath.Join(m, "Random.Show.S02E05.720p.mkv"), 1000},
		{filepath.Join(m, "1917.2019.1080p.BluRay", "1917.2019.1080p.BluRay.mkv"), 8000},
		{filepath.Join(m, "The.E20.Experience.2013.1080p", "The.E20.Experience.2013.1080p.mkv"), 4000},
		{filepath.Join(m, "Bande.a.part.1964.720p.BluRay", "Bande.a.part.1964.720p.BluRay.mkv"), 5000},
		{filepath.Join(m, "2011.12.31.New.Years.Concert.1080p", "2011.12.31.New.Years.Concert.1080p.mkv"), 6000},
		{filepath.Join(m, "Old.Movie.2005.HDTV", "Old.Movie.2005.HDTV.ts"), 2000},
		{filepath.Join(m, "Another.Film.2018.720p", "Another.Film.2018.720p.m4v"), 3000},
		// --- TV season folders ---
		{filepath.Join(t, "Schitt's Creek.S02.720p.WEB-DL", "Schitt's.Creek.S02E01.mkv"), 1500},
		// --- TV bare files ---
		{filepath.Join(t, "A.Knight.of.the.Seven.Kingdoms.S01E06.1080p.WEB-DL.mkv"), 3000},
		{filepath.Join(t, "Breaking.Bad.S01E01.1080p.mkv"), 3000},
		{filepath.Join(t, "Breaking.Bad.S01E01.720p.WEB-DL.mkv"), 1500},
		{filepath.Join(t, "Breaking.Bad.S01E07.1080p.mkv"), 3000},
		{filepath.Join(t, "Breaking.Bad.S01E08.1080p.mkv"), 3000},
		{filepath.Join(t, "random_video_no_pattern.mkv"), 500},
		{filepath.Join(t, "The.Office.US.S01E01.720p.mkv"), 1000},
		{filepath.Join(t, "Futurama.3x05.720p.mkv"), 1000},
		{filepath.Join(t, "Some.Documentary.Episode.4.1080p.mkv"), 2000},
		{filepath.Join(t, "Planet.Earth.1of6.720p.mkv"), 2500},
		{filepath.Join(t, "Fallout.S01E05-E06.1080p.mkv"), 5000},
		{filepath.Join(t, "Marvels.Spidey.and.His.Amazing.Friends.S01E01.1080p.mkv"), 1000},
		{filepath.Join(t, "Bluey.2018.S01E05.1080p.mkv"), 500},
		{filepath.Join(t, "sample.mkv"), 50},
		{filepath.Join(t, "Old.Show.S01E01.HDTV.ts"), 1500},
		{filepath.Join(t, "Retro.Show.S02E03.480p.m4v"), 800},
	}

	// Episode ranges — generated in loops in Python, expanded here.
	// The Night Of: 8 episodes in movies/
	for ep := 1; ep <= 8; ep++ {
		files = append(files, entry{
			filepath.Join(m, "The.Night.Of.2016.1080p.BluRay", fmt.Sprintf("The.Night.Of.S01E%02d.1080p.mkv", ep)),
			3000,
		})
	}
	// Some.Mini: 3 episodes in movies/ (NxNN format)
	for ep := 1; ep <= 3; ep++ {
		files = append(files, entry{
			filepath.Join(m, "Some.Mini.2020.720p", fmt.Sprintf("Some.Mini.1x%02d.720p.mkv", ep)),
			2000,
		})
	}
	// Breaking Bad S01 and S02
	for ep := 1; ep <= 3; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Breaking.Bad.S01.1080p.BluRay.x264-GROUP", fmt.Sprintf("Breaking.Bad.S01E%02d.1080p.mkv", ep)),
			3000,
		})
	}
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Breaking.Bad.S02.1080p.BluRay.x264-GROUP", fmt.Sprintf("Breaking.Bad.S02E%02d.1080p.mkv", ep)),
			3000,
		})
	}
	// Schitt's Creek S01
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Schitts.Creek.S01.1080p.WEB-DL", fmt.Sprintf("Schitts.Creek.S01E%02d.mkv", ep)),
			2000,
		})
	}
	// Fallout S01 1080p and 2160p (duplicate season)
	for ep := 1; ep <= 3; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Fallout.S01.1080p.BluRay", fmt.Sprintf("Fallout.S01E%02d.1080p.mkv", ep)),
			4000,
		})
	}
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Fallout.S01.2160p.WEB-DL", fmt.Sprintf("Fallout.S01E%02d.2160p.mkv", ep)),
			8000,
		})
	}
	// Bluey S01
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Bluey.2018.S01.1080p.WEB-DL", fmt.Sprintf("Bluey.S01E%02d.mkv", ep)),
			500,
		})
	}
	// The Simpsons passthrough (already structured)
	files = append(files,
		entry{filepath.Join(t, "The Simpsons (1989) {tvdb-71663}", "Season 01", "The Simpsons - S01E01 - Simpsons Roasting on an Open Fire.mkv"), 1000},
		entry{filepath.Join(t, "The Simpsons (1989) {tvdb-71663}", "Season 02", "The Simpsons - S02E01 - Bart Gets an F.mkv"), 1000},
		entry{filepath.Join(t, "Fallout (2024) {tvdb-12345}", "Season 01", "Fallout.S01E01.mkv"), 3000},
	)
	// Planet Earth bare E-notation
	for ep := 1; ep <= 3; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Planet.Earth.1080p.BluRay", fmt.Sprintf("pe.E%02d.1080p.mkv", ep)),
			5000,
		})
	}
	// Season 1 orphan override
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Season 1", fmt.Sprintf("S01E%02d.Little.Bear.mkv", ep)),
			500,
		})
	}
	// Wild Kratts Season 4 orphan override
	for ep := 1; ep <= 2; ep++ {
		files = append(files, entry{
			filepath.Join(t, "Wild.Kratts.Season.4", fmt.Sprintf("Wild.Kratts.S04E%02d.mkv", ep)),
			800,
		})
	}

	for _, e := range files {
		if err := writeFile(e.path, e.size); err != nil {
			return fmt.Errorf("creating %s: %w", e.path, err)
		}
	}

	// Ensure output dirs exist.
	for _, d := range []string{
		filepath.Join(target, "movies-linked"),
		filepath.Join(target, "tv-linked"),
	} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return fmt.Errorf("creating output dir %s: %w", d, err)
		}
	}

	// Count files created.
	fileCount := 0
	filepath.WalkDir(target, func(_ string, d os.DirEntry, _ error) error {
		if !d.IsDir() {
			fileCount++
		}
		return nil
	})
	fmt.Printf("Test library: %s  (%d files)\n", target, fileCount)

	// Write auto-generated config.
	tomlPath := filepath.Join(target, "medialnk.toml")
	tomlContent := fmt.Sprintf(`[paths]
media_root_host = "%s"
media_root_container = "%s"

[tmdb]
api_key = ""

[overrides.tv_names]
"The Office US" = "The Office (US)"

[overrides.tv_orphans]
"Season 1" = { show = "Little Bear", season = 1 }
"Wild.Kratts.Season.4" = { show = "Wild Kratts", season = 4 }
`, target, target)

	if err := os.WriteFile(tomlPath, []byte(tomlContent), 0o644); err != nil {
		return fmt.Errorf("writing config: %w", err)
	}
	fmt.Printf("Config: %s\n", tomlPath)
	fmt.Printf("\nTest: medialnk --config %s sync --dry-run\n", tomlPath)
	return nil
}
