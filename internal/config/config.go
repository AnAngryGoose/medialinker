// Package config handles TOML configuration loading, path resolution, and validation.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

// raw TOML shapes — unexported, only used during decode.
type rawPaths struct {
	MediaRootHost      string `toml:"media_root_host"`
	MediaRootContainer string `toml:"media_root_container"`
	MoviesSource       string `toml:"movies_source"`
	TVSource           string `toml:"tv_source"`
	MoviesLinked       string `toml:"movies_linked"`
	TVLinked           string `toml:"tv_linked"`
}

type rawTMDB struct {
	APIKey          string `toml:"api_key"`
	ConfidenceCheck *bool  `toml:"confidence_check"`
}

type rawLogging struct {
	LogDir    string `toml:"log_dir"`
	Verbosity string `toml:"verbosity"`
}

// OrphanOverride holds the resolved show name and season number for a
// bare "Season N" folder that has no show name context.
type OrphanOverride struct {
	Show   string
	Season int
}

type rawOrphanValue struct {
	Show   string `toml:"show"`
	Season int    `toml:"season"`
}

type rawOverrides struct {
	TVNames     map[string]string          `toml:"tv_names"`
	TVOrphans   map[string]rawOrphanValue  `toml:"tv_orphans"`
	MovieTitles map[string]string          `toml:"movie_titles"`
}

type rawConfig struct {
	Paths     rawPaths     `toml:"paths"`
	TMDB      rawTMDB      `toml:"tmdb"`
	Logging   rawLogging   `toml:"logging"`
	Overrides rawOverrides `toml:"overrides"`
}

// Config is the resolved, validated configuration for a medialnk run.
// All paths are absolute.
type Config struct {
	// Roots
	HostRoot      string
	ContainerRoot string

	// Source directories (host absolute paths — read-only)
	MoviesSource string
	TVSource     string

	// Output directories (host absolute paths — safe to write via PathGuard)
	MoviesLinked string
	TVLinked     string

	// Convenience slices
	SourceDirs []string
	OutputDirs []string

	// TMDB
	TMDBApiKey    string
	TMDBConfidence bool

	// Logging
	LogDir    string
	Verbosity string // "quiet" | "normal" | "verbose" | "debug"

	// Overrides
	TVNameOverrides    map[string]string
	TVOrphanOverrides  map[string]OrphanOverride
	MovieTitleOverrides map[string]string // parsed but not yet applied (Phase 2.2)
}

func resolve(val, defaultVal, root string) string {
	if val == "" {
		val = defaultVal
	}
	if filepath.IsAbs(val) {
		return val
	}
	return filepath.Join(root, val)
}

// Load reads a TOML config file and returns a fully resolved Config.
func Load(path string) (*Config, error) {
	var raw rawConfig
	if _, err := toml.DecodeFile(path, &raw); err != nil {
		return nil, fmt.Errorf("parsing config %s: %w", path, err)
	}

	hostRoot := raw.Paths.MediaRootHost
	if hostRoot == "" {
		return nil, fmt.Errorf("paths.media_root_host is required")
	}

	containerRoot := raw.Paths.MediaRootContainer
	if containerRoot == "" {
		containerRoot = hostRoot
	}

	cfg := &Config{
		HostRoot:      hostRoot,
		ContainerRoot: containerRoot,
		MoviesSource:  resolve(raw.Paths.MoviesSource, "movies", hostRoot),
		TVSource:      resolve(raw.Paths.TVSource, "tv", hostRoot),
		MoviesLinked:  resolve(raw.Paths.MoviesLinked, "movies-linked", hostRoot),
		TVLinked:      resolve(raw.Paths.TVLinked, "tv-linked", hostRoot),
	}
	cfg.SourceDirs = []string{cfg.MoviesSource, cfg.TVSource}
	cfg.OutputDirs = []string{cfg.MoviesLinked, cfg.TVLinked}

	// TMDB: env var takes priority over config file
	cfg.TMDBApiKey = os.Getenv("TMDB_API_KEY")
	if cfg.TMDBApiKey == "" {
		cfg.TMDBApiKey = raw.TMDB.APIKey
	}
	cfg.TMDBConfidence = true // default
	if raw.TMDB.ConfidenceCheck != nil {
		cfg.TMDBConfidence = *raw.TMDB.ConfidenceCheck
	}

	// Logging
	logDir := raw.Logging.LogDir
	if logDir == "" {
		logDir = "logs"
	}
	cfg.LogDir = resolve(logDir, "logs", hostRoot)
	cfg.Verbosity = raw.Logging.Verbosity
	if cfg.Verbosity == "" {
		cfg.Verbosity = "normal"
	}

	// Overrides
	cfg.TVNameOverrides = raw.Overrides.TVNames
	if cfg.TVNameOverrides == nil {
		cfg.TVNameOverrides = map[string]string{}
	}
	cfg.TVOrphanOverrides = make(map[string]OrphanOverride, len(raw.Overrides.TVOrphans))
	for k, v := range raw.Overrides.TVOrphans {
		cfg.TVOrphanOverrides[k] = OrphanOverride{Show: v.Show, Season: v.Season}
	}
	cfg.MovieTitleOverrides = raw.Overrides.MovieTitles
	if cfg.MovieTitleOverrides == nil {
		cfg.MovieTitleOverrides = map[string]string{}
	}

	return cfg, nil
}

