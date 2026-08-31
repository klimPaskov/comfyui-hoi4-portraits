// Command hoi4-portrait-setup extracts the model-free workflow package and
// installs it into an existing ComfyUI with a VRAM-guided model variant.
//
// The wizard detects the GPU, offers the official ComfyUI portable package
// when ComfyUI is missing, selects the ROCm package for AMD, pre-checks FP8,
// lets the user toggle optional variants, and then runs the bundled installer.
package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	_ "embed"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

//go:embed payload.zip
var payload []byte

var version = "dev"

const (
	amdPortableURL    = "https://github.com/Comfy-Org/ComfyUI/releases/latest/download/ComfyUI_windows_portable_amd.7z"
	nvidiaPortableURL = "https://github.com/Comfy-Org/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"
	sevenZipURL       = "https://www.7-zip.org/a/7zr.exe"
)

type gpuInfo struct {
	vendor string
	name   string
	vramGB float64
}

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

func formatElapsed(duration time.Duration) string {
	totalSeconds := int64(duration.Round(time.Second) / time.Second)
	if totalSeconds < 0 {
		totalSeconds = 0
	}
	hours := totalSeconds / 3600
	minutes := (totalSeconds % 3600) / 60
	seconds := totalSeconds % 60
	if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, seconds)
	}
	if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, seconds)
	}
	return fmt.Sprintf("%ds", seconds)
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

