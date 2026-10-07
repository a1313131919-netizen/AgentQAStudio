$ErrorActionPreference = "Stop"
$p = Start-Process -FilePath ".\dist\AgentQAStudio.exe" -ArgumentList "--self-test-browser" -Wait -PassThru
Write-Host ("BROWSER_SELF_TEST_EXIT=" + $p.ExitCode)
if ($p.ExitCode -ne 0) {
    exit $p.ExitCode
}
Write-Host "PACKAGED_BROWSER_AUTO_OK"
