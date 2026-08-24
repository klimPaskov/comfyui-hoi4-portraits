package main

import (
	"path/filepath"
	"testing"
	"time"
)

func TestFormatElapsedUsesReadableUnits(t *testing.T) {
	tests := []struct {
		duration time.Duration
		want     string
	}{
		{duration: 42 * time.Second, want: "42s"},
		{duration: 12*time.Minute + 7*time.Second, want: "12m 7s"},
		{duration: 2*time.Hour + 3*time.Minute + 4*time.Second, want: "2h 3m 4s"},
	}
	for _, test := range tests {
		if got := formatElapsed(test.duration); got != test.want {
			t.Fatalf("formatElapsed(%s) = %q, want %q", test.duration, got, test.want)
		}
	}
}

func TestGPUDetectionPrefersDiscreteNvidiaOverAMDIntegratedGraphics(t *testing.T) {
	gpu := classifyGPU("AMD Radeon(TM) Graphics\r\nNVIDIA GeForce RTX 4090\r\n")
	if gpu.vendor != "nvidia" || gpu.name != "NVIDIA GeForce RTX 4090" {
		t.Fatalf("unexpected GPU classification: %#v", gpu)
	}
}

func TestAMDUsesOfficialROCmPortable(t *testing.T) {
	gpu := classifyGPU("AMD Radeon RX 7900 XTX\n")
	if gpu.vendor != "amd" {
		t.Fatalf("unexpected GPU classification: %#v", gpu)
	}
	if !amdWindowsROCmSupported(gpu.name) {
		t.Fatalf("expected %q to be supported by the Windows ROCm portable", gpu.name)
	}
	if got := portableURL(gpu); got != amdPortableURL {
		t.Fatalf("portableURL(%#v) = %q, want %q", gpu, got, amdPortableURL)
	}
}

func TestOlderAMDWarnsButStillSelectsTheOfficialAMDPortable(t *testing.T) {
	gpu := classifyGPU("Radeon RX 6700 XT\n")
	if amdWindowsROCmSupported(gpu.name) {
		t.Fatalf("did not expect %q in the official Windows ROCm support range", gpu.name)
	}
	if got := portableURL(gpu); got != amdPortableURL {
		t.Fatalf("portableURL(%#v) = %q, want %q", gpu, got, amdPortableURL)
	}
}

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
	destination := filepath.Join("C:", "Users", "Example", "Documents", "HOI4-Portrait-Workflows-1.0.1")
	workspace := filepath.Join(filepath.Dir(destination), "hoi4-portraits")
	if got := filepath.Join(workspace, "input"); got != filepath.Join("C:", "Users", "Example", "Documents", "hoi4-portraits", "input") {
		t.Fatalf("unexpected input default: %s", got)
	}
	if got := filepath.Join(workspace, "output"); got != filepath.Join("C:", "Users", "Example", "Documents", "hoi4-portraits", "output") {
		t.Fatalf("unexpected output default: %s", got)
	}
}
