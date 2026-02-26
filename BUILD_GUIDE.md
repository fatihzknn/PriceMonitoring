# Xiaomi Price Monitor — Build & Distribution Guide

## Quick Start (for yourself)

```bash
pip install flask requests beautifulsoup4 playwright lxml
playwright install chromium
python app.py
```

Open `http://localhost:8080` in your browser. The app opens automatically.

---

## Sharing with Others — Two Options

### Option A: Send the folder (recommended)

**Step 1 — Build the executable on your machine:**
```bash
pip install pyinstaller
pyinstaller app.py --onedir --name XiaomiFiyatMonitor --add-data "dashboard.html;."
```

**Step 2 — Zip and send:**
Zip the entire `dist/XiaomiFiyatMonitor/` folder and send it.

**Recipient's one-time setup (run `setup.bat`):**
```
setup.bat
```
That's it. After setup they just double-click `XiaomiFiyatMonitor.exe`.

---

### Option B: Send the source files

Send these files:
```
app.py
scraper.py
dashboard.html
requirements.txt
setup.bat
```

Recipient runs `setup.bat` once, then `python app.py`.

---

## What recipients need (handled by setup.bat)

- Python 3.10+
- `pip install flask requests beautifulsoup4 playwright lxml`
- `playwright install chromium` — downloads Chromium (~150MB, one-time)

---

## Port

The app runs on **port 8080** by default.  
To change it, edit `app.py` line: `PORT = 8080`

---

## File structure

```
XiaomiFiyatMonitor/
├── app.py            → Flask server
├── scraper.py        → Akakce scraper (Playwright)
├── dashboard.html    → Web UI (same folder as app.py)
├── setup.bat         → One-click dependency installer
├── prices.json       → Price history (auto-created)
└── watched.json      → Watchlist (auto-created)
```

> `prices.json` and `watched.json` are created automatically on first run.  
> Delete them to reset all data.

---

## Troubleshooting

**"Port already in use"** → Change `PORT = 8080` in `app.py` to another port (e.g. `8090`)

**"No results found" when searching** → Akakce may have updated their HTML structure. The scraper uses CSS selectors that may need updating — open a browser, inspect the Akakce search page, and update selectors in `scraper.py`.

**Prices show as "Not scanned yet"** → Click the **Scan** button on the card, or **Scan All** at the top. First scan takes ~30s per product (Playwright opens a real browser).

**App doesn't open in browser** → Manually go to `http://localhost:8080`