// detectNvidiaVRAM returns the first NVIDIA GPU's total VRAM in GB.
func detectNvidiaVRAM() float64 {
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

func classifyGPU(names string) gpuInfo {
	lines := strings.FieldsFunc(names, func(r rune) bool { return r == '\r' || r == '\n' })
	for _, line := range lines {
		name := strings.TrimSpace(line)
		lower := strings.ToLower(name)
		if strings.Contains(lower, "nvidia") {
			return gpuInfo{vendor: "nvidia", name: name}
		}
	}
	for _, line := range lines {
		name := strings.TrimSpace(line)
		lower := strings.ToLower(name)
		if strings.Contains(lower, "amd") || strings.Contains(lower, "radeon") || strings.Contains(lower, "advanced micro devices") {
			return gpuInfo{vendor: "amd", name: name}
		}
	}
	if len(lines) > 0 {
		return gpuInfo{vendor: "other", name: strings.TrimSpace(lines[0])}
	}
	return gpuInfo{}
}

func detectGPU() gpuInfo {
	command := "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"
	output, _ := exec.Command("powershell.exe", "-NoProfile", "-Command", command).Output()
	gpu := classifyGPU(string(output))
	nvidiaVRAM := detectNvidiaVRAM()
	if gpu.vendor == "nvidia" {
		gpu.vramGB = nvidiaVRAM
	} else if gpu.vendor == "" && nvidiaVRAM > 0 {
		gpu = gpuInfo{vendor: "nvidia", name: "NVIDIA GPU", vramGB: nvidiaVRAM}
	}
	return gpu
}

func amdWindowsROCmSupported(name string) bool {
	normalized := strings.ToLower(name)
	if strings.Contains(normalized, "strix halo") || strings.Contains(normalized, "ryzen ai max") {
		return true
	}
	rxSeries := regexp.MustCompile(`(?i)\brx\s*(7|9)\d{3}\b`)
	return rxSeries.MatchString(name)
}

func portableURL(gpu gpuInfo) string {
	if gpu.vendor == "amd" {
		return amdPortableURL
	}
	return nvidiaPortableURL
}

func gpuLabel(gpu gpuInfo) string {
	if gpu.name == "" {
		return "not detected"
	}
	if gpu.vramGB > 0 {
		return fmt.Sprintf("%s (%.0f GB VRAM)", gpu.name, gpu.vramGB)
	}
	return gpu.name
}

func recommendedVariant(vram float64) string {
	return "fp8"
}

func recommendedQuant(vram float64) string {
	switch {
	case vram <= 10:
		return "Q4_K_M"
	case vram <= 14:
		return "Q5_K_M"
	case vram <= 16:
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
		{key: "gguf", label: "GGUF (optional, 8-16 GB VRAM)", vr: false},
		{key: "fp8", label: "FP8 (default)", vr: true},
		{key: "full", label: "Full BF16 (optional, >20 GB VRAM)", vr: false},
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
				recommend = "  <-- default"
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
			selected[variants[n-1].key] = true
		}
		if !valid {
			fmt.Println("Please enter valid numbers.")
			continue
		}
		result := []string{}
		for _, v := range variants {
			if selected[v.key] {
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
		return "not available"
	}
	return fmt.Sprintf("%.0f GB", vram)
}

func askYesNo(prompt string, defaultYes bool) bool {
	suffix := " [Y/n]: "
	if !defaultYes {
		suffix = " [y/N]: "
	}
	for {
		switch strings.ToLower(promptLine(prompt + suffix)) {
		case "":
			return defaultYes
		case "y", "yes":
			return true
		case "n", "no":
			return false
		default:
			fmt.Println("Please answer y or n.")
		}
	}
}

func askQuantMenu(vram float64) []string {
	quants := []struct {
		key      string
		selected bool
	}{
		{key: "Q4_K_M", selected: vram <= 10},
		{key: "Q5_K_M", selected: vram > 10 && vram <= 14},
		{key: "Q6_K", selected: vram > 14 && vram <= 16},
		{key: "Q8_0", selected: vram > 16},
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
			if selected[q.key] {
				result = append(result, q.key)
			}
		}
		if len(result) == 0 {
			result = []string{recommended}
		}
		return result
	}
}

func absoluteUserPath(value string) (string, error) {
	cleaned := strings.TrimSpace(value)
	cleaned = strings.Trim(cleaned, `"'`)
	cleaned = os.ExpandEnv(cleaned)
	return filepath.Abs(cleaned)
}

func resolveComfyUIRoot(value string) (string, bool) {
	if strings.TrimSpace(value) == "" {
		return "", false
	}
	path, err := absoluteUserPath(value)
	if err != nil {
		return "", false
	}
	if strings.EqualFold(filepath.Base(path), "main.py") && fileExists(path) {
		path = filepath.Dir(path)
	}
	candidates := []string{
		path,
		filepath.Join(path, "ComfyUI"),
		filepath.Join(path, "ComfyUI_windows_portable", "ComfyUI"),
	}
	for _, candidate := range candidates {
		if fileExists(filepath.Join(candidate, "main.py")) {
			return filepath.Clean(candidate), true
		}
	}
	return "", false
}

func searchForComfyUI(root string, maxDepth int) (string, bool) {
	root, err := absoluteUserPath(root)
	if err != nil {
		return "", false
	}
	if info, err := os.Stat(root); err != nil || !info.IsDir() {
		return "", false
	}
	found := ""
	_ = filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		relative, err := filepath.Rel(root, path)
		if err != nil {
			return nil
		}
		depth := 0
		if relative != "." {
			depth = len(strings.Split(relative, string(os.PathSeparator)))
		}
		if entry.IsDir() {
			if depth > maxDepth {
				return fs.SkipDir
			}
			name := strings.ToLower(entry.Name())
			if depth > 0 && (strings.HasPrefix(name, ".") || name == "node_modules" || name == "__pycache__" || name == "site-packages") {
				return fs.SkipDir
			}
			if candidate, ok := resolveComfyUIRoot(path); ok {
				found = candidate
				return fs.SkipAll
			}
		}
		return nil
	})
	return found, found != ""
}

