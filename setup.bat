@echo off
echo ============================================
echo   Xiaomi Price Monitor - Setup
echo ============================================
echo.
echo Installing Python dependencies...
pip install flask requests beautifulsoup4 playwright lxml
echo.
echo Downloading Chromium browser (~150MB)...
playwright install chromium
echo.
echo ============================================
echo   Setup complete!
echo   Run the app: python app.py
echo   Or double-click: XiaomiFiyatMonitor.exe
echo ============================================
pause