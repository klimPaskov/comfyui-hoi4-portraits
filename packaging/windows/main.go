// Command hoi4-portrait-setup extracts the model-free workflow package and
// installs it into an existing ComfyUI with a VRAM-guided model variant.
//
// The wizard detects the GPU VRAM, pre-checks the recommended
// FLUX.2 Klein 9B variant (gguf / fp8 / full), lets the user toggle any
// combination, asks for GGUF quantizations when gguf is chosen, finds the
// ComfyUI root, and then runs the bundled PowerShell installer exactly like
// the RunPod installer does.
package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	_ "embed"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

//go:embed payload.zip
var payload []byte

var version = "dev"

type variant struct {
	key      string
	label    string
	vr       bool
	selected bool
}

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

// detectVRAM returns the total GPU VRAM in GB, or 0 when it cannot be found.
func detectVRAM() float64 {
	cmd := exec.Command("nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits")
	output, err := cmd.Output()
	if err != nil {
		return 0
	}
	fields := strings.Fields(string(output))
	if len(fields) == 0 {
		return 0
	}
	mb, err := strconv.ParseFloat(fields[0], 64)
	if err != nil || mb <= 0 {
		return 0
	}
	return mb / 1024.0
}

func recommendedVariant(vram float64) string {
	switch {
	case vram > 20:
		return "full"
	case vram > 16:
		return "fp8"
	default:
		return "gguf"
	}
}

func recommendedQuant(vram float64) string {
	switch {
	case vram <= 10:
		return "Q4_K_M"
	case vram <= 14:
		return "Q5_K_M"
	case vram <= 18:
		return "Q6_K"
	default:
		return "Q8_0"
	}
}

func promptLine(prompt string) string {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print(prompt)
	line, err := reader.ReadString('\n')
	if err != nil && line == "" {
		return ""
	}
	return strings.TrimSpace(line)
}

func askVariantMenu(vram float64) []string {
	recommended := recommendedVariant(vram)
	variants := []variant{
		{key: "gguf", label: "GGUF (8-16 GB VRAM)", vr: recommended == "gguf"},
		{key: "fp8", label: "FP8 (16-20 GB VRAM)", vr: recommended == "fp8"},
		{key: "full", label: "Full BF16 (24+ GB VRAM)", vr: recommended == "full"},
	}
	for {
		fmt.Println()
		fmt.Printf("Detected VRAM: %s\n", vramLabel(vram))
		fmt.Println("Which FLUX.2 Klein 9B model(s) should be installed?")
		fmt.Println("Type the numbers you want (space separated) and press Enter. [x] = selected.")
		for i, v := range variants {
			marker := " "
			if v.vr {
				marker = "x"
			}
			recommend := ""
			if v.key == recommended {
				recommend = "  <-- recommended for your GPU"
			}
			fmt.Printf("  [%s] %d) %s%s\n", marker, i+1, v.label, recommend)
		}
		line := promptLine("Selection (Enter keeps the recommended): ")
		if line == "" {
			return []string{recommended}
		}
		tokens := strings.Fields(line)
		selected := map[string]bool{}
		valid := true
		for _, token := range tokens {
			n, err := strconv.Atoi(token)
			if err != nil || n < 1 || n > len(variants) {
				valid = false
				break
			}
			selected[variants[n-1].key] = !variants[n-1].vr
		}
		if !valid {
			fmt.Println("Please enter valid numbers.")
			continue
		}
		// Each typed number toggles that variant from its current state;
		// untyped variants keep their current state. Returning empty keeps
		// the recommended selection.
		result := []string{}
		for _, v := range variants {
			desired, toggled := selected[v.key]
			if toggled {
				if desired {
					result = append(result, v.key)
				}
			} else if v.vr {
				result = append(result, v.key)
			}
		}
		if len(result) == 0 {
			result = []string{recommended}
		}
		return result
	}
}

func vramLabel(vram float64) string {
	if vram <= 0 {
		return "not detected (NVIDIA GPU not found)"
	}
	return fmt.Sprintf("%.0f GB", vram)
}

