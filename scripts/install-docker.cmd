@echo off
REM 双击本文件即可安装 Docker Desktop（会弹 UAC 要求管理员权限）
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0install-docker.ps1\"'"
