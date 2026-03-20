package common

import (
	"os"
	"path/filepath"
	"strings"
)

// VideoExts is the set of recognized video file extensions (lowercase).
var VideoExts = map[string]bool{
	".mkv": true,
	".mp4": true,
	".avi": true,
	".ts":  true,
	".m4v": true,
}

// IsVideo reports whether the filename has a recognized video extension.
func IsVideo(filename string) bool {
	ext := strings.ToLower(filepath.Ext(filename))
	return VideoExts[ext]
}

// IsEpisodeFile reports whether the filename contains episode notation.
// When includePart is false, Part.N patterns are excluded.
func IsEpisodeFile(filename string, includePart bool) bool {
	return EpisodeInfo(filename, includePart) != nil
}

// VideoEntry holds a file's name, full path, and size.
type VideoEntry struct {
	Name string
	Path string
	Size int64
}

// FindVideos returns video files directly in folder (non-recursive).
// If excludeEpisodes is true, files with episode notation are skipped.
// If excludeSamples is true, files matching the sample pattern are skipped.
func FindVideos(folder string, excludeEpisodes, excludeSamples bool) ([]VideoEntry, error) {
	entries, err := os.ReadDir(folder)
	if err != nil {
		return nil, err
	}
	var out []VideoEntry
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if !IsVideo(name) {
			continue
		}
		if excludeSamples && IsSample(name) {
			continue
		}
		if excludeEpisodes && IsEpisodeFile(name, true) {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		out = append(out, VideoEntry{
			Name: name,
			Path: filepath.Join(folder, name),
			Size: info.Size(),
		})
	}
	return out, nil
}

// LargestVideo returns the VideoEntry with the largest Size.
// Caller must ensure videos is non-empty.
func LargestVideo(videos []VideoEntry) VideoEntry {
	best := videos[0]
	for _, v := range videos[1:] {
		if v.Size > best.Size {
			best = v
		}
	}
	return best
}