func findComfyUI() (string, bool) {
	home, _ := os.UserHomeDir()
	workingDirectory, _ := os.Getwd()
	executable, _ := os.Executable()
	localAppData := os.Getenv("LOCALAPPDATA")
	appData := os.Getenv("APPDATA")
	candidates := []string{
		os.Getenv("COMFYUI_ROOT"),
		workingDirectory,
		filepath.Dir(workingDirectory),
		filepath.Dir(executable),
		filepath.Dir(filepath.Dir(executable)),
		`C:\ComfyUI`,
		`C:\ComfyUI_windows_portable\ComfyUI`,
		`C:\ComfyUI_windows_portable`,
		filepath.Join(os.Getenv("USERPROFILE"), "ComfyUI"),
		filepath.Join(os.Getenv("USERPROFILE"), "Documents", "ComfyUI"),
		filepath.Join(home, "Documents", "ComfyUI_windows_portable", "ComfyUI"),
		filepath.Join(home, "Documents", "ComfyUI_windows_portable"),
		filepath.Join(home, "Downloads", "ComfyUI_windows_portable"),
		filepath.Join(home, "Desktop", "ComfyUI_windows_portable"),
		filepath.Join(localAppData, "Programs", "ComfyUI"),
		filepath.Join(localAppData, "Programs", "ComfyUI", "resources", "ComfyUI"),
		filepath.Join(localAppData, "ComfyUI"),
		filepath.Join(appData, "ComfyUI"),
		`D:\ComfyUI`,
		`D:\ComfyUI_windows_portable\ComfyUI`,
		`D:\ComfyUI_windows_portable`,
	}
	for _, candidate := range candidates {
		if root, ok := resolveComfyUIRoot(candidate); ok {
			return root, true
		}
	}
	searchRoots := []string{
		filepath.Join(home, "Desktop"),
		filepath.Join(home, "Downloads"),
		filepath.Join(home, "Documents"),
		filepath.Join(localAppData, "Programs"),
		filepath.Join(localAppData, "ComfyUI"),
		filepath.Join(appData, "ComfyUI"),
	}
	for _, searchRoot := range searchRoots {
		if root, ok := searchForComfyUI(searchRoot, 4); ok {
			return root, true
		}
	}
	return "", false
}

