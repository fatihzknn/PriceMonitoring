"""
Xiaomi Fiyat Monitor - Backend v4
Port: 8080
Durdurma/başlatma desteği eklendi.
"""

from flask import Flask, jsonify, send_from_directory, request
import json, os, threading, time, sys
from datetime import datetime
from scraper import (
    search_akakce, scrape_product_channels, scrape_watched_products,
    load_data, save_data, load_watched, save_watched, DATA_FILE, WATCHED_FILE
)

# PyInstaller exe içinde çalışırken dosya yolu
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

PORT = 8080
SCRAPE_INTERVAL = 300  # 5 dakika

_scraping = False
_stop_requested = False   # Durdurma bayrağı
_auto_enabled = True      # Otomatik tarama açık/kapalı
_last_scrape = None
_scrape_lock = threading.Lock()


def background_scraper():
    global _scraping, _last_scrape, _stop_requested
    while True:
        time.sleep(10)  # Her 10 saniyede kontrol et
        if not _auto_enabled:
            continue
        # Son taramadan bu yana SCRAPE_INTERVAL geçti mi?
        if _last_scrape:
            elapsed = (datetime.now() - datetime.fromisoformat(_last_scrape)).total_seconds()
            if elapsed < SCRAPE_INTERVAL:
                continue
        else:
            # İlk başlatmada 30 sn bekle
            time.sleep(30)

        watched = load_watched()
        if not watched or not _auto_enabled:
            continue

        with _scrape_lock:
            _stop_requested = False
            _scraping = True
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Otomatik tarama başlıyor...")
            scrape_watched_products(stop_flag=lambda: _stop_requested)
            _scraping = False
            _last_scrape = datetime.now().isoformat()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Tarama tamamlandı.")


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "error": "Arama terimi gerekli"})
    results = search_akakce(q)
    return jsonify({"results": results, "query": q})


@app.route("/api/watched", methods=["GET"])
def api_watched_get():
    return jsonify(load_watched())


@app.route("/api/watched", methods=["POST"])
def api_watched_add():
    body = request.json or {}
    watched = load_watched()
    existing_ids = {w["id"] for w in watched}
    pid = body.get("id", "")
    if not pid:
        import hashlib
        pid = hashlib.md5(body.get("url","").encode()).hexdigest()[:10]
    if pid in existing_ids:
        return jsonify({"status": "exists", "message": "Ürün zaten listede"})
    product_name = body.get("name", "")
    watched.append({
        "id": pid,
        "name": product_name,
        "url": body.get("url", ""),
        "image": body.get("image", ""),
        "added_at": datetime.now().isoformat(),
    })
    save_watched(watched)

    # Auto-assign RRP as target price if not already set
    targets = load_targets()
    if pid not in targets:
        rrp = find_rrp_for_product(product_name)
        if rrp:
            targets[pid] = rrp
            save_targets(targets)
            print(f"  [RRP] Auto-assigned {rrp:,} TL to '{product_name}'")

    return jsonify({"status": "ok", "id": pid, "rrp_assigned": pid in load_targets()})


@app.route("/api/watched/<pid>", methods=["DELETE"])
def api_watched_delete(pid):
    watched = [w for w in load_watched() if w["id"] != pid]
    save_watched(watched)
    data = load_data()
    data.pop(pid, None)
    save_data(data)
    return jsonify({"status": "ok"})


@app.route("/api/prices")
def api_prices():
    try:
        data = load_data()
        watched = load_watched()
    except:
        data, watched = {}, []

    result = []
    for w in watched:
        pid = w["id"]
        pdata = data.get(pid, {})
        channels = pdata.get("channels", [])
        history = pdata.get("history", [])
        min_price = min((c["price"] for c in channels if c.get("price")), default=None)
        max_price = max((c["price"] for c in channels if c.get("price")), default=None)
        change = change_pct = None
        valid = [h for h in history if h.get("price")]
        if len(valid) >= 2:
            prev, curr = valid[-2]["price"], valid[-1]["price"]
            if prev and curr:
                change = round(curr - prev, 2)
                change_pct = round((change / prev) * 100, 2)
        result.append({
            "id": pid, "name": w["name"], "url": w["url"], "image": w.get("image",""),
            "channels": channels, "min_price": min_price, "max_price": max_price,
            "channel_count": len(channels), "history": history[-30:],
            "last_updated": pdata.get("last_updated"),
            "change": change, "change_pct": change_pct,
        })

    targets = load_targets()
    rrp_map = load_rrp()
    for p in result:
        p["target_price"] = targets.get(p["id"])
        # Also expose whether this came from RRP
        p["has_rrp"] = p["target_price"] is not None

    return jsonify({
        "products": result,
        "scraping": _scraping,
        "auto_enabled": _auto_enabled,
        "last_scrape": _last_scrape,
        "interval_minutes": SCRAPE_INTERVAL // 60,
    })