// Validate checks that required directories exist.
// Returns a slice of error strings (empty means valid).
func (c *Config) Validate() []string {
	var errs []string
	if info, err := os.Stat(c.HostRoot); err != nil || !info.IsDir() {
		errs = append(errs, fmt.Sprintf("media_root_host not found: %s", c.HostRoot))
	}
	for _, pair := range [][2]string{
		{"movies_source", c.MoviesSource},
		{"tv_source", c.TVSource},
	} {
		if info, err := os.Stat(pair[1]); err != nil || !info.IsDir() {
			errs = append(errs, fmt.Sprintf("%s not found: %s", pair[0], pair[1]))
		}
	}
	return errs
}

// Summary returns a human-readable description of the resolved config.
func (c *Config) Summary() string {
	tmdbStatus := "not set"
	if c.TMDBApiKey != "" {
		tmdbStatus = "set"
	}
	return fmt.Sprintf(
		"  Host root:      %s\n"+
			"  Container root: %s\n"+
			"  Movies source:  %s\n"+
			"  TV source:      %s\n"+
			"  Movies linked:  %s\n"+
			"  TV linked:      %s\n"+
			"  TMDB key:       %s\n"+
			"  TV overrides:   %d names, %d orphans",
		c.HostRoot, c.ContainerRoot,
		c.MoviesSource, c.TVSource,
		c.MoviesLinked, c.TVLinked,
		tmdbStatus,
		len(c.TVNameOverrides), len(c.TVOrphanOverrides),
	)
}

// ValidatePathGuard checks that no output directory is inside a source directory.
// Returns an error describing the conflict if one is found.
func (c *Config) ValidatePathGuard() error {
	for _, output := range c.OutputDirs {
		for _, source := range c.SourceDirs {
			if output == source || strings.HasPrefix(output, source+string(os.PathSeparator)) {
				return fmt.Errorf("output inside source.\n  Out: %s\n  Src: %s", output, source)
			}
		}
	}
	return nil
}

// FindConfig searches for a config file in the standard locations.
// Returns the path if found, empty string if not found, or an error if a
// CLI-specified path doesn't exist.
func FindConfig(cliPath string) (string, error) {
	if cliPath != "" {
		if _, err := os.Stat(cliPath); err != nil {
			return "", fmt.Errorf("config not found: %s", cliPath)
		}
		return cliPath, nil
	}
	candidates := []string{
		filepath.Join(mustCwd(), "medialnk.toml"),
		filepath.Join(homeDir(), ".config", "medialnk", "medialnk.toml"),
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			return c, nil
		}
	}
	return "", nil
}

func mustCwd() string {
	cwd, _ := os.Getwd()
	return cwd
}

func homeDir() string {
	h, _ := os.UserHomeDir()
	return h
}
