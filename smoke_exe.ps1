$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\AgentQAStudio.exe"
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 4
if ($p.HasExited) {
    throw "Packaged app exited unexpectedly with code $($p.ExitCode)"
}
Write-Host "PACKAGED_APP_RUNNING"
Write-Host $p.Id
Stop-Process -Id $p.Id -Force
Write-Host "PACKAGED_APP_SMOKE_OK"
