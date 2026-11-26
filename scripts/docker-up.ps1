<#
.SYNOPSIS
    Starts or rebuilds MetaStudio via Docker Compose with stable port selection.
.DESCRIPTION
    Keeps MetaStudio on the same port across rebuilds/updates, and automatically advances
    to the next free port in the range ONLY when a port is occupied by another service.
#>
param(
    [int]$FrontendStart = 8080,
    [int]$FrontendEnd = 8099,
    [int]$BackendStart = 8000,
    [int]$BackendEnd = 8019,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    function Get-OwnPublishedPort([string]$Service, [int]$ContainerPort) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $raw = & docker compose port $Service $ContainerPort 2>$null
            if ($LASTEXITCODE -eq 0 -and ($raw -join "") -match ":(\d+)$") {
                return [int]$Matches[1]
            }
            return $null
        } finally {
            $ErrorActionPreference = $prev
        }
    }

    function Test-PortInUse([int]$Port) {
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
            $listener.Start()
            $listener.Stop()
        } catch {
            return $true
        }
        try {
            $listenerAny = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
            $listenerAny.Start()
            $listenerAny.Stop()
        } catch {
            return $true
        }
        return $false
    }

    function Resolve-StablePort([string]$Service, [int]$ContainerPort, [int]$StartPort, [int]$EndPort) {
        $ownPort = Get-OwnPublishedPort $Service $ContainerPort
        if ($null -ne $ownPort -and $ownPort -ge $StartPort -and $ownPort -le $EndPort) {
            return $ownPort
        }
        for ($p = $StartPort; $p -le $EndPort; $p++) {
            if (-not (Test-PortInUse $p)) {
                return $p
            }
        }
        throw "No free port found for $Service in range $StartPort-$EndPort."
    }

    function Set-EnvVar([string]$EnvPath, [string]$Key, [string]$Value) {
        if (-not (Test-Path $EnvPath)) {
            if (Test-Path (Join-Path $RepoRoot ".env.example")) {
                Copy-Item (Join-Path $RepoRoot ".env.example") $EnvPath
            } else {
                New-Item -ItemType File -Path $EnvPath | Out-Null
            }
        }
        $lines = Get-Content $EnvPath
        $found = $false
        $updated = foreach ($line in $lines) {
            if ($line -match "^$([regex]::Escape($Key))=") {
                $found = $true
                "$Key=$Value"
            } else {
                $line
            }
        }
        if (-not $found) {
            $updated += "$Key=$Value"
        }
        Set-Content -Path $EnvPath -Value $updated -Encoding UTF8
    }

    $frontendPort = Resolve-StablePort "frontend" 80 $FrontendStart $FrontendEnd
    $backendPort = Resolve-StablePort "backend" 8000 $BackendStart $BackendEnd

    $envFile = Join-Path $RepoRoot ".env"
    Set-EnvVar $envFile "FRONTEND_PORT" "$frontendPort"
    Set-EnvVar $envFile "BACKEND_HOST_PORT" "$backendPort"

    $env:FRONTEND_PORT = "$frontendPort"
    $env:BACKEND_HOST_PORT = "$backendPort"

    Write-Host "MetaStudio -> Frontend: http://localhost:$frontendPort | Backend: http://localhost:$backendPort" -ForegroundColor Green

    if ($NoBuild) {
        docker compose up -d
    } else {
        docker compose up --build -d
    }
    docker compose ps
} finally {
    Pop-Location
}
