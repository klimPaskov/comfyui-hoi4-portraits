package main

import (
	"path/filepath"
	"testing"
)

func TestRecommendedVariantNeverAutomaticallySelectsFull(t *testing.T) {
	tests := []struct {
		vram float64
		want string
	}{
		{vram: 0, want: "fp8"},
		{vram: 8, want: "fp8"},
		{vram: 15.9, want: "fp8"},
		{vram: 16, want: "fp8"},
		{vram: 24, want: "fp8"},
		{vram: 80, want: "fp8"},
	}
	for _, test := range tests {
		if got := recommendedVariant(test.vram); got != test.want {
			t.Fatalf("recommendedVariant(%v) = %q, want %q", test.vram, got, test.want)
		}
	}
}

func TestWorkspaceDefaultsUseLocalHoi4PortraitFolders(t *testing.T) {
	destination := filepath.Join("C:", "Users", "Example", "Documents", "HOI4-Portrait-Workflows-1.0.0")
	workspace := filepath.Join(filepath.Dir(destination), "hoi4-portraits")
	if got := filepath.Join(workspace, "input"); got != filepath.Join("C:", "Users", "Example", "Documents", "hoi4-portraits", "input") {
		t.Fatalf("unexpected input default: %s", got)
	}
	if got := filepath.Join(workspace, "output"); got != filepath.Join("C:", "Users", "Example", "Documents", "hoi4-portraits", "output") {
		t.Fatalf("unexpected output default: %s", got)
	}
}
