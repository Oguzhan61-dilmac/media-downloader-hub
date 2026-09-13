# 🎬 Media Downloader Hub

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Flutter](https://img.shields.io/badge/Mobile-Flutter-02569B.svg?logo=flutter&logoColor=white)](https://flutter.dev/)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-blueviolet.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![faster-whisper](https://img.shields.io/badge/AI-faster--whisper-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![FFmpeg](https://img.shields.io/badge/Media-FFmpeg-green.svg)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Media Downloader Hub**, YouTube, Rutube, TikTok ve Instagram Reels gibi popüler platformlardan yüksek kalitede video indiren, yapay zeka (`faster-whisper`) ile otomatik ses analizi yapıp Türkçe dahil 7 dilde dikey formatlı (Shorts/Reels) ritmik altyazıları doğrudan videoya gömen (hardsub), akıllı klip parçalayıcı, ses temizleme ve dinamik tipografi şablonları sunan **hibrit masaüstü, mobil (Flutter) ve REST API (FastAPI)** video işleme stüdyosudur.

---

## 🌟 Öne Çıkan Özellikler

- 🚀 **Çoklu Platform Video İndirme Motoru**:
  - `yt-dlp` altyapısı ile YouTube, Rutube, TikTok, Instagram ve diğer 1000+ platform desteği.
  - 403 Forbidden ve `googlevideo.com` zaman aşımı (Read Timed Out) hatalarını önleyen gelişmiş `extractor_args`, chunked transfer (10MB HTTP chunk size) ve otomatik yeniden deneme (retry) mimarisi.
- 🎙️ **Yapay Zeka Destekli Otomatik Altyazı (AI Subtitles)**:
  - `faster-whisper` ile yüksek doğruluklu konuşma tanıma ve zaman kodu oluşturma (CPU & CUDA desteği).
  - VAD (Voice Activity Detection) fallback mekanizması sayesinde eksik model hatalarına karşı kesintisiz çalışma.
- ⚡ **Shorts & TikTok Tarzı Ritmik Altyazı Bölümleme**:
  - `word_timestamps=True` kelime seviyesinde zamanlama ile altyazı blokları maksimum 4-5 kelime veya 25 karaktere parçalanır.
  - Ekranda aynı anda **kesinlikle en fazla 1-2 kısa satır** görünür, kalabalık ve yüzü örten altyazı blokları engellenir.
- 🎨 **İçerik Üretici Şablonları & Hizalama Mimarisi**:
  - **Hormozi / Viral Pop-up**: Canlı sarı font (`&H0000FFFF`), 4px siyah kalın kontur ve gölge stili.
  - **Minimalist Beyaz Box**: Şeffaf koyu kutulu (`&H80000000`) zarif beyaz font.
  - **Cyberpunk Neon**: Siyan metin (`&H00FFFF00`) ve mor neon kontur (`&H00FF007C`).
  - **Dinamik Hizalama**: Alt (Shorts/Reels standardı), Orta ve Üst bölge pozisyonlaması.
- 🎬 **Akıllı Video Parçalayıcı (Auto-Splitter & Clips Generator)**:
  - Whisper kelime zamanlamaları ve doğal konuşma duraklamalarını analiz eder.
  - Uzun videoları cümle ortasından kesmeden 30-60 saniyelik Shorts kliplerine böler ve tek tıkla ZIP arşivi olarak sunar.
- 🎙️ **FFmpeg AI Arka Plan Gürültü Temizleme (Denoise & Voice EQ)**:
  - `afftdn` FFT tabanlı gürültü azaltma, highpass (`150Hz`), lowpass (`3500Hz`) ve vokal band-pass equalizer filtresi uygular.
- 📱 **Mobil Uygulama & REST API Mimarisi**:
  - **FastAPI / Uvicorn REST API**: İstemci-sunucu mimarisiyle arka plan işlerini asenkron yönetir.
  - **Flutter Cross-Platform App**: Android & iOS telefonlardan kolay kullanım, canlı ilerleme takibi ve doğrudan telefona indirme.

---

## 🛠️ Kurulum & Çalıştırma

### 1. Sistem Gereksinimleri
- **Python**: 3.9 veya daha üzeri.
- **FFmpeg**: Altyazı gömme ve ses filtreleri için sisteminizde `ffmpeg` ve `ffprobe` kurulu olmalıdır.
- **Flutter SDK**: Mobil uygulamayı çalıştırmak için (isteğe bağlı).

### 2. Depoyu Klonlayın ve Sanal Ortam Oluşturun

```bash
# Depoyu klonlayın
git clone https://github.com/Oguzhan61-dilmac/media-downloader-hub.git
cd media-downloader-hub

# Sanal ortam oluşturun ve aktif edin
python -m venv .venv

# Windows için:
.venv\Scripts\activate

# macOS / Linux için:
source .venv/bin/activate
```

### 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 4. Masaüstü Uygulamasını Çalıştırın

```bash
python main.py
```

### 5. Backend REST API Sunucusunu Çalıştırın

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 6. Flutter Mobil Uygulamasını Çalıştırın

```bash
cd mobile
flutter run
```

---

## 📦 PyInstaller ile Masaüstü (.EXE) & Android APK Derleme

### Masaüstü Executable (.exe) Derleme:
```bash
python build.py
```
Oluşturulan executable `dist/MediaDownloaderHub.exe` dizinindedir.

### Android APK Derleme:
```bash
cd mobile
flutter build apk --release
```
Üretilen APK `mobile/build/app/outputs/flutter-apk/app-release.apk` dizinindedir.

---

## 🗂️ Proje Yapısı

```
media-downloader-hub/
├── main.py                  # Masaüstü GUI uygulama ana giriş noktası
├── build.py                 # PyInstaller otomatik Windows .exe derleme betiği
├── deploy_exe.py            # Masaüstü dağıtım ve kısayol güncelleme betiği
├── test_backend.py          # FastAPI REST API doğrulama ve otomasyon test betiği
├── requirements.txt         # Python bağımlılıkları
├── README.md                # Proje dokümantasyonu
├── LICENSE                  # MIT Lisansı
├── backend/                 # FastAPI REST API & Görev Yöneticisi
│   ├── main.py              # API endpoint'leri ve CORS yapılandırması
│   └── task_manager.py      # İlerleme durumu ve asenkron görev takibi
├── downloader/
│   ├── __init__.py
│   ├── engine.py            # yt-dlp bağlantı stabilizasyonu ve indirme motoru
│   └── utils.py             # URL doğrulama, dosya adı temizleme ve metrik biçimlendiriciler
├── subtitle/
│   ├── __init__.py
│   └── engine.py            # faster-whisper deşifre, ASS şablonları, auto-splitter & FFmpeg motoru
├── mobile/                  # Flutter Mobil Uygulama
│   ├── lib/

---

## 💻 Teknoloji Yığını (Tech Stack)

| Bileşen | Teknoloji | Açıklama |
| :--- | :--- | :--- |
| **GUI Framework** | `CustomTkinter` | Modern karanlık tema ve responsive bileşenler |
| **Media Downloader** | `yt-dlp` | Çoklu platform video/ses akış indirme motoru |
| **Speech Recognition** | `faster-whisper` | CTranslate2 tabanlı yüksek hızlı OpenAI Whisper modeli |
| **Translation Engine**| `deep-translator` | Google Translate / DeepL çeviri entegrasyonu |
| **Media Processing** | `FFmpeg` | Video işleme, filtreleme ve ASS/SRT hardsub gömme |
| **Bundler** | `PyInstaller` | Bağımsız Windows `.exe` oluşturucu |

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır. Serbestçe kullanılabilir, değiştirilebilir ve dağıtılabilir.
