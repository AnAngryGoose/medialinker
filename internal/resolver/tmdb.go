package resolver

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sync"
	"time"

	"github.com/AnAngryGoose/medialnk/internal/common"
)

// Logger is the subset of logging methods the resolver needs.
type Logger interface {
	Verbose(format string, args ...any)
}

// cache holds TMDB results to avoid duplicate API calls across a run.
var (
	cacheMu sync.Mutex
	cache   = map[string]any{} // value is (string | movieResult | nil)
)

type movieResult struct {
	Title string
	Year  string
}

// ClearCache resets the global TMDB result cache. Call between test runs.
func ClearCache() {
	cacheMu.Lock()
	defer cacheMu.Unlock()
	cache = map[string]any{}
}

var httpClient = &http.Client{Timeout: 8 * time.Second}

func tmdbGet(endpoint string, query string, apiKey string) ([]byte, error) {
	params := url.Values{}
	params.Set("query", query)
	params.Set("api_key", apiKey)
	rawURL := fmt.Sprintf("https://api.themoviedb.org/3/%s?%s", endpoint, params.Encode())
	resp, err := httpClient.Get(rawURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}

// SearchTV looks up a TV show name on TMDB and returns the canonical title,
// or empty string if not found / confidence check fails.
// Results are cached; the same query is never sent twice per run.
func SearchTV(name, apiKey string, confidence bool, log Logger) string {
	key := "tv:" + name
	cacheMu.Lock()
	if v, ok := cache[key]; ok {
		cacheMu.Unlock()
		if v == nil {
			return ""
		}
		return v.(string)
	}
	cacheMu.Unlock()

	store := func(v any) {
		cacheMu.Lock()
		cache[key] = v
		cacheMu.Unlock()
	}

	if apiKey == "" || len(name) < 3 {
		store(nil)
		return ""
	}
	body, err := tmdbGet("search/tv", name, apiKey)
	if err != nil {
		store(nil)
		return ""
	}
	var resp struct {
		Results []struct {
			Name string `json:"name"`
		} `json:"results"`
	}
	if err := json.Unmarshal(body, &resp); err != nil || len(resp.Results) == 0 {
		store(nil)
		return ""
	}
	title := common.Sanitize(resp.Results[0].Name)
	if confidence && !wordOverlap(name, title) {
		if log != nil {
			log.Verbose("    [TMDB] Rejected: '%s' -> '%s' (low confidence)", name, title)
		}
		store(nil)
		return ""
	}
	store(title)
	return title
}

// SearchMovie looks up a movie title on TMDB and returns the canonical
// (title, year) pair, or ("", "") if not found / confidence check fails.
// Results are cached per query.
func SearchMovie(title, apiKey string, confidence bool, log Logger) (string, string) {
	key := "movie:" + title
	cacheMu.Lock()
	if v, ok := cache[key]; ok {
		cacheMu.Unlock()
		if v == nil {
			return "", ""
		}
		mr := v.(movieResult)
		return mr.Title, mr.Year
	}
	cacheMu.Unlock()

	store := func(v any) {
		cacheMu.Lock()
		cache[key] = v
		cacheMu.Unlock()
	}

	if apiKey == "" || len(title) < 4 {
		store(nil)
		return "", ""
	}
	body, err := tmdbGet("search/movie", title, apiKey)
	if err != nil {
		store(nil)
		return "", ""
	}
	var resp struct {
		Results []struct {
			Title       string `json:"title"`
			ReleaseDate string `json:"release_date"`
		} `json:"results"`
	}
	if err := json.Unmarshal(body, &resp); err != nil || len(resp.Results) == 0 {
		store(nil)
		return "", ""
	}
	found := common.Sanitize(resp.Results[0].Title)
	year := ""
	if rd := resp.Results[0].ReleaseDate; len(rd) >= 4 {
		year = rd[:4]
	}
	if confidence && !wordOverlap(title, found) {
		if log != nil {
			log.Verbose("    [TMDB] Rejected: '%s' -> '%s' (low confidence)", title, found)
		}
		store(nil)
		return "", ""
	}
	store(movieResult{Title: found, Year: year})
	return found, year
}

// ResolveTVName returns the canonical show name using override → TMDB → parsed fallback.
func ResolveTVName(parsed string, overrides map[string]string, apiKey string, confidence bool, log Logger) string {
	if canonical, ok := overrides[parsed]; ok {
		return canonical
	}
	if canonical := SearchTV(parsed, apiKey, confidence, log); canonical != "" {
		return canonical
	}
	return parsed
}
