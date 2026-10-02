<#
.SYNOPSIS
  Gestión local de PriceHunt en Windows.
.EXAMPLE
  .\scripts\pricehunt.ps1 up
  .\scripts\pricehunt.ps1 demo
  .\scripts\pricehunt.ps1 monitoring
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "demo", "down", "logs", "ps", "test", "lint", "monitoring", "tools", "refresh", "reset", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-Docker {
    # En PowerShell 5.1, con "Stop" el stderr de un comando nativo lanza una excepción
    $ErrorActionPreference = "Continue"
    docker info --format '{{.ServerVersion}}' *> $null
    return $LASTEXITCODE -eq 0
}

function Assert-Docker {
    if (-not (Test-Docker)) {
        Write-Host "Docker no responde. Arrancando Docker Desktop..." -ForegroundColor Yellow
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep 3
            if (Test-Docker) { return }
        }
        throw "Docker no arrancó a tiempo"
    }
}

function Show-Urls {
    Write-Host ""
    Write-Host "  Web       http://localhost:8080" -ForegroundColor Green
    Write-Host "  API docs  http://localhost:8000/docs"
    Write-Host "  Métricas  http://localhost:8000/metrics/"
    Write-Host ""
}

switch ($Command) {
    "up" {
        Assert-Docker
        if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Creado .env desde .env.example" }
        docker compose up -d --build --wait
        Show-Urls
    }
    "demo" {
        Assert-Docker
        $env:DEMO_MODE = "true"
        docker compose up -d --build --wait
        Remove-Item Env:DEMO_MODE
        Show-Urls
    }
    "down" { docker compose down }
    "logs" { docker compose logs -f api }
    "ps" { docker compose ps }
    "test" {
        Push-Location backend
        if (-not (Test-Path .venv)) {
            python -m venv .venv
            .\.venv\Scripts\python -m pip install -q -r requirements-dev.txt
        }
        .\.venv\Scripts\python -m pytest
        Pop-Location
    }
    "lint" {
        Push-Location backend
        .\.venv\Scripts\ruff check .
        .\.venv\Scripts\ruff format --check .
        Pop-Location
    }
    "monitoring" {
        Assert-Docker
        docker compose --profile monitoring up -d
        Write-Host "  Grafana     http://localhost:3000" -ForegroundColor Green
        Write-Host "  Prometheus  http://localhost:9090"
    }
    "tools" {
        Assert-Docker
        docker compose --profile tools up -d
        Write-Host "  Adminer  http://localhost:8081  (servidor: db, usuario/clave: pricehunt)" -ForegroundColor Green
    }
    "refresh" { Invoke-RestMethod -Method Post http://localhost:8000/api/refresh }
    "reset" {
        $ok = Read-Host "Esto BORRA la base de datos. Escribe 'si' para continuar"
        if ($ok -eq "si") { docker compose down -v }
    }
    default {
        Get-Help $PSCommandPath -Examples
        Write-Host "Comandos: up | demo | down | logs | ps | test | lint | monitoring | tools | refresh | reset"
    }
}
