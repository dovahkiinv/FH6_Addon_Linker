[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "Build the Windows executable on Windows; PyInstaller cannot cross-compile from Linux or macOS."
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
            throw "Python was not found. Install Python 3.11 or newer and add it to PATH."
        }
        $python = $pythonCommand.Source
    }

    & $python --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python could not be started."
    }

    & $python -c 'import sys; sys.exit(sys.version_info < (3, 11))'
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 or newer is required to build the executable."
    }

    & $python -c 'import tkinter'
    if ($LASTEXITCODE -ne 0) {
        throw "This Python installation does not include tkinter/Tcl-Tk. Install Python for Windows with Tcl/Tk support."
    }

    & $python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Installing the build requirements failed."
    }

    & $python -m PyInstaller --noconfirm --clean packaging/FH6AddonLinker.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build the executable."
    }

    $executable = Join-Path $repositoryRoot "dist/FH6AddonLinker.exe"
    if (-not (Test-Path $executable -PathType Leaf)) {
        throw "The expected executable was not created: $executable"
    }

    Write-Host "Build complete: $executable" -ForegroundColor Green
    Write-Host "The GUI is standalone; Python is not required on the target computer."
    Write-Host "Settings and original-file backups are stored outside the EXE in the user profile."
}
finally {
    Pop-Location
}
