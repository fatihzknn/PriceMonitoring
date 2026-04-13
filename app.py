"""
Xiaomi Price Monitor - Backend v5
Port: 8080
"""
from flask import Flask, jsonify, send_from_directory, request
import json, os, threading, time, sys, re
from datetime import datetime
from scraper import (
    search_akakce, scrape_product_channels, scrape_watched_products,
    load_data, save_data, load_watched, save_watched, DATA_FILE, WATCHED_FILE
)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

PORT = 8080
SCRAPE_INTERVAL = 300  # 5 dakika

_scraping = False
_stop_requested = False
_auto_enabled = True
_last_scrape = None
_scrape_lock = threading.Lock()

TARGET_FILE = "target_prices.json"
RRP_FILE = "rrp_prices.json"
ALERT_FILE = "alerts.json"
ALERT_THRESHOLD = 999


# ── Loaders ──────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                c = f.read().strip()
                return json.loads(c) if c else default
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_targets():
    return load_json(os.path.join(BASE_DIR, TARGET_FILE), {})

def save_targets(t):
    save_json(os.path.join(BASE_DIR, TARGET_FILE), t)

def load_rrp():
    data = load_json(os.path.join(BASE_DIR, RRP_FILE), {})
    return {k: v for k, v in data.items() if not k.startswith("_")}

def load_alerts():
    return load_json(os.path.join(BASE_DIR, ALERT_FILE), [])

def save_alerts(a):
    save_json(os.path.join(BASE_DIR, ALERT_FILE), a[-100:])


# ── RRP matching ─────────────────────────────────────────────

def find_rrp_for_product(product_name):
    rrp = load_rrp()
    name_lower = product_name.lower()
    normalized = re.sub(r'\bxiaomi\b', '', name_lower)
    normalized = re.sub(r'(\d+)\s*gb', lambda m: m.group(1), normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    mem_match = re.search(r'(\d+)\s*[+]\s*(\d+)', normalized)
    mem_str = f"{mem_match.group(1)}+{mem_match.group(2)}" if mem_match else None
    for key in sorted(rrp.keys(), key=len, reverse=True):
        key_parts = key.split()
        if all(part in normalized for part in key_parts):
            if '+' in key and mem_str:
                if mem_str in key:
                    return rrp[key]
            elif '+' not in key:
                return rrp[key]
    return None


# ── Alert system ─────────────────────────────────────────────

def check_and_alert(pid, product_name, old_price, new_price, target_price):
    if old_price is None or new_price is None:
        return
    drop = old_price - new_price
    if drop < ALERT_THRESHOLD:
        return
    below_target = target_price is not None and new_price < target_price
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


# ── Background scraper ────────────────────────────────────────

def background_scraper():
    global _scraping, _last_scrape, _stop_requested
    while True:
        time.sleep(10)
        if not _auto_enabled:
            continue
        if _last_scrape:
            elapsed = (datetime.now() - datetime.fromisoformat(_last_scrape)).total_seconds()
            if elapsed < SCRAPE_INTERVAL:
                continue
        else:
            time.sleep(30)
        watched = load_watched()
        if not watched or not _auto_enabled:
            continue
        if _scrape_lock.locked():
            continue
        with _scrape_lock:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Otomatik tarama başlıyor...")
            _stop_requested = False
            _scraping = True
            old_data = load_data()
            old_prices = {}
            for pid, pdata in old_data.items():
                hist = [h["price"] for h in pdata.get("history", []) if h.get("price")]
                old_prices[pid] = hist[-1] if hist else None
            scrape_watched_products(stop_flag=lambda: _stop_requested)
            new_data = load_data()
            targets = load_targets()
            for pid, pdata in new_data.items():
                hist = [h["price"] for h in pdata.get("history", []) if h.get("price")]
                if not hist:
                    continue
                check_and_alert(pid, pdata.get("name", pid), old_prices.get(pid), hist[-1], targets.get(pid))
            _scraping = False
            _last_scrape = datetime.now().isoformat()


# ── API routes ────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")

@app.route("/api/prices")
def api_prices():
    data = load_data()
    watched = load_watched()
    targets = load_targets()
    result = []
    for w in watched:
        pid = w["id"]
        pdata = data.get(pid, {})
        channels = pdata.get("channels", [])
        history = pdata.get("history", [])
        prices = [h["price"] for h in history if h.get("price")]
        min_price = min(c["price"] for c in channels) if channels else None
        change = None
        if len(prices) >= 2:
            change = prices[-1] - prices[-2]
        target = targets.get(pid)
        result.append({
            "id": pid,
            "name": w["name"],
            "url": w.get("url", ""),
            "image": w.get("image", ""),
            "min_price": min_price,
            "channels": channels,
            "channel_count": len(channels),
            "history": history[-30:],
            "last_updated": pdata.get("last_updated"),
            "change": change,
            "target_price": target,
            "has_rrp": target is not None,
        })
    return jsonify({
        "products": result,
        "scraping": _scraping,
        "auto_enabled": _auto_enabled,
        "last_scrape": _last_scrape,
        "interval_minutes": SCRAPE_INTERVAL // 60,
    })

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    results = search_akakce(q)
    return jsonify({"results": results})

@app.route("/api/watched", methods=["GET"])
def api_watched_get():
    return jsonify(load_watched())

@app.route("/api/watched", methods=["POST"])
def api_watched_add():
    body = request.json or {}
    watched = load_watched()
    pid = str(body.get("id", "")).strip()
    if not pid:
        return jsonify({"status": "error", "message": "no id"}), 400
    if any(w["id"] == pid for w in watched):
        return jsonify({"status": "exists"})
    product_name = body.get("name", "")
    watched.append({
        "id": pid,
        "name": product_name,
        "url": body.get("url", ""),
        "image": body.get("image", ""),
        "added_at": datetime.now().isoformat(),
    })
    save_watched(watched)
    targets = load_targets()
    if pid not in targets:
        rrp = find_rrp_for_product(product_name)
        if rrp:
            targets[pid] = rrp
            save_targets(targets)
            print(f"  [RRP] Auto-assigned {rrp:,} TL to '{product_name}'")
    return jsonify({"status": "ok", "id": pid})

@app.route("/api/watched/<pid>", methods=["DELETE"])
def api_watched_delete(pid):
    watched = [w for w in load_watched() if w["id"] != pid]
    save_watched(watched)
    data = load_data()
    data.pop(pid, None)
    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/api/scrape/all", methods=["POST"])
def api_scrape_all():
    global _scraping, _last_scrape, _stop_requested
    def run():
        global _scraping, _last_scrape, _stop_requested
        with _scrape_lock:
            _stop_requested = False
            _scraping = True
            old_data = load_data()
            old_prices = {}
            for pid, pdata in old_data.items():
                hist = [h["price"] for h in pdata.get("history", []) if h.get("price")]
                old_prices[pid] = hist[-1] if hist else None
            scrape_watched_products(stop_flag=lambda: _stop_requested)
            new_data = load_data()
            targets = load_targets()
            for pid, pdata in new_data.items():
                hist = [h["price"] for h in pdata.get("history", []) if h.get("price")]
                if hist:
                    check_and_alert(pid, pdata.get("name", pid), old_prices.get(pid), hist[-1], targets.get(pid))
            _scraping = False
            _last_scrape = datetime.now().isoformat()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route("/api/scrape/stop", methods=["POST"])
def api_scrape_stop():
    global _stop_requested
    _stop_requested = True
    return jsonify({"status": "ok"})

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
            old_min = None
            if pid in data and data[pid].get("history"):
                valid = [h["price"] for h in data[pid]["history"] if h.get("price")]
                old_min = valid[-1] if valid else None
            if pid not in data:
                data[pid] = {"name": product["name"], "url": product["url"],
                             "image": product.get("image", ""), "channels": [], "history": [], "last_updated": None}
            data[pid]["channels"] = channels
            data[pid]["last_updated"] = now
            data[pid]["history"].append({"price": min_price, "channel_count": len(channels), "scraped_at": now})
            data[pid]["history"] = data[pid]["history"][-100:]
            save_data(data)
            check_and_alert(pid, product["name"], old_min, min_price, load_targets().get(pid))
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "ok"})

