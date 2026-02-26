# 📱 Xiaomi Fiyat Monitor

Akakce üzerinden Xiaomi ürünlerinin fiyatlarını otomatik takip eden, 
gerçek zamanlı web dashboard'u ile görselleştiren sistem.

---

## 🚀 Kurulum (3 Adım)

### 1. Python bağımlılıklarını kur
```bash
pip install -r requirements.txt
```

### 2. (İsteğe bağlı) Sadece bir kez el ile tara
```bash
python scraper.py
```

### 3. Dashboard'u başlat
```bash
python app.py
```

Tarayıcında aç: **http://localhost:5000**

---

## 📦 Dosya Yapısı

```
xiaomi-monitor/
├── app.py           → Flask web sunucusu (dashboard backend)
├── scraper.py       → Akakce scraper
├── requirements.txt → Python kütüphaneleri
├── prices.json      → Fiyat veritabanı (otomatik oluşur)
└── templates/
    └── dashboard.html → Görsel panel
```

---

## ⚙️ Ayarlar

### Tarama aralığını değiştir
`app.py` içindeki `SCRAPE_INTERVAL` değerini saniye cinsinden ayarla:
```python
SCRAPE_INTERVAL = 300  # 5 dakika (varsayılan)
SCRAPE_INTERVAL = 600  # 10 dakika
SCRAPE_INTERVAL = 3600 # 1 saat
```

### Yeni ürün ekle
`scraper.py` içindeki `PRODUCTS` listesine yeni ürün ekle:
```python
{
    "name": "Xiaomi 13T",
    "url": "https://www.akakce.com/cep-telefonu/en-ucuz-xiaomi-13t-fiyati,...html",
    "image": ""  # boş bırakabilirsin
},
```

---

## 🖥️ Dashboard Özellikleri

- **Canlı fiyat takibi** – Her 30 saniyede otomatik yenilenir
- **Fiyat grafiği** – Her ürün için tarihsel fiyat grafiği
- **Değişim göstergesi** – Yeşil düşüş, kırmızı artış
- **Manuel tarama** – "TARA" butonuyla anında güncelle
- **Akakce linki** – Her üründe doğrudan ürün sayfasına git

---

## ⚠️ Önemli Notlar

- Akakce site yapısı değişirse `scraper.py` içindeki CSS seçicileri güncellemeniz gerekebilir
- Çok sık tarama yapmak IP engellemesine yol açabilir – 5+ dakika önerilir
- Fiyatlar `prices.json` dosyasında birikimli saklanır, silinirse geçmiş sıfırlanır

---

## 🔧 Sorun Giderme

**"Fiyat bulunamadı" görüyorum:**
- Akakce ürün URL'ini kontrol et, ürün sayfasında gerçekten fiyat var mı?
- Site yapısı değiştiyse, tarayıcıda sayfayı aç, fiyat elementine sağ tık → "İncele" ile doğru CSS seçiciyi bul ve `scraper.py` içine ekle

**Port 5000 kullanımda:**
`app.py` son satırındaki `port=5000` değerini `port=5001` yap

---

*Xiaomi Fiyat Monitor — otomatik fiyat takip sistemi*
