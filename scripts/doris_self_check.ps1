param(
  [string]$ProjectName = "sga-tablesis",
  [string]$WorkDir = "E:\sga-tablesis",
  [string]$ComposeFile = "docker-compose.yml",
  [string]$NetworkName = "sga-tablesis_doris-network",
  [string]$Subnet = "172.28.0.0/24",
  [string]$IpRange = "172.28.0.128/25",
  [int]$HealthTimeoutSec = 300
)

$ErrorActionPreference = "Stop"

function Test-Docker {
  try {
    docker info *> $null
    return $true
  } catch {
    Write-Host "Docker is not ready. Start Docker Desktop and retry." -ForegroundColor Red
    return $false
  }
}

function Get-NetworkConfig {
  try {
    $json = docker network inspect $NetworkName | ConvertFrom-Json
    return $json[0]
  } catch {
    return $null
  }
}

function Network-NeedsFix {
  param($net)
  if (-not $net) { return $true }
  $cfg = $net.IPAM.Config | Select-Object -First 1
  if (-not $cfg) { return $true }
  if ($cfg.Subnet -ne $Subnet) { return $true }
  if ($cfg.IPRange -ne $IpRange) { return $true }
  return $false
}

function Compose-DownUp {
  $composePath = Join-Path $WorkDir $ComposeFile
  if (-not (Test-Path $composePath)) {
    throw "Compose file not found: $composePath"
  }
  docker compose -p $ProjectName -f $composePath down | Out-Host
  docker compose -p $ProjectName -f $composePath up -d | Out-Host
}

function Ensure-Started {
  param([string[]]$Names)
  foreach ($n in $Names) {
    try {
      $state = docker inspect $n --format "{{.State.Status}}" 2>$null
      if ($state -in @("created","exited")) {
        docker start $n | Out-Host
      }
    } catch {
      # ignore if container missing
    }
  }
}

function Wait-Healthy {
  param(
    [string]$Name,
    [int]$TimeoutSec
  )
  $start = Get-Date
  while ((Get-Date) -lt $start.AddSeconds($TimeoutSec)) {
    try {
      $health = docker inspect $Name --format "{{.State.Health.Status}}" 2>$null
      if ($health -eq "healthy") { return $true }
      if (-not $health) {
        # no healthcheck, treat as running
        $status = docker inspect $Name --format "{{.State.Status}}" 2>$null
        if ($status -eq "running") { return $true }
      }
    } catch {
      # ignore transient errors
    }
    Start-Sleep -Seconds 3
  }
  return $false
}

if (-not (Test-Docker)) { exit 1 }

$net = Get-NetworkConfig
if (Network-NeedsFix $net) {
  Write-Host "Fixing docker network IP range..." -ForegroundColor Yellow
  Compose-DownUp
} else {
  $composePath = Join-Path $WorkDir $ComposeFile
  docker compose -p $ProjectName -f $composePath up -d | Out-Host
}

Ensure-Started -Names @("doris-fe","doris-be","doris-api","doris-frontend")

$okFe = Wait-Healthy -Name "doris-fe" -TimeoutSec $HealthTimeoutSec
$okBe = Wait-Healthy -Name "doris-be" -TimeoutSec $HealthTimeoutSec

if (-not $okFe -or -not $okBe) {
  Write-Host "Doris FE/BE did not become healthy in time." -ForegroundColor Red
  try { docker logs --tail 120 doris-fe | Out-Host } catch {}
  try { docker logs --tail 120 doris-be | Out-Host } catch {}
  exit 2
}

Write-Host "Doris self-check complete. FE/BE are healthy." -ForegroundColor Green
