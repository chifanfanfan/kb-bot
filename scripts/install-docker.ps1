# Install Docker Desktop (pure ASCII to avoid PowerShell 5.1 encoding issues)
#
# Usage: double-click scripts\install-docker.cmd
#   or: powershell -ExecutionPolicy Bypass -File scripts\install-docker.ps1

$ErrorActionPreference = "Continue"
$installer = Join-Path $env:USERPROFILE "Downloads\DockerDesktopInstaller.exe"

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

Write-Host "== Step 1/3: check installer ==" -ForegroundColor Cyan
if (-not (Test-Path $installer)) {
    Write-Host "[X] Not found: $installer" -ForegroundColor Red
    Write-Host "    Put DockerDesktopInstaller.exe into your Downloads folder first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
$sizeMB = [math]::Round((Get-Item $installer).Length / 1MB)
Write-Host ("    {0}  ({1} MB)" -f $installer, $sizeMB) -ForegroundColor Gray

Write-Host ""
Write-Host "== Step 2/3: enable WSL + VirtualMachinePlatform ==" -ForegroundColor Cyan
Write-Host "    [feature] Microsoft-Windows-Subsystem-Linux"
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Select-String "success|error|complete"
Write-Host "    [feature] VirtualMachinePlatform"
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Select-String "success|error|complete"

Write-Host ""
Write-Host "== Step 3/3: install Docker Desktop (1-3 minutes, no window) ==" -ForegroundColor Cyan
$proc = Start-Process -FilePath $installer -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
Write-Host ("    Installer exit code: {0}   (0 = success)" -f $proc.ExitCode) -ForegroundColor Gray

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " NEXT STEPS" -ForegroundColor Green
Write-Host "   1) Reboot Windows"
Write-Host "   2) Start 'Docker Desktop' from the Start menu"
Write-Host "      wait until the whale icon turns green"
Write-Host "   3) Then run in the project folder:"
Write-Host "        docker build -t kb-bot ."
Write-Host "        docker run -p 8000:8000 kb-bot"
Write-Host ""
Write-Host " If Docker says virtualization is disabled:" -ForegroundColor Yellow
Write-Host "   enable Intel VT-x / AMD-V in BIOS."
Write-Host "==================================================" -ForegroundColor Green
Read-Host "Press Enter to close"
