// Package logger provides a simple leveled logger that mirrors the Python
// Logger class behavior: writes to stdout (respecting verbosity level)
// and to a log file (always at debug level).
package logger

import (
	"fmt"
	"os"
	"path/filepath"
)

const (
	LevelQuiet   = 0
	LevelNormal  = 1
	LevelVerbose = 2
	LevelDebug   = 3
)

// Logger writes to stdout at the configured level and to a log file always.
type Logger struct {
	level int
	fh    *os.File
}

// New creates a Logger at the given verbosity level string.
// logFile may be empty to suppress file output.
func New(level, logFile string) (*Logger, error) {
	lv := levelFromString(level)
	var fh *os.File
	if logFile != "" {
		if err := os.MkdirAll(filepath.Dir(logFile), 0o755); err != nil {
			return nil, fmt.Errorf("creating log dir: %w", err)
		}
		var err error
		fh, err = os.Create(logFile)
		if err != nil {
			return nil, fmt.Errorf("opening log file: %w", err)
		}
	}
	return &Logger{level: lv, fh: fh}, nil
}

func levelFromString(s string) int {
	switch s {
	case "quiet":
		return LevelQuiet
	case "verbose":
		return LevelVerbose
	case "debug":
		return LevelDebug
	default:
		return LevelNormal
	}
}

func (l *Logger) write(msg string, minLevel int) {
	if l.level >= minLevel {
		fmt.Println(msg)
	}
	if l.fh != nil {
		l.fh.WriteString(msg + "\n")
	}
}

// Quiet logs at level 0 (always shown unless silenced, which doesn't happen).
func (l *Logger) Quiet(format string, args ...any) {
	l.write(fmt.Sprintf(format, args...), LevelQuiet)
}

// Normal logs at level 1 (shown unless quiet mode).
func (l *Logger) Normal(format string, args ...any) {
	l.write(fmt.Sprintf(format, args...), LevelNormal)
}

// Verbose logs at level 2.
func (l *Logger) Verbose(format string, args ...any) {
	l.write(fmt.Sprintf(format, args...), LevelVerbose)
}

// Debug logs at level 3.
func (l *Logger) Debug(format string, args ...any) {
	l.write(fmt.Sprintf(format, args...), LevelDebug)
}

// Close flushes and closes the log file if one was opened.
func (l *Logger) Close() {
	if l.fh != nil {
		l.fh.Close()
		l.fh = nil
	}
}
