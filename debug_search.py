from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
    ctx = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36', locale='tr-TR')
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    page.goto('https://www.akakce.com/', wait_until='domcontentloaded', timeout=15000)
    time.sleep(1)
    page.goto('https://www.akakce.com/arama/?q=xiaomi+redmi+note+15', wait_until='domcontentloaded', timeout=15000)
    time.sleep(2)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'html.parser')

# İlk li.w elementinin tam HTML'i
items = soup.select('li.w')
print(f"=== li.w sayısı: {len(items)} ===\n")
if items:
    print("--- İLK li.w HTML'İ ---")
    print(str(items[0])[:2000])
    print("\n--- İKİNCİ li.w HTML'İ ---")
    if len(items) > 1:
        print(str(items[1])[:1000])