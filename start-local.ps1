# Runs the app directly with Python and translates with the local Ollama model (no Docker).
# start.ps1 remains the Docker entry point; do not run both at once (same port and database).
param(
    [switch]$NoOpen,
    [switch]$Stop,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PidFile = Join-Path $ProjectRoot "data\local-server.pid"
$LogFile = Join-Path $ProjectRoot "data\local-server.log"

# .env values become process variables; anything already set in the environment wins.
$dotenv = @{}
if (Test-Path ".env") {
    foreach ($line in Get-Content ".env") {
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$") { $dotenv[$Matches[1]] = $Matches[2].Trim() }
    }
}
function Set-Default($Name, $Value) {
    if ([Environment]::GetEnvironmentVariable($Name, "Process")) { return }
    if ($dotenv.ContainsKey($Name) -and $dotenv[$Name]) { $Value = $dotenv[$Name] }
    if ($Value) { [Environment]::SetEnvironmentVariable($Name, $Value, "Process") }
}

$port = if ($dotenv["APP_HOST_PORT"]) { $dotenv["APP_HOST_PORT"] } else { "8098" }
$appUrl = "http://127.0.0.1:$port"

function Test-App {
    try { return $null -ne (Invoke-RestMethod -Uri "$appUrl/api/status" -TimeoutSec 3) } catch { return $false }
}
function Test-Ollama {
    try { return $null -ne (Invoke-RestMethod -Uri "$env:OLLAMA_BASE_URL/api/version" -TimeoutSec 2) } catch { return $false }
}
function Open-App {
    if ($NoOpen) { return }
    $edge = Get-Command "msedge" -ErrorAction SilentlyContinue
    if ($edge) { Start-Process -FilePath $edge.Source -ArgumentList "--app=$appUrl", "--window-size=1280,860" }
    else { Start-Process $appUrl }
}

if ($Stop) {
    if (Test-Path $PidFile) {
        $serverPid = [int](Get-Content $PidFile)
        & taskkill /PID $serverPid /T /F 2>$null | Out-Null
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Stopped."
    } else { Write-Host "Not running (no pid file)." }
    exit 0
}
if ($Logs) { Get-Content $LogFile -Tail 40 -Wait; exit 0 }

foreach ($name in $dotenv.Keys) { Set-Default $name $null }
Set-Default "TRANSLATION_PROVIDER" "ollama"
Set-Default "OLLAMA_BASE_URL" "http://127.0.0.1:11434"
Set-Default "OLLAMA_MODEL" "qwen3:8b"
# GitHub and the remote chat API keep the proxy the Docker setup used. Ollama calls never use it.
if (-not $env:HTTPS_PROXY) {
    $proxy = if ($dotenv["APP_HTTPS_PROXY"]) { $dotenv["APP_HTTPS_PROXY"] } else { "http://127.0.0.1:7897" }
    $env:HTTPS_PROXY = $proxy -replace "host\.docker\.internal", "127.0.0.1"
    $env:HTTP_PROXY = $env:HTTPS_PROXY
}
$env:NO_PROXY = "localhost,127.0.0.1"

if (Test-App) { Open-App; Write-Host "Already running at $appUrl"; exit 0 }

# Ollama's tray app normally starts the server with Windows; start the server ourselves otherwise.
if ($env:TRANSLATION_PROVIDER -eq "ollama" -and -not (Test-Ollama)) {
    $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $ollama) {
        # The model server must not inherit the proxy, or model pulls would go through it.
        $saved = $env:HTTPS_PROXY, $env:HTTP_PROXY
        $env:HTTPS_PROXY = $null; $env:HTTP_PROXY = $null; $env:OLLAMA_NUM_PARALLEL = "1"
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
        $env:HTTPS_PROXY, $env:HTTP_PROXY = $saved
        for ($i = 0; $i -lt 20 -and -not (Test-Ollama); $i++) { Start-Sleep -Seconds 1 }
    }
    if (-not (Test-Ollama)) { Write-Warning "Ollama is not reachable; translation will retry later." }
}

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "data") | Out-Null
$server = Start-Process -FilePath "python" -WindowStyle Hidden -PassThru `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $port `
    -RedirectStandardError $LogFile -RedirectStandardOutput "$LogFile.out"
Set-Content -Path $PidFile -Value $server.Id

for ($i = 0; $i -lt 30 -and -not (Test-App); $i++) { Start-Sleep -Seconds 1 }
if (-not (Test-App)) { throw "The app did not start. See $LogFile" }
Open-App
Write-Host "GitHub Trending Viewer is running at $appUrl (local translation: $env:OLLAMA_MODEL)"
