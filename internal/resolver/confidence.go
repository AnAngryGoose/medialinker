// Package resolver handles TMDB API lookups with caching and
// word-overlap confidence checking.
package resolver

import (
	"regexp"
	"strings"
)

var reNonWord = regexp.MustCompile(`[^\w\s]`)

// words normalizes s to a set of lowercase plain words.
// Special characters are replaced with spaces before splitting.
// This handles degree signs, hyphens-as-joiners, apostrophes, etc.
func words(s string) map[string]bool {
	s = strings.ToLower(s)
	s = reNonWord.ReplaceAllString(s, " ")
	parts := strings.Fields(s)
	set := make(map[string]bool, len(parts))
	for _, w := range parts {
		if w != "" {
			set[w] = true
		}
	}
	return set
}

// wordOverlap checks whether result is a confident match for parsed.
//
// Short names (1-2 words): all parsed words must appear in result,
// and result may have at most 1 extra word beyond the parsed set.
// Longer names: at least 50% of parsed words must appear in result.
func wordOverlap(parsed, result string) bool {
	pw := words(parsed)
	rw := words(result)
	if len(pw) == 0 {
		return false
	}
	overlap := 0
	for w := range pw {
		if rw[w] {
			overlap++
		}
	}
	if len(pw) <= 2 {
		return overlap == len(pw) && len(rw) <= len(pw)+1
	}
	return float64(overlap) >= float64(len(pw))/2.0
}
