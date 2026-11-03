# Web Sitesini Ücretsiz Yayınlama (Oracle Cloud Always Free)

Bu rehber, sitenin tamamını Oracle Cloud'un ücretsiz ARM sunucusunda çalıştırır:
link yapıştır → indir, MP3, yapay zekâ altyazı ve Shorts klipleri. Kurulum tek bir
betikle otomatik yapılır; senin yapacağın iş Oracle panelinde birkaç tıklama.

```
Tarayıcı ──HTTPS──> Caddy ──> api (FastAPI + yt-dlp + Whisper + FFmpeg)
                                 ├──> pot  (YouTube PO token sunucusu)
                                 └──> warp (Cloudflare WARP; sadece YouTube trafiği)
```

## 1. Oracle hesabı

1. https://www.oracle.com/cloud/free/ adresinden hesap aç. Kart doğrulaması isteniyor; Always Free kaynaklar için ücret çekilmez.
2. **Home region** seçimi kalıcıdır. ARM sunucular popüler bölgelerde sık sık "Out of host capacity" verir; Frankfurt yerine daha sakin bir Avrupa bölgesi (ör. Amsterdam, Zürih, Stockholm) seçmek işini kolaylaştırır.

## 2. Sunucuyu oluştur

**Compute → Instances → Create instance**

| Ayar | Değer |
|---|---|
| Image | Canonical **Ubuntu 24.04** |
| Shape | **VM.Standard.A1.Flex** (Ampere, ARM) — 2 OCPU, 12 GB RAM (ücretsiz sınır: toplam 4 OCPU / 24 GB) |
| Networking | "Assign a public IPv4 address" açık |
| SSH keys | "Save private key" ile anahtarı indir (sorun çözmek için lazım olur) |
| Advanced options → Management | **Paste cloud-init script** → `deploy/oracle-cloud-init.yaml` dosyasının tamamını yapıştır |

"Out of host capacity" hatası alırsan 1 OCPU / 6 GB ile dene ya da birkaç saat sonra tekrar dene.

## 3. Portları aç (unutulursa site açılmaz)

**Networking → Virtual cloud networks → (VCN) → Security Lists → Default Security List → Add Ingress Rules**

| Source CIDR | Protocol | Destination port |
|---|---|---|
| 0.0.0.0/0 | TCP | 80 |
| 0.0.0.0/0 | TCP | 443 |

## 4. Bekle ve aç

Sunucu kendini 10–20 dakikada kurar (Docker imajları ARM üzerinde derleniyor). Sonra:

```
https://<IP-adresi-tireli>.sslip.io      örnek: 152.70.1.2 → https://152-70-1-2.sslip.io
```

Kurulumu canlı izlemek için:

```bash
ssh -i indirdigin-anahtar.key ubuntu@<IP>
sudo tail -f /var/log/mdh-setup.log
```

## 5. Kendi alan adınla canlıya alma

Önce sslip.io adresinde her şeyin çalıştığını gör, sonra alan adına geç.

1. **Alan adını seç.** İçinde YouTube, Instagram, TikTok gibi marka adları geçmesin. Marka sahipleri bu tür alan adlarını şikâyetle geri alabiliyor.
2. **DNS kayıtları:** `@` ve `www` için **A kaydı → sunucunun IP adresi**.
   Cloudflare DNS kullanıyorsan iki kaydı da **"DNS only" (gri bulut)** yap. Cloudflare, kendi dışında barındırılan video dosyalarının CDN'den geçirilmesini kısıtlıyor; HTTPS sertifikasını zaten Caddy alıyor.
3. **Sunucuda ayarları değiştir:**
   ```bash
   cd /opt/media-downloader-hub/deploy
   sudo nano .env
   #   SITE_ADDRESS=ornek.com, www.ornek.com
   #   CONTACT_EMAIL=iletisim@ornek.com
   sudo docker compose up -d
   ```
   Caddy sertifikayı birkaç dakika içinde alır. `www.ornek.com` otomatik olarak `ornek.com`'a yönlenir.
4. **Bot koruması (ücretsiz):** Cloudflare panelinde **Turnstile → Add widget**, hostname olarak alan adını gir. Verilen anahtarları `.env` içindeki `TURNSTILE_SITE_KEY` ve `TURNSTILE_SECRET_KEY` satırlarına yaz, `sudo docker compose up -d`. Bu, botların sunucunu indirme makinesi olarak kullanmasını engeller.
5. **Yasal sayfalar:** `web/kullanim-sartlari.html` ve `web/gizlilik.html` birer şablon. Yayına almadan önce bir hukukçuya kontrol ettir.
6. **Telif şikâyeti gelirse:** Video ID'sini ya da bağlantının bir parçasını `deploy/config/blocklist.txt` dosyasına yeni satır olarak ekle. Kaydettiğin anda geçerli olur, yeniden başlatma gerekmez.
7. **Arama motoru:** Google Search Console'a siteyi ekle ve `https://ornek.com/sitemap.xml` adresini gönder.
8. **İzleme:** Ücretsiz bir çalışma süresi (uptime) servisine `https://ornek.com/api/health` adresini ekle; site çökerse e-posta alırsın.