@app.route("/api/scrape/all", methods=["POST"])
def api_scrape_all():
    global _scraping, _last_scrape, _stop_requested
    if _scraping:
        return jsonify({"status": "busy"}), 409

    def run():
        global _scraping, _last_scrape, _stop_requested
        with _scrape_lock:
            _stop_requested = False
            _scraping = True
            # Snapshot prices before scrape for alert comparison
            old_data = load_data()
            old_prices = {pid: (
                max((h["price"] for h in pdata.get("history", []) if h.get("price")), default=None)
                if pdata.get("history") else None
            ) for pid, pdata in old_data.items()}

            scrape_watched_products(stop_flag=lambda: _stop_requested)

            # Check alerts after scrape
            new_data = load_data()
            targets = load_targets()
            for pid, pdata in new_data.items():
                history = [h["price"] for h in pdata.get("history", []) if h.get("price")]
                if not history:
                    continue
                new_price = history[-1]
                old_price = old_prices.get(pid)
                target = targets.get(pid)
                check_and_alert(pid, pdata.get("name", pid), old_price, new_price, target)

            _scraping = False
            _last_scrape = datetime.now().isoformat()

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "ok"})


@app.route("/api/scrape/stop", methods=["POST"])
def api_scrape_stop():
    global _stop_requested
    _stop_requested = True
    return jsonify({"status": "ok", "message": "Durdurma isteği gönderildi"})


@app.route("/api/auto", methods=["POST"])
def api_auto_toggle():
    global _auto_enabled
    body = request.json or {}
    _auto_enabled = body.get("enabled", not _auto_enabled)
    return jsonify({"status": "ok", "auto_enabled": _auto_enabled})


@app.route("/api/scrape/<pid>", methods=["POST"])
def api_scrape_one(pid):
    watched = load_watched()
    product = next((w for w in watched if w["id"] == pid), None)
    if not product:
        return jsonify({"status": "not_found"}), 404

    def run():
        data = load_data()
        channels = scrape_product_channels(product["url"], product["name"])
        if channels:
            now = datetime.now().isoformat()
            min_price = min(c["price"] for c in channels)
            # Get previous price for alert comparison
            old_min = None
            if pid in data and data[pid].get("history"):
                valid = [h["price"] for h in data[pid]["history"] if h.get("price")]
                old_min = valid[-1] if valid else None
            if pid not in data:
                data[pid] = {"name": product["name"], "url": product["url"],
                             "image": product.get("image",""), "channels": [], "history": [], "last_updated": None}
            data[pid]["channels"] = channels
            data[pid]["last_updated"] = now
            data[pid]["history"].append({"price": min_price, "channel_count": len(channels), "scraped_at": now})
            data[pid]["history"] = data[pid]["history"][-100:]
            save_data(data)
            # Check alert condition
            target = load_targets().get(pid)
            check_and_alert(pid, product["name"], old_min, min_price, target)

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "ok"})



TARGET_FILE = "target_prices.json"
RRP_FILE = "rrp_prices.json"
ALERT_FILE = "alerts.json"
ALERT_THRESHOLD = 999  # TL — minimum price drop to trigger alert


