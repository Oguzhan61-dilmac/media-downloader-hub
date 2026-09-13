import threading
import os
import sys
from pathlib import Path
from typing import Callable, Optional, Dict, Any

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from downloader.utils import format_bytes, format_speed, format_seconds, clean_filename
from subtitle.engine import process_auto_subtitles


class DownloaderTask:
    def __init__(
        self,
        url: str,
        output_dir: str,
        format_option: str,
        on_progress: Callable[[Dict[str, Any]], None],
        on_completion: Callable[[bool, str, Optional[Dict[str, Any]]], None],
        on_log: Optional[Callable[[str], None]] = None,
        auto_subtitle: bool = False,
        sub_source_lang: str = "ru",
        sub_target_lang: str = "tr",
        on_sub_progress: Optional[Callable[[int, str, float, str], None]] = None
    ):
        self.url = url
        self.output_dir = output_dir
        self.format_option = format_option
        self.on_progress = on_progress
        self.on_completion = on_completion
        self.on_log = on_log
        self.auto_subtitle = auto_subtitle
        self.sub_source_lang = sub_source_lang
        self.sub_target_lang = sub_target_lang
        self.on_sub_progress = on_sub_progress
        
        self.cancel_requested = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the download process in a background daemon thread."""
        self.cancel_requested = False
        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def cancel(self):
        """Signals the downloader task to cancel."""
        self.cancel_requested = True
        self._log("İndirme iptal isteği gönderildi...")

    def _log(self, message: str):
        if self.on_log:
            try:
                self.on_log(message)
            except Exception:
                pass

    def _get_format_spec(self) -> Dict[str, Any]:
        """Maps user selection to yt-dlp format parameters."""
        fmt = self.format_option.strip()
        opts = {}

        if "Sadece Ses" in fmt or "MP3" in fmt:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        elif "1080p" in fmt:
            opts["format"] = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        elif "720p" in fmt:
            opts["format"] = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        elif "480p" in fmt:
            opts["format"] = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best"
        else:  # En İyi Kalite MP4 (Default)
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        return opts

    def _progress_hook(self, d: Dict[str, Any]):
        """yt-dlp progress hook called periodically during download."""
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Kullanıcı tarafından iptal edildi.")

        status = d.get("status")
        
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)
            filename = d.get("filename", "")

            percent = (downloaded / total * 100.0) if total > 0 else 0.0

            progress_data = {
                "status": "downloading",
                "percent": min(100.0, max(0.0, percent)),
                "downloaded_bytes": downloaded,
                "total_bytes": total,
                "size_str": f"{format_bytes(downloaded)} / {format_bytes(total)}" if total > 0 else f"{format_bytes(downloaded)}",
                "speed_str": format_speed(speed),
                "eta_str": format_seconds(eta),
                "filename": os.path.basename(filename) if filename else "",
                "raw_info": d
            }
            self.on_progress(progress_data)

        elif status == "finished":
            filename = d.get("filename", "")
            progress_data = {
                "status": "processing",
                "percent": 100.0,
                "size_str": "Tamamlandı - İşleniyor...",
                "speed_str": "0 B/s",
                "eta_str": "00:00",
                "filename": os.path.basename(filename) if filename else "",
                "raw_info": d
            }
            self.on_progress(progress_data)

    def _run_download(self):
        if yt_dlp is None:
            self.on_completion(False, "yt-dlp kütüphanesi yüklü değil! Lütfen requirements.txt içindeki paketleri yükleyin.", None)
            return

        out_template = os.path.join(self.output_dir, "%(title)s.%(ext)s")
        
        ydl_opts = {
            "outtmpl": out_template,
            "progress_hooks": [self._progress_hook],
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            # Windows long path fix & compatibility
            "windowsfilenames": True,
            # Timeout, retries & chunk size stability settings for googlevideo streams
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "http_chunk_size": 10485760,  # 10MB chunking to prevent throttling & timeout
            "buffersize": 1024 * 64,
            "concurrent_fragment_downloads": 1,
            # YouTube 403 Forbidden prevention & bot protection bypass
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                }
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        # Merge format specs
        ydl_opts.update(self._get_format_spec())

        self._log(f"İndirme başlatılıyor: {self.url}")
        self._log(f"Hedef Dizün: {self.output_dir}")
        self._log(f"Format Modu: {self.format_option}")

        info_dict = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                
            if self.cancel_requested:
                self.on_completion(False, "İndirme kullanıcı tarafından iptal edildi.", None)
                return

            video_title = info_dict.get("title", "Medya Dosyası") if info_dict else "Medya Dosyası"
            downloaded_file = ydl.prepare_filename(info_dict) if info_dict else None

            # Fallback file search if prepare_filename doesn't find exact match
            if downloaded_file and not os.path.exists(downloaded_file):
                ext = info_dict.get("ext", "mp4")
                possible_file = os.path.join(self.output_dir, f"{video_title}.{ext}")
                if os.path.exists(possible_file):
                    downloaded_file = possible_file

            self._log(f"Başarıyla indirildi: {video_title}")

            # Trigger Auto Subtitle Module if requested
            if self.auto_subtitle and downloaded_file and os.path.exists(downloaded_file):
                self._log("Otomatik Türkçe Altyazı Ekleme modülü başlatılıyor...")
                try:
                    sub_res = process_auto_subtitles(
                        video_path=downloaded_file,
                        output_dir=self.output_dir,
                        source_lang=self.sub_source_lang,
                        target_lang=self.sub_target_lang,
                        progress_callback=self.on_sub_progress,
                        log_callback=self._log,
                        cancel_check=lambda: self.cancel_requested
                    )
                    final_video = sub_res.get("video", downloaded_file)
                    self.on_completion(
                        True,
                        f"Video indirildi ve Türkçe altyazı eklendi!\nDosya: '{os.path.basename(final_video)}'",
                        info_dict
                    )
                except Exception as sub_ex:
                    self._log(f"[HATA] Otomatik Altyazı Ekleme Başarısız: {sub_ex}")
                    self.on_completion(
                        True,
                        f"Video indirildi fakat altyazı eklenirken hata oluştu:\n{sub_ex}\nDosya: '{os.path.basename(downloaded_file)}'",
                        info_dict
                    )
            else:
                self.on_completion(True, f"İndirme tamamlandı:\n'{video_title}'", info_dict)

        except yt_dlp.utils.DownloadCancelled:
            self._log("İndirme iptal edildi.")
            self.on_completion(False, "İndirme işlemi iptal edildi.", None)

        except yt_dlp.utils.DownloadError as de:
            err_msg = str(de)
            self._log(f"İndirme Hatası: {err_msg}")
            
            user_err = "İndirme sırasında bir hata oluştu."
            if "Unsupported URL" in err_msg or "is not a valid URL" in err_msg:
                user_err = "Geçersiz veya desteklenmeyen video adresi (URL).\nLütfen bağlantıyı kontrol edin."
            elif "Private video" in err_msg:
                user_err = "Bu video gizli veya erişime kapalı."
            elif "Video unavailable" in err_msg:
                user_err = "Video bulunamadı veya silinmiş."
            elif "HTTP Error 404" in err_msg:
                user_err = "Sayfa bulunamadı (404 Error)."
            elif "HTTP Error 403" in err_msg or "Forbidden" in err_msg:
                user_err = "Erişim reddedildi (403 Forbidden). Bağlantı veya sunucu kısıtlaması."
            else:
                clean_err = err_msg.split("\n")[0] if "\n" in err_msg else err_msg
                user_err = f"İndirme başarısız:\n{clean_err}"

            self.on_completion(False, user_err, None)

        except Exception as ex:
            self._log(f"Bilinmeyen Hata: {str(ex)}")
            self.on_completion(False, f"Beklenmeyen bir hata oluştu:\n{str(ex)}", None)

