param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [string]$Variant = "fp8",

    [string]$GgufQuants = "Q5_K_M",

    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Variants = @($Variant -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })

foreach ($item in $Variants) {
    if ($item -notin @("full", "fp8", "gguf")) {
        throw "Unknown variant '$item'. Use full, fp8, or gguf."
    }
}

$Candidates = @(
    (Join-Path $ComfyUIRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $ComfyUIRoot) "python_embeded\python.exe"),
    (Join-Path $ComfyUIRoot "python_embeded\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

& $Python -c "import cv2, scipy, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install -r (Join-Path $ProjectRoot "custom_nodes\hoi4_portraits\requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $SkipModels) {
    & $Python -c "import huggingface_hub, hf_xet" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install -r (Join-Path $ProjectRoot "scripts\requirements-download.txt")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Write-Host "Installing the exact Adonis workflow dependencies..."
& $Python (Join-Path $ProjectRoot "scripts\install_custom_node_packs.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python (Join-Path $ProjectRoot "scripts\build_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\validate_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\install_workflows.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$VariantArgs = @()
foreach ($item in $Variants) {
    $VariantArgs += @("--variant", $item)
}
& $Python (Join-Path $ProjectRoot "scripts\apply_variant.py") --comfyui-root $ComfyUIRoot @VariantArgs --gguf-quants $GgufQuants
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipModels) {
    $DownloadArgs = @()
    foreach ($item in $Variants) {
        $DownloadArgs += @("--variant", $item)
    }
    & $Python (Join-Path $ProjectRoot "scripts\download_models.py") --comfyui-root $ComfyUIRoot @DownloadArgs --gguf-quants $GgufQuants
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installed $($Variants.Count) model variant(s): $($Variants -join ', ') (GGUF quants: $GgufQuants)."
Write-Host "Four workflows are under user\default\workflows\hoi4_portraits. Restart ComfyUI, then open Workflows > hoi4_portraits."
