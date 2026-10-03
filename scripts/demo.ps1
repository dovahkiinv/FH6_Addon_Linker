# Smoke test CLI end-to-end na bezpiecznej, tymczasowej atrapce gry.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("fh6linker-demo-" + [guid]::NewGuid().ToString("N"))
$game = Join-Path $tempRoot "game"
$library = Join-Path $tempRoot "mods"
$backups = Join-Path $tempRoot "backups"
$config = Join-Path $tempRoot "config"

function Invoke-Linker([string[]]$Arguments) {
    & python -m fh6linker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "fh6linker zakończył się kodem $LASTEXITCODE"
    }
}

try {
    Set-Location $projectRoot
    $env:FH6LINKER_CONFIG_DIR = $config
    $null = New-Item -ItemType Directory -Force (Join-Path $game "media/Audio/FMODBanks")
    $null = New-Item -ItemType Directory -Force (Join-Path $library "Audio/Demo/media/Audio/FMODBanks")
    [System.IO.File]::WriteAllBytes((Join-Path $game "forzahorizon6.exe"), [System.Text.Encoding]::UTF8.GetBytes("fake game"))
    [System.IO.File]::WriteAllBytes((Join-Path $game "media/Audio/FMODBanks/engine.bank"), [System.Text.Encoding]::UTF8.GetBytes("vanilla sound"))
    [System.IO.File]::WriteAllBytes((Join-Path $library "Audio/Demo/media/Audio/FMODBanks/engine.bank"), [System.Text.Encoding]::UTF8.GetBytes("modded sound"))

    Invoke-Linker @("set", "--game", $game, "--library", $library, "--backup-dir", $backups, "--method", "auto")
    Invoke-Linker @("scan")
    Invoke-Linker @("enable", "Demo", "--dry-run")
    Invoke-Linker @("enable", "Demo")
    Invoke-Linker @("status")
    Invoke-Linker @("disable", "Demo")
    Invoke-Linker @("enable", "Demo")
    Invoke-Linker @("restore", "--yes")

    Write-Host "Demo zakończone — oryginalny plik gry został przywrócony."
}
finally {
    Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
    Remove-Item Env:FH6LINKER_CONFIG_DIR -ErrorAction SilentlyContinue
}
