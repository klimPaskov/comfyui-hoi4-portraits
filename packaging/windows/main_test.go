package main

import "testing"

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