func askQuantMenu(vram float64) []string {
	quants := []struct {
		key      string
		selected bool
	}{
		{key: "Q4_K_M", selected: vram <= 10},
		{key: "Q5_K_M", selected: vram > 10 && vram <= 14},
		{key: "Q6_K", selected: vram > 14 && vram <= 18},
		{key: "Q8_0", selected: vram > 18},
	}
	recommended := recommendedQuant(vram)
	for {
		fmt.Println()
		fmt.Println("Which GGUF quantization(s) should be installed?")
		fmt.Println("Type the numbers you want (space separated) and press Enter. [x] = selected.")
		for i, q := range quants {
			marker := " "
			if q.selected {
				marker = "x"
			}
			recommend := ""
			if q.key == recommended {
				recommend = "  <-- recommended for your GPU"
			}
			fmt.Printf("  [%s] %d) %s%s\n", marker, i+1, q.key, recommend)
		}
		line := promptLine("Selection (Enter keeps the recommended): ")
		if line == "" {
			return []string{recommended}
		}
		tokens := strings.Fields(line)
		selected := map[string]bool{}
		valid := true
		for _, token := range tokens {
			n, err := strconv.Atoi(token)
			if err != nil || n < 1 || n > len(quants) {
				valid = false
				break
			}
			selected[quants[n-1].key] = true
		}
		if !valid {
			fmt.Println("Please enter valid numbers.")
			continue
		}
		result := []string{}
		for _, q := range quants {
			if selected[q.key] || (len(selected) == 0 && q.selected) {
				result = append(result, q.key)
			}
		}
		if len(result) == 0 {
			result = []string{recommended}
		}
		return result
	}
}

func findComfyUI() string {
	candidates := []string{
		`C:\ComfyUI`,
		filepath.Join(os.Getenv("USERPROFILE"), "ComfyUI"),
		filepath.Join(os.Getenv("USERPROFILE"), "Documents", "ComfyUI"),
		`D:\ComfyUI`,
	}
	for _, candidate := range candidates {
		if fileExists(filepath.Join(candidate, "main.py")) {
			return candidate
		}
	}
	for {
		path := promptLine("ComfyUI root (folder containing main.py): ")
		if path == "" {
			fmt.Println("No ComfyUI root was provided.")
			continue
		}
		if fileExists(filepath.Join(path, "main.py")) {
			return path
		}
		fmt.Printf("%s does not contain main.py. Try again.\n", path)
	}
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func runInstaller(destination, comfyRoot string, variants, quants []string) {
	ps1 := filepath.Join(destination, "scripts", "install_windows.ps1")
	if !fileExists(ps1) {
		fail("installer script missing after extraction: %s", ps1)
	}
	args := []string{
		"-NoProfile", "-ExecutionPolicy", "Bypass",
		"-File", ps1,
		"-ComfyUIRoot", comfyRoot,
	}
	for _, v := range variants {
		args = append(args, "-Variant", v)
	}
	args = append(args, "-GgufQuants", strings.Join(quants, ","))
	cmd := exec.Command("powershell.exe", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	fmt.Println()
	fmt.Println("Running the ComfyUI installer (this downloads the selected models)...")
	if err := cmd.Run(); err != nil {
		fail("PowerShell installer failed: %v", err)
	}
}

func main() {
	destination := flag.String("destination", "", "empty destination folder for the extracted package")
	comfyRoot := flag.String("comfyui-root", "", "existing ComfyUI root; skips detection")
	flag.Parse()
	if *destination == "" {
		*destination = destinationDefault()
	}
	absolute, err := filepath.Abs(*destination)
	if err != nil {
		fail("cannot resolve destination: %v", err)
	}
	fmt.Printf("HOI4 Portrait Workflows %s\n", version)
	fmt.Println("=====================================")
	extract(absolute)
	fmt.Printf("Package extracted to:\n%s\n\n", absolute)

	vram := detectVRAM()
	if *comfyRoot == "" {
		*comfyRoot = findComfyUI()
	}
	variants := askVariantMenu(vram)
	quants := []string{"Q5_K_M"}
	for _, v := range variants {
		if v == "gguf" {
			quants = askQuantMenu(vram)
			break
		}
	}
	sort.Strings(variants)
	sort.Strings(quants)
	fmt.Println()
	fmt.Printf("Selected variants: %s\n", strings.Join(variants, ", "))
	fmt.Printf("Selected GGUF quants: %s\n", strings.Join(quants, ", "))
	fmt.Printf("ComfyUI root: %s\n", *comfyRoot)

	runInstaller(absolute, *comfyRoot, variants, quants)

	fmt.Println()
	fmt.Println("Installation finished.")
	fmt.Println("Restart ComfyUI, then open Workflows > hoi4_portraits and queue a workflow.")
	fmt.Println("Everything (workflows, custom nodes, models, and DDS outputs) is ready to use.")
}
