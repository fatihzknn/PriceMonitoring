@echo off
title Xiaomi Price Monitor
cd /d "%~dp0"

:: Python kontrolu
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python bulunamadi! Once SETUP.bat calistirin.
    pause
    exit /b 1
)

:: Uygulama basliyor
start "" http://localhost:8080
py app.py
