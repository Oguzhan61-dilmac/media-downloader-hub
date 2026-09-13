# 📱 Media Downloader Hub Mobile (Faz 1)

**Media Downloader Hub Mobile**, masaüstü sürümündeki ağır iş yüklerini (video indirme, yapay zeka altyazı çıkarımı ve FFmpeg hardsub gömme) sunucu tarafına taşıyarak mobil cihazların (Android & iOS) batarya ve bellek kaynaklarını tüketmeden çalışan **Client-Server (İstemci-Sunucu)** mimarili mobil uygulamadır.

---

## 🏛️ Mimari Yapı (Client-Server Mimarisi)

```
+------------------------------------+             +------------------------------------+
|       Mobil İstemci (Flutter)      |             |     REST API Sunucusu (FastAPI)     |
|   (Android / iOS Mobile Device)    |             |       (High-Performance Backend)    |
+------------------------------------+             +------------------------------------+
                  |                                                  |
                  |  1. POST /api/process (URL & Dil Ayarları)       |
                  |------------------------------------------------->| ---> [yt-dlp Video İndirici]
                  |  <-- returns task_id                             | ---> [faster-whisper AI STT]
                  |                                                  | ---> [FFmpeg Hardsub Engine]
                  |  2. GET /api/status/{task_id} (Periyodik Polling) |
                  |------------------------------------------------->|
                  |  <-- returns status (%0-%100, step_name)         |
                  |                                                  |
                  |  3. GET /api/download/{task_id} (Tamamlandığında) |
                  |------------------------------------------------->|
                  |  <-- Stream _altyazili.mp4 (FileResponse)         |
                  v                                                  v
     [Yerel Galeride/İndirilenlerde Saklanır]             [Geçici Çıktı Temizlenir]
```

---

## 🚀 Kurulum ve Çalıştırma Talimatları

### 1. Backend REST API Sunucusunu Başlatma

Backend sunucusu Python 3.9+ ortamında `FastAPI` ve `Uvicorn` kullanır.

```bash
# Proje ana dizininde (busy-galileo/):
pip install -r requirements.txt

# Uvicorn sunucusunu tüm ağ arayüzlerinde dinleyecek şekilde başlatın:
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Sunucu başarıyla başladığında `http://localhost:8000/api/health` adresinden veya Swagger dokümantasyonundan (`http://localhost:8000/docs`) test edilebilir.

---

### 2. Mobil Uygulamayı (Flutter) Çalıştırma

Mobil uygulama `mobile/` klasöründe yer alır.

```bash
# Mobil klasörüne geçin
cd mobile

# Bağımlılıkları kontrol edin
flutter pub get

# Bağlı olan fiziksel cihazda veya emülatörde çalıştırın
flutter run
```

#### Sunucu Bağlantısı (Server URL):
- **Android Emülatör**: Varsayılan olarak `http://10.0.2.2:8000` adresini kullanır.
- **Fiziksel Telefon (Yerel Ağ)**: Telefonunuz ve bilgisayarınız aynı Wi-Fi ağında ise, bilgisayarınızın yerel IP adresini girin (örneğin: `http://192.168.1.35:8000`).

---

## 🛠️ REST API Endpoint Dokümantasyonu

| Metot | Endpoint | Açıklama | Örnek İstek Gövdesi |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Sunucu durum kontrolü | `-` |
| `POST` | `/api/process` | İndirme ve altyazı sürecini başlatır | `{"url": "https://...", "auto_subtitle": true, "target_lang": "tr"}` |
| `GET` | `/api/status/{task_id}` | Anlık ilerleme yüzdesini döner | `-` |
| `GET` | `/api/download/{task_id}` | İşlenmiş `.mp4` videosunu istemciye akıtır | `-` |

---

## 📱 Öne Çıkan Mobil Arayüz Özellikleri

- 🌙 **Modern Koyu Tema (Dark Mode)**: `#0F111A` arka plan ve `#00E5FF` neon mavi vurgu rengi.
- 📋 **Panodan Hızlı Yapıştırma**: Tek tıkla kopyalanan video URL'sini alana aktarma.
- 🌐 **7 Çeviri Dili Desteği**: Türkçe, İngilizce, İspanyolca, Almanca, Fransızca, Arapça ve Rusça.
- 📊 **Anlık İlerleme Çubuğu**: İndirme ve AI altyazı adımlarını (%0 - %100) canlı gösterme.
- 💾 **Yerel Depolama Entegrasyonu**: Tamamlanan videoyu otomatik olarak telefon galerisine / dokümanlar klasörüne indirme.
