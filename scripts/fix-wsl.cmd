@echo off
REM Double-click to fix WSL2 (UAC will be requested)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0fix-wsl.ps1\"'"
