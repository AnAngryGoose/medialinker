package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/AnAngryGoose/medialnk/internal/testlib"
)

var testLibReset bool

var testLibCmd = &cobra.Command{
	Use:   "test-library <path>",
	Short: "Generate a fake test library for validation",
	Args:  cobra.ExactArgs(1),
	RunE:  runTestLib,
}

func init() {
	testLibCmd.Flags().BoolVar(&testLibReset, "reset", false, "Remove target directory before creating")
}

func runTestLib(cmd *cobra.Command, args []string) error {
	target, err := filepath.Abs(args[0])
	if err != nil {
		return err
	}

	// Check for existing media dirs (prevent accidental overwrite without --reset).
	if !testLibReset {
		for _, sub := range []string{"movies", "tv"} {
			if _, err := os.Stat(filepath.Join(target, sub)); err == nil {
				return fmt.Errorf("%s already has media dirs. Use --reset", target)
			}
		}
	}

	return testlib.Build(target, testLibReset)
}
