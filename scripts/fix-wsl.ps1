# Fix WSL2 / VirtualMachinePlatform for Docker Desktop (ASCII only)
# Double-click scripts\fix-wsl.cmd
# Shows RAW dism output and the final feature state - nothing is filtered.

$ErrorActionPreference = "Continue"

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[!] Need admin. Requesting elevation..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit",
        "-File", "`"$PSCommandPath`""
    )
    exit
}

Write-Host "=== Windows version ===" -ForegroundColor Cyan
Get-CimInstance Win32_OperatingSystem | ForEach-Object { Write-Host "   $($_.Caption) build $($_.BuildNumber)" }

Write-Host ""
Write-Host "=== STEP 1: enable VirtualMachinePlatform ===" -ForegroundColor Cyan
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
Write-Host ("   -> dism exit code: {0}  (0 or 3010 means ok)" -f $LASTEXITCODE) -ForegroundColor Gray

Write-Host ""
Write-Host "=== STEP 2: enable Windows Subsystem for Linux ===" -ForegroundColor Cyan
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
Write-Host ("   -> dism exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Gray

Write-Host ""
Write-Host "=== STEP 3: check feature state AFTER enabling ===" -ForegroundColor Cyan
foreach ($f in @("VirtualMachinePlatform","Microsoft-Windows-Subsystem-Linux")) {
    Write-Host "   --- $f ---"
    dism.exe /online /get-featureinfo /featurename:$f | Select-String -Pattern "State"
}

Write-Host ""
Write-Host "=== STEP 4: install WSL2 kernel (web download) ===" -ForegroundColor Cyan
wsl.exe --install --no-distribution --web-download
Write-Host ("   -> wsl exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Gray

Write-Host ""
Write-Host "=== STEP 5: update WSL ===" -ForegroundColor Cyan
wsl.exe --update --web-download
Write-Host ("   -> exit code: {0}" -f $LASTEXITCODE) -ForegroundColor Gray

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " IMPORTANT: reboot now, then run this one-liner to verify:"
Write-Host "    (Get-CimInstance Win32_ComputerSystem).HypervisorPresent"
Write-Host " It must be True. If still False, tell me the exit codes above."
Write-Host "======================================================" -ForegroundColor Green
Read-Host "Press Enter to close"
