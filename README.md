# 📱 Xiaomi Price Monitor

A system that automatically tracks **Xiaomi product prices** from **Akakce** and visualizes them through a real-time web dashboard.

---

## 🚀 Installation (3 Steps)

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Run a manual scrape once

```bash
python scraper.py
```

### 3. Start the dashboard

```bash
python app.py
```

Open in your browser: **[http://localhost:5000](http://localhost:5000)**

---

## 📦 Project Structure

```
xiaomi-monitor/
├── app.py           → Flask web server (dashboard backend)
├── scraper.py       → Akakce scraper
├── requirements.txt → Python dependencies
├── prices.json      → Price database (auto-generated)
└── templates/
    └── dashboard.html → Visual dashboard
```

---

## ⚙️ Configuration

### Change scraping interval

Modify the `SCRAPE_INTERVAL` value in `app.py` (in seconds):

```python
SCRAPE_INTERVAL = 300   # 5 minutes (default)
SCRAPE_INTERVAL = 600   # 10 minutes
SCRAPE_INTERVAL = 3600  # 1 hour
```

---

### Add a new product

Add a new item to the `PRODUCTS` list in `scraper.py`:

```python
{
    "name": "Xiaomi 13T",
    "url": "https://www.akakce.com/cep-telefonu/en-ucuz-xiaomi-13t-fiyati,...html",
    "image": ""  # can be left empty
},
```

---

## 🖥️ Dashboard Features

* **Live price tracking** – Automatically refreshes every 30 seconds
* **Price history chart** – Historical price graph for each product
* **Change indicator** – Green for price drops, red for price increases
* **Manual scraping** – Instantly update prices with the "SCAN" button
* **Direct Akakce link** – Navigate directly to the product page

---

## ⚠️ Important Notes

* If Akakce changes its website structure, you may need to update the CSS selectors inside `scraper.py`.
* Scraping too frequently may result in IP blocking — 5+ minutes is recommended.
* Prices accumulate in the `prices.json` file. If deleted, price history will reset.

---

## 🔧 Troubleshooting

### “Price not found” error

* Check the Akakce product URL — does the page actually display a price?
* If the site structure changed:

  * Open the product page in your browser
  * Right-click the price → **Inspect**
  * Find the correct CSS selector and update it inside `scraper.py`

---

### Port 5000 already in use

Change the `port=5000` value at the bottom of `app.py` to:

```python
port=5001
```

---

*Xiaomi Price Monitor — Automated price tracking system*
