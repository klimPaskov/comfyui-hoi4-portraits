param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Res4lyfUrl = "https://github.com/ClownsharkBatwing/RES4LYF.git"
$Res4lyfRevision = "e716cd1cb2c5cff90131bf4914b75b75a0489d48"
$Res4lyfDirectory = Join-Path $ComfyUIRoot "custom_nodes\RES4LYF"
$Candidates = @(
    (Join-Path $ComfyUIRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $ComfyUIRoot) "python_embeded\python.exe"),
    (Join-Path $ComfyUIRoot "python_embeded\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

New-Item -ItemType Directory -Force -Path (Join-Path $ComfyUIRoot "custom_nodes") | Out-Null
if (Test-Path (Join-Path $Res4lyfDirectory ".git")) {
    & git -C $Res4lyfDirectory fetch --depth 1 origin $Res4lyfRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (Test-Path $Res4lyfDirectory) {
    throw "$Res4lyfDirectory exists but is not a Git checkout. Move it aside, then rerun this installer."
} else {
    & git clone --filter=blob:none --no-checkout $Res4lyfUrl $Res4lyfDirectory
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & git -C $Res4lyfDirectory fetch --depth 1 origin $Res4lyfRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& git -C $Res4lyfDirectory checkout --detach $Res4lyfRevision
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m pip install -r (Join-Path $Res4lyfDirectory "requirements.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -c "import cv2, scipy" 2>$null
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

Write-Host "Installed three FLUX.2 Klein 9B workflows, the hoi4_portraits node pack, and RES4LYF samplers. Restart ComfyUI, then open Workflows > hoi4_portraits."
