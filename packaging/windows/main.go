package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

//go:embed payload.zip
var payload []byte

var version = "dev"

func fail(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "Setup stopped: "+format+"\n", values...)
	os.Exit(1)
}

func destinationDefault() string {
	home, err := os.UserHomeDir()
	if err != nil {
		fail("cannot resolve the user folder: %v", err)
	}
	return filepath.Join(home, "Documents", "HOI4-Portrait-Workflows-"+version)
}

func directoryEmpty(path string) bool {
	entries, err := os.ReadDir(path)
	return os.IsNotExist(err) || (err == nil && len(entries) == 0)
}

func extract(destination string) {
	if !directoryEmpty(destination) {
		fail("destination is not empty: %s", destination)
	}
	if err := os.MkdirAll(destination, 0o755); err != nil {
		fail("cannot create destination: %v", err)
	}
	reader, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		fail("embedded package is invalid: %v", err)
	}
	cleanRoot := filepath.Clean(destination) + string(os.PathSeparator)
	for _, item := range reader.File {
		target := filepath.Join(destination, filepath.FromSlash(item.Name))
		cleanTarget := filepath.Clean(target)
		if !strings.HasPrefix(cleanTarget+string(os.PathSeparator), cleanRoot) {
			fail("unsafe archive path: %s", item.Name)
		}
		if item.FileInfo().IsDir() {
			if err := os.MkdirAll(cleanTarget, 0o755); err != nil {
				fail("cannot create directory: %v", err)
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(cleanTarget), 0o755); err != nil {
			fail("cannot create parent directory: %v", err)
		}
		source, err := item.Open()
		if err != nil {
			fail("cannot read embedded file: %v", err)
		}
		targetFile, err := os.OpenFile(cleanTarget, os.O_CREATE|os.O_EXCL|os.O_WRONLY, item.Mode())
		if err != nil {
			source.Close()
			fail("cannot create extracted file: %v", err)
		}
		_, copyErr := io.Copy(targetFile, source)
		closeErr := targetFile.Close()
		source.Close()
		if copyErr != nil || closeErr != nil {
			fail("cannot write extracted file")
		}
	}
}

func main() {
	destination := flag.String("destination", "", "empty destination folder for the extracted package")
	flag.Parse()
	if *destination == "" {
		*destination = destinationDefault()
	}
	absolute, err := filepath.Abs(*destination)
	if err != nil {
		fail("cannot resolve destination: %v", err)
	}
	extract(absolute)
	instructions := filepath.Join(absolute, "docs", "local-install.md")
	fmt.Printf("HOI4 portrait workflow package %s extracted to:\n%s\n\n", version, absolute)
	fmt.Println("ComfyUI is not included. The installer adds the bundled hoi4_portraits node pack when you follow docs/local-install.md.")
	fmt.Println("Open docs/local-install.md for model installation and RunPod/Windows commands.")
	_ = exec.Command("cmd", "/C", "start", "", instructions).Start()
}