@app.route("/api/auto", methods=["POST"])
def api_auto_toggle():
    global _auto_enabled
    body = request.json or {}
    _auto_enabled = body.get("enabled", not _auto_enabled)
    return jsonify({"status": "ok", "auto_enabled": _auto_enabled})

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
    return jsonify({"status": "ok"})

@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    alerts = load_alerts()
    unseen = [a for a in alerts if not a.get("seen")]
    return jsonify({"alerts": list(reversed(alerts)), "unseen_count": len(unseen)})

@app.route("/api/alerts/seen", methods=["POST"])
def api_alerts_seen():
    alerts = load_alerts()
    for a in alerts:
        a["seen"] = True
    save_alerts(alerts)
    return jsonify({"status": "ok"})

@app.route("/api/alerts/clear", methods=["POST"])
def api_alerts_clear():
    save_alerts([])
    return jsonify({"status": "ok"})


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Startup: prices.json sil
    prices_path = os.path.join(BASE_DIR, DATA_FILE)
    if os.path.exists(prices_path):
        os.remove(prices_path)
        print("  [Startup] prices.json cleared.")

    # Bozuk JSON'ları onar
    for fname, default in [(WATCHED_FILE, "[]"), (TARGET_FILE, "{}"), (ALERT_FILE, "[]")]:
        fpath = os.path.join(BASE_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    c = f.read().strip()
                if not c:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(default)
                    print(f"  [Startup] Repaired {fname}")
            except:
                pass

    threading.Thread(target=background_scraper, daemon=True).start()

    def open_browser():
        time.sleep(1.5)
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()

    print("\n" + "="*50)
    print("  Xiaomi Price Monitor")
    print(f"  http://localhost:{PORT}")
    print("  Close this window to stop")
    print("="*50 + "\n")

    app.run(debug=False, host="0.0.0.0", port=PORT)