def load_alerts():
    path = os.path.join(BASE_DIR, ALERT_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                c = f.read().strip()
                return json.loads(c) if c else []
        except:
            return []
    return []


def save_alerts(alerts):
    path = os.path.join(BASE_DIR, ALERT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts[-100:], f, ensure_ascii=False, indent=2)  # keep last 100


def check_and_alert(pid, product_name, old_price, new_price, target_price):
    """
    Fire an alert if:
    - Price dropped by >= ALERT_THRESHOLD TL, AND
    - New price is below RRP/target (or no target set → alert anyway)
    """
    if old_price is None or new_price is None:
        return None
    drop = old_price - new_price
    if drop < ALERT_THRESHOLD:
        return None

    # Compare with target/RRP
    below_target = target_price is not None and new_price < target_price
    at_or_above = target_price is not None and new_price >= target_price

    alert = {
        "id": f"{pid}_{int(datetime.now().timestamp())}",
        "pid": pid,
        "name": product_name,
        "old_price": old_price,
        "new_price": new_price,
        "drop": drop,
        "drop_pct": round((drop / old_price) * 100, 1),
        "target_price": target_price,
        "below_target": below_target,
        "timestamp": datetime.now().isoformat(),
        "seen": False,
    }

    alerts = load_alerts()
    alerts.append(alert)
    save_alerts(alerts)
    print(f"  [ALERT] {product_name}: {old_price:,.0f} → {new_price:,.0f} TL (↓{drop:,.0f} TL)")
    return alert


def load_rrp():
    """Load RRP reference prices by product name."""
    path = os.path.join(BASE_DIR, RRP_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                data = json.loads(content) if content else {}
                return {k: v for k, v in data.items() if not k.startswith("_")}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def find_rrp_for_product(product_name):
    """
    Try to match a product name to an RRP price.
    Tries: full name+memory, then progressively shorter matches.
    e.g. "Xiaomi Redmi Note 15 Pro 256 GB 8 GB" → matches "redmi note 15 pro 8+256"
    """
    rrp = load_rrp()
    name_lower = product_name.lower()

    # Normalize: remove "xiaomi", "gb", commas, extra spaces
    import re
    normalized = re.sub(r'\bxiaomi\b', '', name_lower)
    normalized = re.sub(r'(\d+)\s*gb', lambda m: m.group(1), normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # Extract memory pattern like "8+256" or "12+512"
    mem_match = re.search(r'(\d+)\s*[+]\s*(\d+)', normalized)
    mem_str = f"{mem_match.group(1)}+{mem_match.group(2)}" if mem_match else None

    # Try keys from longest to shortest match
    for key in sorted(rrp.keys(), key=len, reverse=True):
        key_parts = key.split()
        # Check if all key parts appear in normalized name
        if all(part in normalized for part in key_parts):
            # If key has memory spec, must match
            if '+' in key and mem_str:
                if mem_str in key:
                    return rrp[key]
            elif '+' not in key:
                return rrp[key]

    return None

def load_targets():
    path = os.path.join(BASE_DIR, TARGET_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}

def save_targets(targets):
    path = os.path.join(BASE_DIR, TARGET_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)


@app.route("/api/targets", methods=["GET"])
def api_targets_get():
    return jsonify(load_targets())


@app.route("/api/targets/<pid>", methods=["POST"])
def api_targets_set(pid):
    body = request.json or {}
    targets = load_targets()
    price = body.get("price")
    if price is None:
        targets.pop(pid, None)
    else:
        targets[pid] = float(price)
    save_targets(targets)
    return jsonify({"status": "ok", "pid": pid, "target": targets.get(pid)})


@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    alerts = load_alerts()
    unseen = [a for a in alerts if not a.get("seen")]
    return jsonify({
        "alerts": list(reversed(alerts)),  # newest first
        "unseen_count": len(unseen),
    })


@app.route("/api/alerts/seen", methods=["POST"])
def api_alerts_mark_seen():
    alerts = load_alerts()
    for a in alerts:
        a["seen"] = True
    save_alerts(alerts)
    return jsonify({"status": "ok"})


@app.route("/api/alerts/clear", methods=["POST"])
def api_alerts_clear():
    save_alerts([])
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Startup: clear price history (keep watchlist and target prices)
    prices_path = os.path.join(BASE_DIR, DATA_FILE)
    if os.path.exists(prices_path):
        os.remove(prices_path)
        print("  [Startup] prices.json cleared.")

    # Repair corrupt/empty JSON files on startup
    for fname, default in [(WATCHED_FILE, "[]"), (TARGET_FILE, "{}"), (RRP_FILE, None)]:
        fpath = os.path.join(BASE_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content and default is not None:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(default)
                    print(f"  [Startup] Repaired empty {fname}")
            except Exception:
                pass

    # Tarayıcıyı otomatik aç
    def open_browser():
        time.sleep(1.5)
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()

    # Arka plan tarayıcı
    threading.Thread(target=background_scraper, daemon=True).start()

    print("\n" + "="*50)
    print("  Xiaomi Fiyat Monitor")
    print(f"  http://localhost:{PORT}")
    print("  Kapatmak icin bu pencereyi kapat")
    print("="*50 + "\n")

    app.run(debug=False, host="0.0.0.0", port=PORT)