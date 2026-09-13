# 🎬 Media Downloader Hub

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-blueviolet.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![faster-whisper](https://img.shields.io/badge/AI-faster--whisper-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![FFmpeg](https://img.shields.io/badge/Media-FFmpeg-green.svg)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Media Downloader Hub**, YouTube, Rutube, TikTok ve Instagram Reels gibi populer platformlardan yüksek kalitede video indiren, yapay zeka (`faster-whisper`) ile otomatik ses analizi yapıp Türkçe dahil 7 dilde dikey formatlı (Shorts/Reels) ritmik altyazıları doğrudan videoya gömen (hardsub) gelişmiş bir masaüstü uygulamasıdır.

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
- 🌍 **Çoklu Hedef Dil Çevirisi & Bypass Mimarisi**:
  - Türkçe (`tr`), İngilizce (`en`), İspanyolca (`es`), Almanca (`de`), Fransızca (`fr`), Arapça (`ar`) ve Rusça (`ru`) çeviri desteği.
  - Kaynak ve hedef dil aynı olduğunda gereksiz çeviri adımı otomatik atlanır (Bypass).
- 🎨 **Referans Çözünürlüklü Dinamik Tipografi**:
  - `PlayResX=1080, PlayResY=1920` sabit referans düzlemi sayesinde video çözünürlüğü ne olursa olsun font boyut sapması engellenir.
  - `FontSize=42`, `Alignment=2` (alt-orta), `MarginV=120` ile ekran altı butonların üstünde, yüz ve göğüs alanlarının altında zarif ve okunaklı görünüm.
- 📁 **Esnek Dizin Seçimi & Ayar Kalıcılığı**:
  - İndirme dizini tek tıkla özelleştirilebilir ve `config.json` ile oturumlar arasında korunur.
- 🌙 **Modern Dark Mode Arayüzü**:
  - CustomTkinter ile tasarlanmış, kilitlenmeyen arka plan iş parçacıklı (`threading.Thread`) estetik ve akıcı kullanıcı deneyimi.

---

## 🛠️ Kurulum & Çalıştırma

### 1. Sistem Gereksinimleri
- **Python**: 3.9 veya daha üzeri.
- **FFmpeg**: Altyazı gömme (hardsub) işlemleri için sisteminizde `ffmpeg` ve `ffprobe` kurulu ve PATH'e eklenmiş olmalıdır.

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

### 4. Uygulamayı Çalıştırın

```bash
python main.py
```

---

## 📦 PyInstaller ile Masaüstü (.EXE) Derleme

Projeyi Python kurulu olmayan bilgisayarlarda çalışabilen **penceresiz (no-console)** bağımsız bir `.exe` dosyasına dönüştürmek için:

```bash
python build.py
```

Derleme tamamlandığında oluşturulan executable dosyası `dist/MediaDownloaderHub.exe` dizininde hazır olacaktır. Masaüstü kısayollarını otomatik oluşturmak ve dağıtmak için `python deploy_exe.py` komutunu kullanabilirsiniz.

---

## 🗂️ Proje Yapısı

```
media-downloader-hub/
├── main.py                  # Uygulama ana giriş noktası (penceresiz başlatma korumalı)
├── build.py                 # PyInstaller otomatik derleme betiği
├── deploy_exe.py            # Masaüstü dağıtım ve kısayol güncelleme betiği
├── requirements.txt         # Proje bağımlılıkları
├── README.md                # Proje dokümantasyonu
├── LICENSE                  # MIT Lisansı
├── downloader/
│   ├── __init__.py
│   ├── engine.py            # yt-dlp bağlantı stabilizasyonu ve arka plan indirme motoru
│   └── utils.py             # URL doğrulama, dosya adı temizleme ve metrik biçimlendiriciler
├── subtitle/
│   ├── __init__.py
│   └── engine.py            # faster-whisper deşifre, kelime zamanlaması, çeviri ve FFmpeg hardsub motoru
└── ui/
    ├── __init__.py
    ├── app.py               # CustomTkinter GUI ve olay yönetimi
    └── theme.py             # Renk paleti, stil kuralları ve sabitler
```

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
