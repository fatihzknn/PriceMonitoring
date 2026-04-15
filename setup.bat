@echo off
title Xiaomi Price Monitor - Kurulum
cd /d "%~dp0"
color 0A
echo.
echo  ============================================
echo   Xiaomi Price Monitor - Kurulum
echo  ============================================
echo.

:: Python var mi kontrol et
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python bulunamadi. Indiriliyor...
    echo.
    winget install Python.Python.3.11 -e --silent
    if %errorlevel% neq 0 (
        echo.
        echo  [HATA] Python kurulamadi!
        echo  Lutfen https://python.org adresinden manuel kurun.
        echo  Kurulum sirasinda "Add Python to PATH" kutusunu isaretleyin!
        pause
        exit /b 1
    )
    echo  [OK] Python kuruldu.
) else (
    echo  [OK] Python mevcut.
)

echo.
echo  [*] Gerekli paketler kuruluyor...
py -m pip install --upgrade pip -q
py -m pip install flask requests beautifulsoup4 playwright lxml playwright-stealth -q
if %errorlevel% neq 0 (
    echo  [HATA] Paketler kurulamadi!
    pause
    exit /b 1
)
echo  [OK] Paketler kuruldu.

echo.
echo  [*] Chromium indiriliyor (ilk kurulum ~150MB)...
py -m playwright install chromium
if %errorlevel% neq 0 (
    echo  [HATA] Chromium kurulamadi!
    pause
    exit /b 1
)
echo  [OK] Chromium kuruldu.

echo.
echo  ============================================
echo   Kurulum tamamlandi!
echo   Uygulamayi baslatmak icin START.bat kullan
echo  ============================================
echo.
pause
