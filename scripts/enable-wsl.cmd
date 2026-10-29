@echo off
REM Double-click to enable WSL2 for Docker Desktop (UAC will be requested)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0enable-wsl.ps1\"'"
