package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var watchCmd = &cobra.Command{
	Use:   "watch",
	Short: "Watch for changes and sync automatically (not yet implemented)",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("watch mode is not yet implemented")
		return nil
	},
}
