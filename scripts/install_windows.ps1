param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [string]$Variant = "fp8",

    [string]$GgufQuants = "Q5_K_M",

    [string]$BatchInputPath = "",

    [string]$PortraitOutputPath = "",

    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Join-Path (Split-Path -Parent $ProjectRoot) "hoi4-portraits"
if (-not $BatchInputPath) { $BatchInputPath = Join-Path $WorkspaceRoot "input" }
if (-not $PortraitOutputPath) { $PortraitOutputPath = Join-Path $WorkspaceRoot "output" }
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
    & $Python -m pip install -r (Join-Path $ProjectRoot "scripts\requirements-download.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installing the exact Adonis workflow dependencies..."
& $Python (Join-Path $ProjectRoot "scripts\install_custom_node_packs.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python (Join-Path $ProjectRoot "scripts\install_workflows.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\configure_workspace.py") --comfyui-root $ComfyUIRoot --input-dir $BatchInputPath --output-dir $PortraitOutputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-ChildItem (Join-Path $ProjectRoot "examples\batch_input") -File | ForEach-Object {
    $Destination = Join-Path $BatchInputPath $_.Name
    if (-not (Test-Path $Destination)) { Copy-Item $_.FullName $Destination }
}

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
Write-Host "Batch inputs: $BatchInputPath"
Write-Host "Portrait outputs: $PortraitOutputPath"
Write-Host "Four workflows are under user\default\workflows\hoi4_portraits. Restart ComfyUI, then open Workflows > hoi4_portraits."
