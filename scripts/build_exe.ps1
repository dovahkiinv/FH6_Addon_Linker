[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "Windowsowe EXE buduj na Windowsie — PyInstaller nie kompiluje EXE dla Windows z Linuksa/macOS."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repositoryRoot
try {
    $venvPython = Join-Path $repositoryRoot ".venv-build/Scripts/python.exe"
    if (Test-Path $venvPython -PathType Leaf) {
        $python = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Nie znaleziono polecenia python. Zainstaluj Python 3.11+ i zaznacz opcję PATH."
        }
        $python = $pythonCommand.Source
    }

    & $python --version
    if ($LASTEXITCODE -ne 0) {
        throw "Nie można uruchomić Pythona."
    }
    & $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Do budowania wymagany jest Python 3.11 lub nowszy."
    }
    & $python -c "import tkinter"
    if ($LASTEXITCODE -ne 0) {
        throw "Ten Python nie zawiera tkinter/Tcl-Tk. Zainstaluj Pythona dla Windows z opcją Tcl/Tk and IDLE."
    }

    & $python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Instalacja narzędzi deweloperskich nie powiodła się."
    }

    & $python -m PyInstaller --noconfirm --clean packaging/FH6AddonLinker.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller zakończył budowanie błędem."
    }

    $executable = Join-Path $repositoryRoot "dist/FH6AddonLinker.exe"
    if (-not (Test-Path $executable -PathType Leaf)) {
        throw "Budowanie zakończyło się bez oczekiwanego pliku: $executable"
    }

    Write-Host "Gotowe: $executable" -ForegroundColor Green
    Write-Host "To samodzielny plik GUI; na komputerze docelowym nie trzeba instalować Pythona."
    Write-Host "Ustawienia i kopie oryginałów są przechowywane poza EXE w profilu użytkownika."
}
finally {
    Pop-Location
}
