@echo off
chcp 65001 >nul
title AI-consultant bot
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
C:\dtemp\venv\Scripts\python.exe scripts\run_local.py
pause
