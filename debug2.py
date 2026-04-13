"""
py debug2.py
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

URL = "https://www.akakce.com/cep-telefonu/en-ucuz-xiaomi-redmi-note-15-pro-256-gb-8-gb-fiyati,1337432076.html"

def parse_price(text):
    if not text: return None
    text = re.sub(r'[^\d\.,]', '', text.strip())
    if ',' not in text and text.count('.') == 1:
        text = text.replace('.', '')
    elif ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try: return float(text)
    except: return None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # görünür açılır
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        viewport={"width":1280,"height":900}
    ).new_page()

    print("Sayfa yükleniyor...")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_selector("a.iC, ul.pp_v8, button#SAP", timeout=12000)
        print("✓ İlk yükleme tamam")
    except:
        print("⚠ Timeout")

    # SAP
    btn = page.query_selector("button#SAP")
    print(f"SAP butonu: {'BULUNDU' if btn and btn.is_visible() else 'YOK'}")
    if btn and btn.is_visible():
        btn.click()
        try: page.wait_for_selector("button#loadMoreBtn", timeout=4000)
        except: page.wait_for_timeout(1500)

    # loadMore
    c = 0
    for i in range(15):
        b = page.query_selector("button#loadMoreBtn")
        if not b or not b.is_visible(): break
        b.scroll_into_view_if_needed(); b.click(); page.wait_for_timeout(1000); c+=1
    print(f"loadMoreBtn: {c} kez tıklandı")

    html = page.content()

    # Canlı sayım
    ic_count = len(page.query_selector_all("a.iC"))
    xt_count = len(page.query_selector_all("a.iC.xt_v8"))
    pt_count = len(page.query_selector_all("a.iC.pt_v8"))
    pp_count = len(page.query_selector_all("ul.pp_v8"))
    print(f"\nDOM'da:")
    print(f"  a.iC toplam: {ic_count}")
    print(f"  a.iC.xt_v8 (normal): {xt_count}")
    print(f"  a.iC.pt_v8 (piyasa): {pt_count}")
    print(f"  ul.pp_v8: {pp_count}")

    input("\nEnter'a bas, tarayıcı kapansın...")
    browser.close()

# BeautifulSoup parse
soup = BeautifulSoup(html, "lxml")

print("\n" + "="*55)
print("BS4 SONUÇLARI:")
print("="*55)

print(f"\nul.pp_v8: {len(soup.select('ul.pp_v8'))} adet")
print(f"ul.pp_v8 a.iC: {len(soup.select('ul.pp_v8 a.iC'))} adet")
print(f"a.iC.pt_v8: {len(soup.select('a.iC.pt_v8'))} adet")
print(f"a.iC.xt_v8: {len(soup.select('a.iC.xt_v8'))} adet")

print("\n--- PİYASA FİYATLARI ---")
for a in soup.select("ul.pp_v8 a.iC"):
    img = a.select_one("img")
    store = img.get("alt","?") if img else "?"
    txt = a.get_text(" ", strip=True)
    print(f"  {store}: '{txt}' → {parse_price(txt)}")

for a in soup.select("a.iC.pt_v8"):
    img = a.select_one("img")
    store = img.get("alt","?") if img else "?"
    txt = a.get_text(" ", strip=True)
    print(f"  [pt_v8] {store}: '{txt}' → {parse_price(txt)}")

print("\n--- NORMAL SATICILАR (ilk 5) ---")
for a in soup.select("a.iC.xt_v8")[:5]:
    img = a.select_one("img")
    store = img.get("alt","?") if img else "?"
    p = a.select_one("span.pt_v8")
    txt = p.get_text(strip=True) if p else a.get_text(" ",strip=True)[:30]
    print(f"  {store}: '{txt}' → {parse_price(txt)}")