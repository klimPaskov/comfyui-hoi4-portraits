param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [string[]]$Variant = @("full"),

    [string]$GgufQuants = "Q5_K_M",

    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$GgufRevision = "6ea2651e7df66d7585f6ffee804b20e92fb38b8a"
$GgufUrl = "https://github.com/city96/ComfyUI-GGUF.git"
$GgufDirectory = Join-Path $ComfyUIRoot "custom_nodes\ComfyUI-GGUF"

foreach ($item in $Variant) {
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

if ($Variant -contains "gguf") {
    Write-Host "Installing the ComfyUI-GGUF node pack for the GGUF variant..."
    New-Item -ItemType Directory -Force -Path (Join-Path $ComfyUIRoot "custom_nodes") | Out-Null
    if (Test-Path (Join-Path $GgufDirectory ".git")) {
        & git -C $GgufDirectory fetch --depth 1 origin $GgufRevision
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } elseif (Test-Path $GgufDirectory) {
        throw "$GgufDirectory exists but is not a Git checkout. Move it aside, then rerun this installer."
    } else {
        & git clone --filter=blob:none --no-checkout $GgufUrl $GgufDirectory
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & git -C $GgufDirectory fetch --depth 1 origin $GgufRevision
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & git -C $GgufDirectory checkout --detach $GgufRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pip install -r (Join-Path $GgufDirectory "requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Python (Join-Path $ProjectRoot "scripts\build_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\validate_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\install_workflows.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$VariantArgs = @()
foreach ($item in $Variant) {
    $VariantArgs += @("--variant", $item)
}
& $Python (Join-Path $ProjectRoot "scripts\apply_variant.py") --comfyui-root $ComfyUIRoot @VariantArgs --gguf-quants $GgufQuants
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipModels) {
    $DownloadArgs = @()
    foreach ($item in $Variant) {
        $DownloadArgs += @("--variant", $item)
    }
    & $Python (Join-Path $ProjectRoot "scripts\download_models.py") --comfyui-root $ComfyUIRoot @DownloadArgs --gguf-quants $GgufQuants
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installed $($Variant.Count) model variant(s): $($Variant -join ', ') (GGUF quants: $GgufQuants)."
Write-Host "Four workflows are under user\default\workflows\hoi4_portraits. Restart ComfyUI, then open Workflows > hoi4_portraits."
