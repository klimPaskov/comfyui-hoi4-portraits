param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Candidates = @(
    (Join-Path $ComfyUIRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $ComfyUIRoot) "python_embeded\python.exe"),
    (Join-Path $ComfyUIRoot "python_embeded\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

& $Python -c "import cv2, scipy" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install -r (Join-Path $ProjectRoot "custom_nodes\adaptive_portrait_crop\requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $SkipModels) {
    & $Python -c "import huggingface_hub, hf_xet" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install -r (Join-Path $ProjectRoot "scripts\requirements-download.txt")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

& $Python (Join-Path $ProjectRoot "scripts\build_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\validate_workflows.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $ProjectRoot "scripts\install_workflows.py") --comfyui-root $ComfyUIRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipModels) {
    & $Python (Join-Path $ProjectRoot "scripts\download_models.py") --comfyui-root $ComfyUIRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Installed three FLUX.2 Klein 9B workflows and the adaptive portrait crop. Restart ComfyUI, then open Workflows > hoi4_portraits."
