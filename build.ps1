$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$cache = "D:\OpenMCP\cache\pip"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$env:PIP_CACHE_DIR = $cache

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt

if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --hidden-import "playwright.sync_api" --collect-all "playwright" --name "AgentQAStudio" "app.py"
if (-not (Test-Path "dist\AgentQAStudio.exe")) { throw "AgentQAStudio.exe build failed" }

& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "AgentQAStudio_Setup" --add-data "dist\AgentQAStudio.exe;." "setup_installer.py"
if (-not (Test-Path "dist\AgentQAStudio_Setup.exe")) { throw "AgentQAStudio_Setup.exe build failed" }

Write-Host "BUILD_OK"
Write-Host (Resolve-Path "dist\AgentQAStudio.exe")
Write-Host (Resolve-Path "dist\AgentQAStudio_Setup.exe")