**Trafik artınca:** Ücretsiz sunucuda aynı anda 2 iş çalışır, gerisi sıraya girer. 4 OCPU / 24 GB'a çıkarsan `.env` içinde `MAX_CONCURRENT_JOBS=4` yapabilirsin. Whisper (altyazı) en ağır kısım; sunucu zorlanırsa `ALLOW_SUBTITLES=0` ile kapat. Tüm YouTube indirmeleri tek bir WARP çıkışından geçtiği için yoğun kullanımda YouTube bu çıkışı da yavaşlatabilir; saatlik limitler bunu dengelemek için var.

## Kontroller

```bash
cd /opt/media-downloader-hub/deploy

sudo docker compose ps                     # 4 servis "running" olmalı
sudo docker compose logs -f api            # indirme logları, "[health] YouTube OK/FAILED"
sudo docker compose exec warp curl -s https://cloudflare.com/cdn-cgi/trace | grep warp   # warp=on olmalı
curl -s localhost/api/health               # youtube.ok değeri
```

`/api/health` içindeki `youtube.ok` **false** ise site YouTube için otomatik olarak
"masaüstü uygulamasını kullan" uyarısı gösterir; diğer siteler çalışmaya devam eder.
Sunucu her saat (sorun varken 10 dakikada bir) tekrar dener ve düzelince uyarı kalkar.

## YouTube çalışmazsa sırayla dene

1. **Güncelle:** `sudo docker compose restart api` (yt-dlp her başlangıçta en güncel nightly sürüme güncellenir).
2. **WARP bağlantısını yenile:** `sudo docker compose restart warp api`
3. **Çerez (son çare):** *Asla ana hesabını kullanma; hesap kapatılabilir.* Boş bir Google hesabıyla YouTube'a gir, "Get cookies.txt LOCALLY" eklentisiyle `cookies.txt` dışa aktar, sunucuda `deploy/cookies/youtube.txt` olarak kaydet. `.env` dosyasında `YOUTUBE_COOKIES_FILE=/cookies/youtube.txt` satırının başındaki `#`'i kaldır, sonra `sudo docker compose up -d`.

## Ayarlar (`deploy/.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `SITE_ADDRESS` | sslip.io adresi | Alan adın varsa `ornek.com` yaz (DNS A kaydı sunucu IP'sine). Sertifika alınamazsa `:80` ile düz HTTP. |
| `MAX_DURATION_SEC` | 900 | İndirilebilecek en uzun video (saniye) |
| `MAX_SUBTITLE_DURATION_SEC` | 300 | Altyazı/Shorts için en uzun video. Whisper ARM CPU'da yavaştır. |
| `RATE_LIMIT_PER_HOUR` | 15 | Kişi (IP) başına saatlik indirme |
| `FILE_TTL_MIN` | 60 | Dosyaların sunucuda kalma süresi (dakika) |
| `ALLOW_SUBTITLES` | 1 | Sunucu zorlanırsa `0` yap, altyazı stüdyosu kapanır |
| `CONTACT_EMAIL` | boş | Yasal sayfalarda ve telif bildirimi için gösterilen adres |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | boş | İkisi de doluysa bot doğrulaması açılır |

Değişiklikten sonra: `sudo docker compose up -d`

## Güncelleme

GitHub'a yeni kod gönderdikten sonra sunucuda:

```bash
sudo bash /opt/media-downloader-hub/deploy/update.sh
```

## Bilmen gerekenler

- **Bu bir kedi-fare oyunu.** YouTube engellerini sık değiştiriyor; WARP yöntemi bugün çalışıyor ama yarın kapanabilir. Sağlık kontrolü ve masaüstü uygulamasına yönlendirme bu yüzden var.
- **Cloudflare WARP'ın ücretsiz sürümünü** herkese açık bir servis için sunucuda kullanmanın Cloudflare'in şartlarına uygunluğunu kendin kontrol et. İstemezsen `.env` içinde `YOUTUBE_PROXY=` satırını boş bırak.
- **Oracle**, 7 gün boyunca CPU, ağ ve bellek kullanımı %20'nin altında kalan ücretsiz ARM sunucuları geri alabiliyor. Gerçek kullanım varsa sorun olmaz.
- **Telif:** Sitede "yalnızca hakkına sahip olduğun içerikleri indir" uyarısı ve 1 saatlik dosya silme süresi var. Şikâyet gelirse ilgili içeriği engellemen gerekir.
