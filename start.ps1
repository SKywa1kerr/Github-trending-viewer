param(
    [switch]$Build,
    [switch]$NoOpen,
    [switch]$Doctor,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Test-Command($Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)

    $dockerArgs = @("compose") + $Arguments
    & docker @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Get-AppUrl {
    $port = "8098"
    if (Test-Path ".env") {
        foreach ($line in Get-Content ".env" -ErrorAction SilentlyContinue) {
            if ($line -match "^APP_HOST_PORT=(.+)$") {
                $port = $Matches[1].Trim()
                break
            }
        }
    }
    return "http://localhost:$port"
}

if ($Doctor) {
    & (Join-Path $ProjectRoot "doctor.ps1")
    exit $LASTEXITCODE
}

if ($Logs) {
    Invoke-DockerCompose -Arguments @("logs", "-f", "github-trending")
    exit $LASTEXITCODE
}

function Wait-ForDocker {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    try {
        docker info *> $null
        return
    } catch {
        if (Test-Path $dockerDesktop) {
            Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
        } else {
            throw "Docker is not running and Docker Desktop was not found."
        }
    }

    for ($i = 0; $i -lt 150; $i++) {
        Start-Sleep -Seconds 2
        try {
            docker info *> $null
            return
        } catch {
            continue
        }
    }

    throw "Timed out waiting for Docker to start."
}

function Wait-ForService {
    $appUrl = Get-AppUrl
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $response = Invoke-RestMethod -Uri "$appUrl/api/status" -TimeoutSec 3
            if ($null -ne $response) {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "Timed out waiting for $appUrl."
}

if (-not (Test-Path ".env")) {
    @'
GITHUB_TOKEN=
GITHUB_TIMEOUT_SECONDS=30
GITHUB_MAX_RETRIES=3
GITHUB_BACKOFF_SECONDS=1
API_ENDPOINT=https://models.sjtu.edu.cn/api/v1/chat/completions
API_KEY=
API_MODEL=qwen
UPDATE_HOUR=8
APP_HOST_PORT=8098
APP_HTTP_PROXY=http://host.docker.internal:7897
APP_HTTPS_PROXY=http://host.docker.internal:7897
APP_NO_PROXY=localhost,127.0.0.1
'@ | Set-Content -Path ".env" -Encoding UTF8
    Write-Warning ".env was created with empty API_KEY. Fill it in before using translation, recommendations, or chat."
}

if (-not (Test-Command "docker")) {
    throw "Docker command was not found. Install Docker Desktop first."
}

Wait-ForDocker

$composeArgs = @("up", "-d")
if ($Build) {
    $composeArgs += "--build"
}

Invoke-DockerCompose -Arguments $composeArgs
Wait-ForService

if (-not $NoOpen) {
    $appUrl = Get-AppUrl
    $edge = Get-Command "msedge" -ErrorAction SilentlyContinue
    if ($edge) {
        Start-Process -FilePath $edge.Source -ArgumentList "--app=$appUrl", "--window-size=1200,800"
    } else {
        Start-Process $appUrl
    }
}

Write-Host "GitHub Trending Viewer is running at $(Get-AppUrl)"