func promptForComfyUIRoot() string {
	fmt.Println("Paste either the ComfyUI folder or its main.py file.")
	fmt.Println(`Examples: C:\ComfyUI  or  C:\ComfyUI\main.py`)
	fmt.Println("Quoted paths and paths dragged into this window are accepted.")
	for {
		path := promptLine("ComfyUI folder or main.py path: ")
		if root, ok := resolveComfyUIRoot(path); ok {
			return root
		}
		if strings.TrimSpace(path) == "" {
			fmt.Println("No path was provided.")
			continue
		}
		fmt.Println("ComfyUI was not found at that path. Select the ComfyUI folder itself or its main.py file and try again.")
	}
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func askStoragePath(label, defaultPath, comfyPath string) string {
	for {
		fmt.Println()
		fmt.Printf("Where should %s be located?\n", label)
		fmt.Printf("  [x] 1) HOI4 workspace: %s\n", defaultPath)
		fmt.Printf("  [ ] 2) ComfyUI folder: %s\n", comfyPath)
		fmt.Println("  [ ] 3) Custom path")
		switch promptLine("Selection (Enter keeps the HOI4 workspace): ") {
		case "", "1":
			return defaultPath
		case "2":
			return comfyPath
		case "3":
			for {
				path := promptLine("Custom folder path: ")
				if strings.TrimSpace(path) != "" {
					absolute, err := absoluteUserPath(path)
					if err == nil {
						return absolute
					}
				}
				fmt.Println("Please enter a valid folder path.")
			}
		default:
			fmt.Println("Please choose 1, 2, or 3.")
		}
	}
}

func askComfyInstallRoot(defaultRoot string) string {
	for {
		line := promptLine(fmt.Sprintf("ComfyUI install folder (Enter for %s): ", defaultRoot))
		root := defaultRoot
		if line != "" {
			absolute, err := absoluteUserPath(line)
			if err != nil {
				fmt.Println("Please enter a valid folder path.")
				continue
			}
			root = absolute
		}
		if directoryEmpty(root) {
			return root
		}
		fmt.Printf("%s is not empty. Choose another folder.\n", root)
	}
}

func downloadFile(url, destination, label string) {
	fmt.Printf("Downloading %s...\n", label)
	response, err := http.Get(url)
	if err != nil {
		fail("cannot download %s: %v", label, err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		fail("cannot download %s: HTTP %s", label, response.Status)
	}
	target, err := os.OpenFile(destination, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		fail("cannot create the %s download: %v", label, err)
	}
	written, copyErr := io.Copy(target, response.Body)
	closeErr := target.Close()
	if copyErr != nil || closeErr != nil {
		fail("cannot save %s", label)
	}
	if written <= 0 {
		fail("downloaded %s is empty", label)
	}
	fmt.Printf("Downloaded %s (%.1f GB).\n", label, float64(written)/1_000_000_000)
}

func installComfyUI(gpu gpuInfo, installRoot string) string {
	parent := filepath.Dir(installRoot)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		fail("cannot create the ComfyUI parent folder: %v", err)
	}
	temporary, err := os.MkdirTemp(parent, ".hoi4-comfyui-install-")
	if err != nil {
		fail("cannot create a temporary ComfyUI folder: %v", err)
	}
	defer os.RemoveAll(temporary)
	archive := filepath.Join(temporary, "ComfyUI_windows_portable.7z")
	sevenZip := filepath.Join(temporary, "7zr.exe")
	flavor := "NVIDIA/CPU"
	if gpu.vendor == "amd" {
		flavor = "AMD ROCm"
	}
	downloadFile(portableURL(gpu), archive, "official ComfyUI "+flavor+" portable")
	downloadFile(sevenZipURL, sevenZip, "7-Zip command-line extractor")
	staging := filepath.Join(temporary, "extracted")
	if err := os.MkdirAll(staging, 0o755); err != nil {
		fail("cannot create the ComfyUI extraction folder: %v", err)
	}
	command := exec.Command(sevenZip, "x", archive, "-o"+staging, "-y")
	command.Stdout = os.Stdout
	command.Stderr = os.Stderr
	if err := command.Run(); err != nil {
		fail("cannot extract the official ComfyUI package: %v", err)
	}
	extractedRoot := filepath.Join(staging, "ComfyUI_windows_portable")
	comfyRoot := filepath.Join(extractedRoot, "ComfyUI")
	if !fileExists(filepath.Join(comfyRoot, "main.py")) {
		fail("the official ComfyUI package did not contain ComfyUI\\main.py")
	}
	if _, err := os.Stat(installRoot); err == nil {
		if !directoryEmpty(installRoot) {
			fail("the selected ComfyUI install folder is no longer empty: %s", installRoot)
		}
		if err := os.Remove(installRoot); err != nil {
			fail("cannot prepare the selected ComfyUI install folder: %v", err)
		}
	}
	if err := os.Rename(extractedRoot, installRoot); err != nil {
		fail("cannot move ComfyUI into %s: %v", installRoot, err)
	}
	return filepath.Join(installRoot, "ComfyUI")
}

func runInstaller(destination, comfyRoot, batchInput, portraitOutput string, variants, quants []string) {
	ps1 := filepath.Join(destination, "scripts", "install_windows.ps1")
	if !fileExists(ps1) {
		fail("installer script missing after extraction: %s", ps1)
	}
	args := []string{
		"-NoProfile", "-ExecutionPolicy", "Bypass",
		"-File", ps1,
		"-ComfyUIRoot", comfyRoot,
		"-Variant", strings.Join(variants, ","),
		"-BatchInputPath", batchInput,
		"-PortraitOutputPath", portraitOutput,
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
	installationStarted := time.Now()
	destination := flag.String("destination", "", "empty destination folder for the extracted package")
	comfyRoot := flag.String("comfyui-root", "", "existing ComfyUI root; skips detection")
	batchInput := flag.String("batch-input", "", "batch input folder; skips the location menu")
	portraitOutput := flag.String("portrait-output", "", "portrait output folder; skips the location menu")
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

	gpu := detectGPU()
	vram := gpu.vramGB
	if *comfyRoot == "" {
		if detectedRoot, found := findComfyUI(); found {
			*comfyRoot = detectedRoot
			fmt.Printf("Found ComfyUI at %s.\n", *comfyRoot)
		} else {
			fmt.Println("ComfyUI was not found in the usual locations.")
			fmt.Printf("Detected GPU: %s\n", gpuLabel(gpu))
			if gpu.vendor == "amd" {
				fmt.Println("The automatic install uses the official experimental AMD portable package with ROCm-enabled PyTorch.")
				if !amdWindowsROCmSupported(gpu.name) {
					fmt.Println("Warning: official Windows ROCm support currently targets RDNA 3, RDNA 3.5, and RDNA 4 GPUs.")
				}
			}
			installPrompt := "Install ComfyUI automatically now?"
			if gpu.vendor == "amd" {
				installPrompt = "Install ComfyUI with ROCm automatically now?"
			}
			if askYesNo(installPrompt, true) {
				home, err := os.UserHomeDir()
				if err != nil {
					fail("cannot resolve the user folder: %v", err)
				}
				installRoot := askComfyInstallRoot(filepath.Join(home, "Documents", "ComfyUI_windows_portable"))
				*comfyRoot = installComfyUI(gpu, installRoot)
				fmt.Printf("Installed ComfyUI at %s.\n", *comfyRoot)
			} else {
				*comfyRoot = promptForComfyUIRoot()
			}
		}
	} else if resolvedRoot, ok := resolveComfyUIRoot(*comfyRoot); ok {
		*comfyRoot = resolvedRoot
	} else {
		fail("ComfyUI was not found at %s. Pass either a folder such as C:\\ComfyUI or the full path C:\\ComfyUI\\main.py.", *comfyRoot)
	}
	workspaceRoot := filepath.Join(filepath.Dir(absolute), "hoi4-portraits")
	if *batchInput == "" {
		*batchInput = askStoragePath("batch inputs", filepath.Join(workspaceRoot, "input"), filepath.Join(*comfyRoot, "input", "hoi4_portraits_batch"))
	}
	if *portraitOutput == "" {
		*portraitOutput = askStoragePath("portrait outputs", filepath.Join(workspaceRoot, "output"), filepath.Join(*comfyRoot, "output", "hoi4_portraits"))
	}
	variants := askVariantMenu(vram)
	quants := []string{"Q5_K_M"}
	for _, v := range variants {
		if v == "gguf" {
			quants = askQuantMenu(vram)
			break
		}
	}
	sort.SliceStable(variants, func(i, j int) bool {
		return variants[i] == recommendedVariant(vram) && variants[j] != recommendedVariant(vram)
	})
	sort.Strings(quants)
	fmt.Println()
	fmt.Printf("Selected variants: %s\n", strings.Join(variants, ", "))
	fmt.Printf("Selected GGUF quants: %s\n", strings.Join(quants, ", "))
	fmt.Printf("ComfyUI root: %s\n", *comfyRoot)
	fmt.Printf("Batch inputs: %s\n", *batchInput)
	fmt.Printf("Portrait outputs: %s\n", *portraitOutput)

	runInstaller(absolute, *comfyRoot, *batchInput, *portraitOutput, variants, quants)

	fmt.Println()
	fmt.Println("Installation finished.")
	fmt.Printf("Total installation time: %s.\n", formatElapsed(time.Since(installationStarted)))
	fmt.Println("Restart ComfyUI, then open Workflows > hoi4_portraits and queue a workflow.")
	fmt.Printf("Add batch images to %s and collect PNG and DDS files from %s.\n", *batchInput, *portraitOutput)
}
