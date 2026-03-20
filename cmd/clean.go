package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"

	"github.com/AnAngryGoose/medialnk/internal/common"
	"github.com/AnAngryGoose/medialnk/internal/config"
	"github.com/AnAngryGoose/medialnk/internal/logger"
)

var (
	cleanDryRun bool
	cleanVerbose int
)

var cleanCmd = &cobra.Command{
	Use:   "clean",
	Short: "Remove broken symlinks from output directories",
	RunE:  runClean,
}

func init() {
	cleanCmd.Flags().BoolVar(&cleanDryRun, "dry-run", false, "Preview only, no writes")
	cleanCmd.Flags().CountVarP(&cleanVerbose, "verbose", "v", "Verbose output")
}

func runClean(cmd *cobra.Command, args []string) error {
	cfgPath, err := config.FindConfig(cfgPath)
	if err != nil {
		return err
	}
	if cfgPath == "" {
		return fmt.Errorf("no config file found")
	}

	cfg, err := config.Load(cfgPath)
	if err != nil {
		return err
	}

	level := "normal"
	if cleanVerbose > 0 {
		level = "verbose"
	}
	log, err := logger.New(level, "")
	if err != nil {
		return err
	}
	defer log.Close()

	log.Normal("medialnk v%s clean", Version)

	if errs := cfg.Validate(); len(errs) > 0 {
		for _, e := range errs {
			log.Quiet("[ERROR] %s", e)
		}
		os.Exit(1)
	}

	total := 0
	for _, d := range cfg.OutputDirs {
		info, err := os.Stat(d)
		if err != nil || !info.IsDir() {
			log.Normal("  %s: does not exist", d)
			continue
		}
		if cleanDryRun {
			// Count broken symlinks without removing.
			c := 0
			filepath.WalkDir(d, func(path string, de os.DirEntry, err error) error {
				if err != nil {
					return nil
				}
				if de.Type()&os.ModeSymlink != 0 {
					if !common.SymlinkTargetExists(path, cfg.HostRoot, cfg.ContainerRoot) {
						log.Verbose("  [BROKEN] %s", path)
						c++
					}
				}
				return nil
			})
			log.Normal("  %s: %d broken", d, c)
			total += c
		} else {
			log.Normal("  Cleaning %s...", d)
			sp, err := common.NewSafePath(d, cfg.OutputDirs)
			if err != nil {
				log.Normal("  [ERROR] %v", err)
				continue
			}
			r, err := common.CleanBrokenSymlinks(sp, cfg.HostRoot, cfg.ContainerRoot)
			if err != nil {
				log.Normal("  [ERROR] %v", err)
			}
			total += r
			log.Normal("  Removed %d", r)
		}
	}

	action := "Removed"
	if cleanDryRun {
		action = "Would remove"
	}
	log.Normal("\n%s %d broken symlink(s).", action, total)
	return nil
}
