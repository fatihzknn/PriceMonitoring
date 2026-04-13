import json, os, re
from datetime import datetime

DATA_FILE = "prices.json"
WATCHED_FILE = "watched.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_PATH = os.path.join(BASE_DIR, DATA_FILE)
WATCHED_FILE_PATH = os.path.join(BASE_DIR, WATCHED_FILE)


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
    """'14.999 TL' veya '14.624,00 TL' → float"""
    if not text:
        return None
    # Nokta binlik ayraç, virgül ondalık ayraç
    text = text.strip()
    text = re.sub(r'[^\d\.,]', '', text)
    # "14.999" formatı (nokta=binlik, virgül yok)
    if ',' not in text and text.count('.') == 1:
        text = text.replace('.', '')
    # "14.624,00" formatı
    elif ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        return float(text)
    except:
        return None


# ── Search ────────────────────────────────────────────────────

def search_akakce(query):
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
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
        if not name_el or not pid:
            continue
        href = link_el.get("href", "") if link_el else ""
        results.append({
            "id": pid,
            "name": name_el.get_text(strip=True),
            "price": parse_price(price_el.get_text()) if price_el else None,
            "image": img_el.get("src", "") if img_el else "",
            "url": f"https://www.akakce.com{href}" if href.startswith("/") else href,
        })
    return results


# ── More buttons ──────────────────────────────────────────────

def _click_more_buttons(page):
    """
    1. button#SAP  → "Daha fazla fiyat gör"
    2. button#loadMoreBtn → "Devamını Göster" (birden fazla kez)
    """
    try:
        btn = page.query_selector("button#SAP")
        if btn and btn.is_visible():
            btn.scroll_into_view_if_needed()
            btn.click()
            try:
                page.wait_for_selector("button#loadMoreBtn", timeout=4000)
            except:
                page.wait_for_timeout(1500)
            print("    [SAP] clicked")
    except Exception as e:
        print(f"    [SAP] {e}")

    for i in range(15):
        try:
            btn = page.query_selector("button#loadMoreBtn")
            if not btn or not btn.is_visible():
                break
            btn.scroll_into_view_if_needed()
            btn.click()
            page.wait_for_timeout(1000)
            print(f"    [LoadMore] click #{i+1}")
        except:
            break


# ── Parse HTML ────────────────────────────────────────────────

def _parse_channels(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    channels = []
    seen = set()

    # ── Piyasa fiyatları (ul.pp_v8 içinde a.iC.pt_v8) ──
    # Bunlar MediaMarkt, Vatan, Hepsiburada gibi büyük mağazalar
    for a in soup.select("ul.pp_v8 a.iC"):
        try:
            img = a.select_one("img")
            store = img.get("alt", "").strip() if img else ""
            if not store:
                continue
            # Fiyat direkt link text'inde: "14.999 TL"
            full_text = a.get_text(" ", strip=True)
            price = parse_price(full_text)
            if not price:
                continue
            href = a.get("href", "")
            channels.append({
                "store": store,
                "price": price,
                "url": f"https://www.akakce.com{href}" if href.startswith("/") else href,
                "kargo": "",
                "kupon": "",
                "source": "market",
            })
            seen.add(store.lower())
        except:
            continue

    # ── Normal satıcılar (a.iC.xt_v8) ──
    for a in soup.select("a.iC.xt_v8, a.iC:not(.pt_v8)"):
        try:
            img = a.select_one("img")
            store = img.get("alt", "").strip() if img else ""
            if not store or store.lower() in seen:
                continue

            # Fiyat: indirimli varsa ikinci fiyat, yoksa tek fiyat
            price_els = a.select("span.pt_v8, em.op_v8")
            price = None
            for pel in a.select("span.pt_v8"):
                price = parse_price(pel.get_text())
                if price:
                    break
            if not price:
                # Tüm text'ten TL içeren sayıyı bul
                txt = a.get_text(" ", strip=True)
                matches = re.findall(r'([\d]{2,}[\d\.]*,\d{2})\s*TL', txt)
                if matches:
                    prices = [parse_price(m) for m in matches if parse_price(m)]
                    price = min(prices) if prices else None
            if not price:
                continue

            kargo_el = a.select_one("em.uk_v8")
            kupon_el = a.select_one("span.cam_w")
            href = a.get("href", "")

            channels.append({
                "store": store,
                "price": price,
                "url": f"https://www.akakce.com{href}" if href.startswith("/") else href,
                "kargo": kargo_el.get_text(strip=True) if kargo_el else "",
                "kupon": kupon_el.get_text(strip=True) if kupon_el else "",
                "source": "normal",
            })
            seen.add(store.lower())
        except:
            continue

    return channels


# ── Main scraper ──────────────────────────────────────────────

def scrape_product_channels(url, product_name):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = ctx.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_selector("a.iC, ul.pp_v8, button#SAP", timeout=12000)
            except:
                page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[Scrape] Load error: {e}")
            browser.close()
            return []

        # Tüm "daha fazla" butonlarına tıkla
        _click_more_buttons(page)

        html = page.content()
        browser.close()

    channels = _parse_channels(html)
    channels = sorted(channels, key=lambda x: x["price"])
    print(f"  [Done] {len(channels)} sellers ({sum(1 for c in channels if c['source']=='market')} market, {sum(1 for c in channels if c['source']=='normal')} normal)")
    return channels


# ── Bulk ─────────────────────────────────────────────────────

def scrape_watched_products(stop_flag=None):
    watched = load_watched()
    if not watched:
        return
    data = load_data()
    for product in watched:
        if stop_flag and stop_flag():
            print("[Scrape] Stopped")
            break
        pid = product["id"]
        print(f"[Scrape] {product['name']}")
        try:
            channels = scrape_product_channels(product["url"], product["name"])
        except Exception as e:
            print(f"  [Error] {e}")
            continue
        if channels:
            now = datetime.now().isoformat()
            min_price = min(c["price"] for c in channels)
            if pid not in data:
                data[pid] = {
                    "name": product["name"],
                    "url": product["url"],
                    "image": product.get("image", ""),
                    "channels": [],
                    "history": [],
                    "last_updated": None,
                }
            data[pid]["channels"] = channels
            data[pid]["last_updated"] = now
            data[pid]["history"].append({
                "price": min_price,
                "channel_count": len(channels),
                "scraped_at": now,
            })
            data[pid]["history"] = data[pid]["history"][-100:]
            save_data(data)
            print(f"  ✓ {len(channels)} sellers, min: {min_price:,.0f} TL")