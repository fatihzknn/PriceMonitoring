import json, os, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_FILE = "prices.json"
WATCHED_FILE = "watched.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_PATH = os.path.join(BASE_DIR, DATA_FILE)
WATCHED_FILE_PATH = os.path.join(BASE_DIR, WATCHED_FILE)

# Progress callback — app.py tarafından set edilir
_progress_callback = None

def set_progress_callback(fn):
    global _progress_callback
    _progress_callback = fn

def _notify(msg):
    if _progress_callback:
        _progress_callback(msg)
    print(msg)


def load_data():
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
                c = f.read().strip()
                return json.loads(c) if c else {}
        except:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_watched():
    if os.path.exists(WATCHED_FILE_PATH):
        try:
            with open(WATCHED_FILE_PATH, "r", encoding="utf-8") as f:
                c = f.read().strip()
                return json.loads(c) if c else []
        except:
            return []
    return []

def save_watched(w):
    with open(WATCHED_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=2)

def parse_price(text):
    if not text: return None
    text = re.sub(r'[^\d\.,]', '', text.strip())
    if ',' not in text and text.count('.') == 1:
        text = text.replace('.', '')
    elif ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try: return float(text)
    except: return None


def _make_context(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
    )
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        extra_http_headers={
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR','tr','en'] });
        window.chrome = { runtime: {} };
    """)
    try:
        from playwright_stealth import stealth_sync
        page = ctx.new_page()
        stealth_sync(page)
        return browser, ctx, page
    except ImportError:
        pass
    return browser, ctx, ctx.new_page()


def search_akakce(query):
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser, ctx, page = _make_context(p)
        try:
            page.goto(
                f"https://www.akakce.com/arama/?q={query.replace(' ', '+')}",
                wait_until="domcontentloaded", timeout=20000
            )
            page.wait_for_timeout(2000)
            html = page.content()
        except Exception as e:
            print(f"[Search] {e}")
            browser.close()
            return []
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    results = []
    for li in soup.select("li.w")[:20]:
        pid = li.get("data-pr", "")
        name_el = li.select_one("h3.pn_v8")
        price_el = li.select_one("span.pt_v9")
        img_el = li.select_one("figure img")
        link_el = li.select_one("a[href]")
        if not name_el or not pid: continue
        href = link_el.get("href", "") if link_el else ""
        results.append({
            "id": pid,
            "name": name_el.get_text(strip=True),
            "price": parse_price(price_el.get_text()) if price_el else None,
            "image": img_el.get("src", "") if img_el else "",
            "url": f"https://www.akakce.com{href}" if href.startswith("/") else href,
        })
    return results


def _click_more_buttons(page):
    try:
        btn = page.query_selector("button#SAP")
        if btn and btn.is_visible():
            btn.scroll_into_view_if_needed()
            btn.click()
            try: page.wait_for_selector("button#loadMoreBtn", timeout=4000)
            except: page.wait_for_timeout(1500)
    except: pass

    for i in range(15):
        try:
            btn = page.query_selector("button#loadMoreBtn")
            if not btn or not btn.is_visible(): break
            btn.scroll_into_view_if_needed()
            btn.click()
            page.wait_for_timeout(1000)
        except: break


def _parse_channels(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    best = {}

    def add(store, price, url, kargo, kupon, source):
        if not store or not price: return
        key = store.lower().strip()
        if key not in best or price < best[key]["price"]:
            best[key] = {"store": store, "price": price, "url": url,
                         "kargo": kargo, "kupon": kupon, "source": source}

    # Piyasa fiyatları (ul.pp_v8)
    for a in soup.select("ul.pp_v8 a.iC"):
        img = a.select_one("img")
        store = img.get("alt", "").strip() if img else ""
        price = parse_price(a.get_text(" ", strip=True))
        href = a.get("href", "")
        add(store, price, f"https://www.akakce.com{href}" if href.startswith("/") else href, "", "", "market")

    # Normal satıcılar
    for a in soup.select("a.iC.xt_v8"):
        img = a.select_one("img")
        store = img.get("alt", "").strip() if img else ""
        if not store:
            l_img = a.select_one("span.l img, .l img")
            store = l_img.get("alt", "").strip() if l_img else ""
        if not store: continue
        price_el = a.select_one("span.pt_v8")
        price = parse_price(price_el.get_text()) if price_el else None
        if not price:
            matches = re.findall(r'[\d]{2,}[\d\.]*,\d{2}', a.get_text(" ", strip=True))
            prices = [parse_price(m) for m in matches if parse_price(m)]
            price = min(prices) if prices else None
        if not price: continue
        kargo_el = a.select_one("em.uk_v8")
        kupon_el = a.select_one("span.cam_w")
        href = a.get("href", "")
        add(store, price,
            f"https://www.akakce.com{href}" if href.startswith("/") else href,
            kargo_el.get_text(strip=True) if kargo_el else "",
            kupon_el.get_text(strip=True) if kupon_el else "",
            "normal")

    return sorted(best.values(), key=lambda x: x["price"])


def scrape_product_channels(url, product_name):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, ctx, page = _make_context(p)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try: page.wait_for_selector("a.iC, ul.pp_v8, button#SAP", timeout=12000)
            except: page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[Scrape] Load error: {e}")
            browser.close()
            return []
        _click_more_buttons(page)
        html = page.content()
        browser.close()

    channels = _parse_channels(html)
    market = sum(1 for c in channels if c["source"] == "market")
    normal = sum(1 for c in channels if c["source"] == "normal")
    _notify(f"  ✓ {product_name[:30]}: {len(channels)} satıcı ({market} piyasa, {normal} normal)")
    return channels


def _scrape_one_product(product, stop_flag):
    """Tek ürünü scrape et — thread'de çalışır"""
    if stop_flag and stop_flag():
        return None
    pid = product["id"]
    _notify(f"[Taranıyor] {product['name']}")
    try:
        channels = scrape_product_channels(product["url"], product["name"])
        return (pid, product, channels)
    except Exception as e:
        _notify(f"  [Hata] {product['name']}: {e}")
        return None


def scrape_watched_products(stop_flag=None, max_workers=3, progress_fn=None):
    """
    Paralel tarama — max_workers ürünü aynı anda tara.
    progress_fn(done, total, product_name) çağrılır.
    """
    watched = load_watched()
    if not watched: return

    total = len(watched)
    done = 0
    data = load_data()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_scrape_one_product, product, stop_flag): product
            for product in watched
        }
        for future in as_completed(futures):
            if stop_flag and stop_flag():
                executor.shutdown(wait=False, cancel_futures=True)
                break
            result = future.result()
            done += 1
            if result is None:
                continue
            pid, product, channels = result
            if progress_fn:
                progress_fn(done, total, product["name"])
            if not channels:
                continue
            now = datetime.now().isoformat()
            min_price = min(c["price"] for c in channels)
            if pid not in data:
                data[pid] = {"name": product["name"], "url": product["url"],
                             "image": product.get("image", ""), "channels": [], "history": [], "last_updated": None}
            data[pid]["channels"] = channels
            data[pid]["last_updated"] = now
            data[pid]["history"].append({"price": min_price, "channel_count": len(channels), "scraped_at": now})
            data[pid]["history"] = data[pid]["history"][-100:]
            save_data(data)