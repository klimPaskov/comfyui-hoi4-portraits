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
$EnhancerUrl = "https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer.git"
$EnhancerRevision = "6804643bff9a20926106427ff08d5b1bd2e49861"
$EnhancerDirectory = Join-Path $ComfyUIRoot "custom_nodes\ComfyUI-Flux2Klein-Enhancer"
$PulidUrl = "https://github.com/iFayens/ComfyUI-PuLID-Flux2.git"
$PulidRevision = "3a0a3f5f18260fc914f96a8c7f0f23c835e881cd"
$PulidDirectory = Join-Path $ComfyUIRoot "custom_nodes\ComfyUI-PuLID-Flux2"
$CompositeUrl = "https://github.com/supermansundies/comfyui-klein-edit-composite.git"
$CompositeRevision = "1505bc58d38abf5411457804ed4923e83f986eee"
$CompositeDirectory = Join-Path $ComfyUIRoot "custom_nodes\comfyui-klein-edit-composite"
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

if (Test-Path (Join-Path $EnhancerDirectory ".git")) {
    & git -C $EnhancerDirectory fetch --depth 1 origin $EnhancerRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (Test-Path $EnhancerDirectory) {
    throw "$EnhancerDirectory exists but is not a Git checkout. Move it aside, then rerun this installer."
} else {
    & git clone --filter=blob:none --no-checkout $EnhancerUrl $EnhancerDirectory
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & git -C $EnhancerDirectory fetch --depth 1 origin $EnhancerRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& git -C $EnhancerDirectory checkout --detach $EnhancerRevision
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path (Join-Path $PulidDirectory ".git")) {
    & git -C $PulidDirectory fetch --depth 1 origin $PulidRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (Test-Path $PulidDirectory) {
    throw "$PulidDirectory exists but is not a Git checkout. Move it aside, then rerun this installer."
} else {
    & git clone --filter=blob:none --no-checkout $PulidUrl $PulidDirectory
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & git -C $PulidDirectory fetch --depth 1 origin $PulidRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& git -C $PulidDirectory checkout --detach $PulidRevision
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path (Join-Path $CompositeDirectory ".git")) {
    & git -C $CompositeDirectory fetch --depth 1 origin $CompositeRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (Test-Path $CompositeDirectory) {
    throw "$CompositeDirectory exists but is not a Git checkout. Move it aside, then rerun this installer."
} else {
    & git clone --filter=blob:none --no-checkout $CompositeUrl $CompositeDirectory
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & git -C $CompositeDirectory fetch --depth 1 origin $CompositeRevision
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& git -C $CompositeDirectory checkout --detach $CompositeRevision
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$IdentityPackages = @(
    "insightface==1.0.1",
    "onnx==1.22.0",
    "onnxruntime-gpu>=1.16.0",
    "open-clip-torch==3.2.0",
    "safetensors>=0.4.0",
    "huggingface_hub>=0.34.0",
    "hf_xet>=1.1.0",
    "numpy<2.0.0",
    "ml_dtypes==0.5.4"
)
& $Python -m pip install $IdentityPackages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -c "import ml_dtypes, onnx; assert hasattr(ml_dtypes, 'float4_e2m1fn'), 'ml_dtypes is incompatible with ONNX'; print(f'Verified ONNX {onnx.__version__} with ml_dtypes {ml_dtypes.__version__}.')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -c "import onnxruntime; assert 'CUDAExecutionProvider' in onnxruntime.get_available_providers()"
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip uninstall -y onnxruntime onnxruntime-gpu
    & $Python -m pip install "onnxruntime-gpu>=1.16.0"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -c "import onnxruntime; assert 'CUDAExecutionProvider' in onnxruntime.get_available_providers(), onnxruntime.get_available_providers()"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $Python -c "from huggingface_hub import hf_hub_download; r='timm/eva02_large_patch14_clip_336.merged2b_s6b_b61k'; f='open_clip_pytorch_model.bin'; hf_hub_download(repo_id=r, filename=f, revision='4f62907359c8506be7021582f360564693b22c15'); hf_hub_download(repo_id=r, filename=f)"
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

Write-Host "Installed three primary workflows, nine identity comparison workflows, and their pinned runtime dependencies. Restart ComfyUI, then open Workflows > hoi4_portraits."
