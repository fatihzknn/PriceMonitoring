#!/bin/bash
cd "$(dirname "$0")"
echo ""
echo "============================================"
echo " Xiaomi Price Monitor - Kurulum (Mac/Linux)"
echo "============================================"
echo ""

# Python kontrolu
if ! command -v python3 &> /dev/null; then
    echo "[!] Python bulunamadi. Homebrew ile kuruluyor..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    brew install python3
fi
echo "[OK] Python mevcut: $(python3 --version)"

echo ""
echo "[*] Paketler kuruluyor..."
python3 -m pip install --upgrade pip -q
python3 -m pip install flask requests beautifulsoup4 playwright lxml playwright-stealth -q
echo "[OK] Paketler kuruldu."

echo ""
echo "[*] Chromium indiriliyor (~150MB)..."
python3 -m playwright install chromium
echo "[OK] Chromium kuruldu."

echo ""
echo "============================================"
echo " Kurulum tamamlandi!"
echo " Baslatmak icin: bash START.sh"
echo "============================================"
echo ""
