param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [ValidateSet("local_nvidia_16gb", "full_power_gpu")]
    [string]$Profile = "local_nvidia_16gb"
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

& $Python (Join-Path $ProjectRoot "scripts\install_into_existing_comfyui.py") `
    --comfyui-root $ComfyUIRoot `
    --profile $Profile

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Installation complete. Restart ComfyUI and open Workflows > hoi4_portraits."
