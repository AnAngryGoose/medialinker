// Package tv implements the two-pass TV scanning and symlink creation pipeline.
package tv

import (
	"fmt"
	"strings"
)

// BuildLinkName constructs the standardized episode symlink filename.
// Format: Show.S01E05 - 1080P.mkv  or  Show.S01E05-E06 - 1080P.mkv
// quality is uppercased; secondEp < 0 means single episode.
func BuildLinkName(show string, season, episode int, quality, ext string, secondEp int) string {
	tag := fmt.Sprintf("S%02dE%02d", season, episode)
	if secondEp >= 0 {
		tag += fmt.Sprintf("-E%02d", secondEp)
	}
	q := ""
	if quality != "" {
		q = " - " + strings.ToUpper(quality)
	}
	return fmt.Sprintf("%s.%s%s%s", show, tag, q, ext)
}
