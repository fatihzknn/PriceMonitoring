"""
Xiaomi Fiyat Monitor - Scraper v4
Akakce'nin gerçek HTML yapısına göre yazıldı:
  - Arama: li.w > a.pw_v8, h3.pn_v8, span.pt_v9, figure img
  - Satıcılar: a.iC > span.pt_v8, img[alt] (logo)
"""

import json, os, time, re, random
from datetime import datetime

DATA_FILE = "prices.json"
WATCHED_FILE = "watched.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


def parse_price(text):
    """Akakce fiyat formatı: '16.679,00 TL' veya span içinde '16.679<i>,00 TL</i>'"""
    if not text:
        return None
    # Sadece rakam ve virgül/nokta bırak
    cleaned = re.sub(r"[^\d,.]", "", str(text).strip())
    if not cleaned:
        return None
    # Türk formatı: 16.679,00 → binlik nokta, ondalık virgül
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts[-1]) == 3:  # 16.679 → binlik ayraç
            cleaned = cleaned.replace(".", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        val = float(cleaned)
        return val if val > 10 else None
    except:
        return None


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_watched():
    if os.path.exists(WATCHED_FILE):
        try:
            with open(WATCHED_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def save_watched(watched):
    with open(WATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(watched, f, ensure_ascii=False, indent=2)


def get_page(url, wait=2.0):
    """Playwright ile sayfa aç, HTML döndür"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
        )
        # Ana sayfa → cookie al
        page.goto("https://www.akakce.com/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(random.uniform(0.5, 1.0))
        # Hedef sayfa
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(wait)
        html = page.content()
        browser.close()
    return html


def search_akakce(query):
    """
    Akakce'de ürün ara.
    Döndürür: [{"name", "url", "price", "image", "id"}, ...]
    """
    from bs4 import BeautifulSoup

    url = f"https://www.akakce.com/arama/?q={query.strip().replace(' ', '+')}"
    try:
        html = get_page(url, wait=2.0)
    except Exception as e:
        print(f"[Arama Hatası] {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for li in soup.select("li.w"):
        try:
            # URL ve ürün ID
            a = li.select_one("a.pw_v8")
            if not a:
                continue
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)

            # data-pr attribute'undan ID al (en güvenilir)
            pid = li.get("data-pr", "")
            if not pid:
                # URL'den çıkar: ...,1337432076.html
                m = re.search(r",(\d+)\.html", href)
                pid = m.group(1) if m else href

            # Ürün adı
            name_el = li.select_one("h3.pn_v8")
            name = name_el.get_text(strip=True) if name_el else a.get("title", "")

            # Fiyat — span.pt_v9 içinde metin + <i> tag karışık
            price_el = li.select_one("span.pt_v9")
            price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

            # Görsel
            img_el = li.select_one("figure img")
            img = img_el.get("src", "") if img_el else ""

            if name:
                results.append({
                    "id": pid,
                    "name": name,
                    "url": href,
                    "price": price,
                    "image": img,
                })
        except Exception:
            continue

    return results


def scrape_product_channels(product_url, product_name):
    """
    Ürün sayfasındaki tüm satıcı fiyatlarını çek.
    Akakce yapısı: a.iC → span.pt_v8 (fiyat) + img[alt] (mağaza adı)
    Döndürür: [{"store", "price", "url"}, ...] fiyata göre sıralı
    """
    from bs4 import BeautifulSoup

    try:
        html = get_page(product_url, wait=2.5)
    except Exception as e:
        print(f"  [Kanal Hatası] {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    channels = []
    seen_stores = set()
    now = datetime.now().isoformat()

    # Her satıcı bir a.iC elementi
    for a in soup.select("a.iC"):
        try:
            href = a.get("href", "")

            # Fiyat: span.pt_v8 içinde "16.679<i>,00 TL</i>" formatı
            price_el = a.select_one("span.pt_v8")
            price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None
            if not price:
                continue

            # Mağaza adı: logo img'nin alt attribute'u
            logo = a.select_one("img")
            store = logo.get("alt", "").strip() if logo else ""
            if not store:
                # Fallback: span içindeki metin
                store_el = a.select_one("span.l, [class*='shop'], [class*='store']")
                store = store_el.get_text(strip=True) if store_el else f"Satıcı"

            if not store or store in seen_stores:
                continue
            seen_stores.add(store)

            # Kargo durumu
            kargo_el = a.select_one("em.uk_v8")
            kargo = kargo_el.get_text(strip=True) if kargo_el else ""

            # Kampanya/kupon
            kupon_el = a.select_one("span.cam_w")
            kupon = kupon_el.get_text(strip=True) if kupon_el else ""

            channels.append({
                "store": store,
                "price": price,
                "url": href,
                "kargo": kargo,
                "kupon": kupon,
                "scraped_at": now,
            })
        except Exception:
            continue

    return sorted(channels, key=lambda x: x["price"])


def scrape_watched_products(stop_flag=None):
    """İzleme listesindeki tüm ürünleri tara. stop_flag() True dönerse durur."""
    watched = load_watched()
    data = load_data()
    now = datetime.now().isoformat()

    for product in watched:
        if stop_flag and stop_flag():
            print("  [DURDURULDU]")
            break
        pid = product["id"]
        print(f"\n  [{product['name']}]")

        channels = scrape_product_channels(product["url"], product["name"])

        if pid not in data:
            data[pid] = {
                "name": product["name"],
                "url": product["url"],
                "image": product.get("image", ""),
                "channels": [],
                "history": [],
                "last_updated": None,
            }

        if channels:
            min_price = min(c["price"] for c in channels)
            data[pid]["channels"] = channels
            data[pid]["last_updated"] = now
            data[pid]["history"].append({
                "price": min_price,
                "channel_count": len(channels),
                "scraped_at": now,
            })
            data[pid]["history"] = data[pid]["history"][-100:]
            print(f"  ✓ {len(channels)} satıcı | En düşük: {min_price:,.0f} TL")
        else:
            print(f"  ✗ Satıcı bulunamadı")

        time.sleep(random.uniform(3, 5))

    save_data(data)
    return data


if __name__ == "__main__":
    print("Test: Xiaomi Redmi Note 15 arama")
    results = search_akakce("xiaomi redmi note 15")
    print(f"{len(results)} sonuç bulundu:")
    for r in results[:5]:
        print(f"  [{r['id']}] {r['name']} - {r['price']} TL")
        print(f"    {r['url']}")