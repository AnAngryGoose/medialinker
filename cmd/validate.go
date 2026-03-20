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

var validateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Check config, paths, and PathGuard",
	RunE:  runValidate,
}

func runValidate(cmd *cobra.Command, args []string) error {
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

	log, err := logger.New("verbose", "")
	if err != nil {
		return err
	}
	defer log.Close()

	log.Normal("medialnk v%s validate", Version)
	log.Normal("Config: %s\n", cfgPath)
	log.Normal(cfg.Summary())
	log.Normal("")

	ok := true

	if errs := cfg.Validate(); len(errs) > 0 {
		for _, e := range errs {
			log.Quiet("[FAIL] %s", e)
		}
		ok = false
	} else {
		log.Normal("[PASS] Source directories exist.")
	}

	for _, d := range cfg.OutputDirs {
		info, err := os.Stat(d)
		if err != nil || !info.IsDir() {
			log.Normal("[INFO] %s: not created yet", d)
			continue
		}
		c := 0
		filepath.WalkDir(d, func(path string, de os.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			if !de.IsDir() && common.IsVideo(de.Name()) && !common.IsSymlink(path) {
				c++
			}
			return nil
		})
		if c > 0 {
			log.Quiet("[WARN] %s: %d real video file(s)", d, c)
		} else {
			log.Normal("[PASS] %s: clean", d)
		}
	}

	if err := cfg.ValidatePathGuard(); err != nil {
		log.Quiet("[FAIL] PathGuard: %v", err)
		ok = false
	} else {
		log.Normal("[PASS] PathGuard valid.")
	}

	log.Close()
	if !ok {
		os.Exit(1)
	}
	return nil
}
