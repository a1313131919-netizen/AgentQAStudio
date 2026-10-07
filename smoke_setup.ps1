$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\AgentQAStudio_Setup.exe"
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 4
if ($p.HasExited) {
    throw "Setup exited unexpectedly with code $($p.ExitCode)"
}
Write-Host "SETUP_RUNNING"
Stop-Process -Id $p.Id -Force
Write-Host "SETUP_SMOKE_OK"
