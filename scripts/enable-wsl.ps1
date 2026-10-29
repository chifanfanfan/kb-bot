# Enable WSL2 for Docker Desktop (pure ASCII)
# Run by double-clicking scripts\enable-wsl.cmd  (UAC will be requested)
# Reboot is required afterwards.

$ErrorActionPreference = "Continue"

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Requesting administrator privileges..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit",
        "-File", "`"$PSCommandPath`""
    )
    exit
}

Write-Host "== 1/4: enable Windows features ==" -ForegroundColor Cyan
$features = @("Microsoft-Windows-Subsystem-Linux", "VirtualMachinePlatform")
foreach ($f in $features) {
    Write-Host "   enabling $f ..."
    $out = dism.exe /online /enable-feature /featurename:$f /all /norestart 2>&1
    $code = $LASTEXITCODE
    Write-Host ("   exit code: {0}" -f $code) -ForegroundColor Gray
    if ($code -ne 0 -and $code -ne 3010) {
        Write-Host "   [!] dism failed for $f" -ForegroundColor Red
        $out | Select-Object -Last 5 | ForEach-Object { Write-Host "       $_" }
    }
}

Write-Host ""
Write-Host "== 2/4: install the WSL2 kernel ==" -ForegroundColor Cyan
wsl.exe --install --no-distribution 2>&1 | Select-Object -Last 8 | ForEach-Object { Write-Host "   $_" }
Write-Host ("   wsl exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Gray

Write-Host ""
Write-Host "== 3/4: set WSL default version to 2 ==" -ForegroundColor Cyan
wsl.exe --set-default-version 2 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "   $_" }

Write-Host ""
Write-Host "== 4/4: current status ==" -ForegroundColor Cyan
wsl.exe --status 2>&1 | Select-Object -First 6 | ForEach-Object { Write-Host "   $_" }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " NEXT: reboot Windows, then start Docker Desktop." -ForegroundColor Green
Write-Host " After reboot run:  wsl --status     (should say version 2)"
Write-Host " Then:              docker version"
Write-Host "==================================================" -ForegroundColor Green
Read-Host "Press Enter to close"
