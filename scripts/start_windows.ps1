param(
    [Parameter(Mandatory = $true)]
    [string]$ComfyUIRoot,

    [ValidateSet("human_local_nvidia_16gb", "agent_local_nvidia_16gb")]
    [string]$Workflow = "human_local_nvidia_16gb"
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

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:HOI4_PORTRAIT_PROJECT_ROOT = $ProjectRoot
$env:HOI4_SUBJECT_SERVICE_LOOPBACK = "http://127.0.0.1:8790/v1/subject"
$env:HOI4_MASK_SERVICE_LOOPBACK = "http://127.0.0.1:8790/v1/mask"
$env:HOI4_AUTOPROMPTER_LOOPBACK = "http://127.0.0.1:8099/v1/chat/completions"

$RuntimeLog = Join-Path $ProjectRoot ".runtime\logs"
New-Item -ItemType Directory -Path $RuntimeLog -Force | Out-Null

$Preprocessing = Start-Process -FilePath $Python -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RuntimeLog "preprocessing.out.log") `
    -RedirectStandardError (Join-Path $RuntimeLog "preprocessing.err.log") `
    -ArgumentList @(
        "-m", "portrait_pipeline.preprocessing_service",
        "--root", "`"$ProjectRoot`"",
        "--host", "127.0.0.1",
        "--port", "8790",
        "--device", "cuda"
    )

$Autoprompter = $null
if ($Workflow -eq "human_local_nvidia_16gb") {
    $Autoprompter = Start-Process -FilePath $Python -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $RuntimeLog "autoprompter.out.log") `
        -RedirectStandardError (Join-Path $RuntimeLog "autoprompter.err.log") `
        -ArgumentList @(
            "-m", "portrait_pipeline.autoprompter_service",
            "--root", "`"$ProjectRoot`"",
            "--profile", "human_local_nvidia_16gb",
            "--host", "127.0.0.1",
            "--port", "8099",
            "--upstream-port", "8100"
        )
}

try {
    Start-Sleep -Seconds 3
    & $Python (Join-Path $ComfyUIRoot "main.py") --listen 127.0.0.1 --port 8188
}
finally {
    if ($Autoprompter -and -not $Autoprompter.HasExited) {
        Stop-Process -Id $Autoprompter.Id
    }
    if (-not $Preprocessing.HasExited) {
        Stop-Process -Id $Preprocessing.Id
    }
}
