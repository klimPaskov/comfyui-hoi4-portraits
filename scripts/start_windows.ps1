param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot
)

$ErrorActionPreference = "Stop"
$PortableRoot = Split-Path -Parent $ComfyUIRoot
$AmdLauncher = Join-Path $PortableRoot "run_amd_gpu.bat"
if (Test-Path $AmdLauncher) {
    Push-Location $PortableRoot
    try {
        & $AmdLauncher
        exit $LASTEXITCODE
    } finally {
        Pop-Location
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

Push-Location $ComfyUIRoot
try {
    & $Python "main.py"
} finally {
    Pop-Location
}
