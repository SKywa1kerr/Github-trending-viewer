param(
    [string]$AppUrl = "",
    [string]$ProxyUrl = "http://127.0.0.1:7897"
)

$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$failed = 0

if ([string]::IsNullOrWhiteSpace($AppUrl)) {
    $port = "8098"
    if (Test-Path ".env") {
        foreach ($line in Get-Content ".env" -ErrorAction SilentlyContinue) {
            if ($line -match "^APP_HOST_PORT=(.+)$") {
                $port = $Matches[1].Trim()
                break
            }
        }
    }
    $AppUrl = "http://localhost:$port"
}

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail = ""
    )

    if ($Ok) {
        Write-Host "[OK]   $Name $Detail" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $Name $Detail" -ForegroundColor Red
        $script:failed += 1
    }
}

function Write-WarnCheck {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail = ""
    )

    if ($Ok) {
        Write-Host "[OK]   $Name $Detail" -ForegroundColor Green
    } else {
        Write-Host "[WARN] $Name $Detail" -ForegroundColor Yellow
    }
}

Write-Host "GitHub Trending Viewer diagnostics" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot"
Write-Host "App URL: $AppUrl"
Write-Host ""

$dockerExists = $null -ne (Get-Command "docker" -ErrorAction SilentlyContinue)
Write-Check "Docker command" $dockerExists

if ($dockerExists) {
    docker info *> $null
    Write-Check "Docker engine" ($LASTEXITCODE -eq 0)

    $composeConfig = & docker compose config --quiet 2>&1
    Write-Check "Compose config" ($LASTEXITCODE -eq 0) ($composeConfig -join " ")

    $container = (& docker ps --filter "name=github-trending" --format "{{.Names}} {{.Status}}" 2>$null) -join " "
    Write-WarnCheck "Container running" ($container -like "*github-trending*") $container
}

Write-Check ".env exists" (Test-Path ".env")
if (Test-Path ".env") {
    $envLines = Get-Content ".env" -ErrorAction SilentlyContinue
    $hasApiKey = $false
    $hasProxy = $false
    foreach ($line in $envLines) {
        if ($line -match "^API_KEY=.+") { $hasApiKey = $true }
        if ($line -match "^APP_HTTPS_PROXY=.+") { $hasProxy = $true }
    }
    Write-WarnCheck "API_KEY configured" $hasApiKey "required for translation, recommendations, and chat"
    if ($hasProxy) {
        Write-Check "App proxy configured" $true "from .env"
    } else {
        Write-Check "App proxy configured" $true "using compose default: http://host.docker.internal:7897"
    }
}

try {
    $proxyUri = [Uri]$ProxyUrl
    $proxyPort = $proxyUri.Port
    $proxyHost = $proxyUri.Host
    $proxyCheck = Test-NetConnection -ComputerName $proxyHost -Port $proxyPort -InformationLevel Quiet -WarningAction SilentlyContinue
    Write-WarnCheck "Local proxy port" $proxyCheck "$ProxyUrl"
} catch {
    Write-WarnCheck "Local proxy port" $false "$ProxyUrl could not be checked"
}

try {
    $status = Invoke-RestMethod -Uri "$AppUrl/api/status" -TimeoutSec 5
    Write-Check "App status endpoint" ($null -ne $status) "$AppUrl/api/status"
} catch {
    Write-WarnCheck "App status endpoint" $false "$AppUrl is not responding"
}

try {
    $health = Invoke-RestMethod -Uri "$AppUrl/api/health" -TimeoutSec 5
    $hasHealthStatus = $null -ne $health -and -not [string]::IsNullOrWhiteSpace([string]$health.status)
    Write-WarnCheck "App health endpoint" $hasHealthStatus "status=$($health.status)"
    if (-not $hasHealthStatus) {
        Write-Host "       - Health endpoint is missing the new response shape; run .\start.ps1 -Build" -ForegroundColor Yellow
    }
    if ($health.problems) {
        foreach ($problem in $health.problems) {
            Write-Host "       - $problem" -ForegroundColor Yellow
        }
    }
    if ($health.checks -and $health.checks.data_freshness) {
        $freshness = $health.checks.data_freshness
        Write-Host "       data latest=$($freshness.latest_fetched_at) age_hours=$($freshness.age_hours) stale_after_hours=$($freshness.stale_after_hours)" -ForegroundColor DarkGray
    }
} catch {
    Write-WarnCheck "App health endpoint" $false "$AppUrl/api/health is not responding"
}

Write-Host ""
if ($failed -gt 0) {
    Write-Host "$failed blocking check(s) failed." -ForegroundColor Red
    exit 1
}

Write-Host "Diagnostics completed." -ForegroundColor Green
exit 0
