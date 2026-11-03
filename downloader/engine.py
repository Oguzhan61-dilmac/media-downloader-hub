import threading
import os
from typing import Callable, Optional, Dict, Any

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from downloader.utils import format_bytes, format_speed, format_seconds
from subtitle.engine import process_auto_subtitles


class DownloadRejected(Exception):
    """Raised when a video is refused before downloading (too long, live stream...)."""


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
        sub_source_lang: str = "auto",
        sub_target_lang: str = "tr",
        on_sub_progress: Optional[Callable[[int, str, float, str], None]] = None,
        auto_split: bool = False,
        subtitle_style: str = "hormozi",
        subtitle_position: str = "bottom",
        clean_audio: bool = False,
        # --- Server / web options (all optional, desktop app leaves them unset) ---
        proxy: Optional[str] = None,
        cookies_file: Optional[str] = None,
        extractor_args: Optional[Dict[str, Dict[str, list]]] = None,
        max_duration: Optional[int] = None,
        max_filesize: Optional[int] = None,
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
        self.auto_split = auto_split
        self.subtitle_style = subtitle_style
        self.subtitle_position = subtitle_position
        self.clean_audio = clean_audio
        self.proxy = proxy
        self.cookies_file = cookies_file
        self.extractor_args = extractor_args
        self.max_duration = max_duration
        self.max_filesize = max_filesize

        self.cancel_requested = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the download process in a background daemon thread (desktop app)."""
        self.cancel_requested = False
        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def run(self):
        """Runs the download synchronously in the caller's thread (web job queue)."""
        self._run_download()

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

    def _is_audio_only(self) -> bool:
        fmt = self.format_option.strip()
        return "Sadece Ses" in fmt or "MP3" in fmt.upper()

    def _get_format_spec(self) -> Dict[str, Any]:
        """Maps user selection to yt-dlp format parameters."""
        fmt = self.format_option.strip()
        opts: Dict[str, Any] = {}

        if fmt == "__probe__":
            # Smallest possible real download, used by the server's YouTube health check
            opts["format"] = "worstaudio/worst"
        elif self._is_audio_only():
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

        if fmt != "__probe__" and not self._is_audio_only():
            # Separate video+audio streams that can't go into MP4 (e.g. webm+opus) are still merged into MP4
            opts["merge_output_format"] = "mp4"

        return opts

    def _progress_hook(self, d: Dict[str, Any]):
        """yt-dlp progress hook called periodically during download."""
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadCancelled("Kullanıcı tarafından iptal edildi.")

        status = d.get("status")

        if status == "downloading":
            # yt-dlp may send these keys with a None value, so `or` instead of .get() defaults
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed")
            eta = d.get("eta")
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

    def _build_ydl_opts(self) -> Dict[str, Any]:
        ydl_opts: Dict[str, Any] = {
            # .150B keeps very long titles from exceeding filesystem name limits
            "outtmpl": os.path.join(self.output_dir, "%(title).150B.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "noplaylist": True,          # a link with &list= downloads only that video
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "windowsfilenames": True,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "http_chunk_size": 10485760,  # 10MB chunks
        }
        # Note: no custom User-Agent / player_client overrides and TLS verification stays ON.
        # yt-dlp picks per-client headers itself; forcing a desktop Chrome UA on mobile
        # clients is a common cause of 403s. Keep yt-dlp updated instead.

        if self.proxy:
            ydl_opts["proxy"] = self.proxy
        if self.cookies_file and os.path.isfile(self.cookies_file):
            ydl_opts["cookiefile"] = self.cookies_file
        if self.extractor_args:
            ydl_opts["extractor_args"] = self.extractor_args
        if self.max_filesize:
            ydl_opts["max_filesize"] = int(self.max_filesize)

        ydl_opts.update(self._get_format_spec())
        return ydl_opts

    def _check_limits(self, info: Dict[str, Any]):
        if info.get("_type") in ("playlist", "multi_video") and not info.get("formats"):
            raise DownloadRejected("Oynatma listeleri desteklenmiyor. Lütfen tek bir videonun bağlantısını girin.")
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            raise DownloadRejected("Canlı yayınlar indirilemiyor.")
        duration = info.get("duration")
        if self.max_duration and duration and duration > self.max_duration:
            raise DownloadRejected(
                f"Video çok uzun ({format_seconds(duration)}). "
                f"Bu seçenek için en fazla {format_seconds(self.max_duration)} uzunluğunda videolar indirilebiliyor."
            )

    @staticmethod
    def _resolve_output_file(info: Optional[Dict[str, Any]]) -> Optional[str]:
        """Final file path after merging/post-processing (e.g. the .mp3, not the source .webm)."""
        if not info:
            return None
        for item in info.get("requested_downloads") or []:
            path = item.get("filepath")
            if path and os.path.exists(path):
                return path
        path = info.get("filepath")
        if path and os.path.exists(path):
            return path
        return None

    def _run_download(self):
        if yt_dlp is None:
            self.on_completion(False, "yt-dlp kütüphanesi yüklü değil! Lütfen requirements.txt içindeki paketleri yükleyin.", None)
            return

        os.makedirs(self.output_dir, exist_ok=True)
        ydl_opts = self._build_ydl_opts()

        self._log(f"İndirme başlatılıyor: {self.url}")
        self._log(f"Hedef Dizin: {self.output_dir}")
        self._log(f"Format Modu: {self.format_option}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Read metadata first so length/live limits are checked before any bytes are downloaded
                info = ydl.extract_info(self.url, download=False)
                if info is None:
                    raise DownloadRejected("Video bilgisi alınamadı.")
                self._check_limits(info)
                info = ydl.process_ie_result(info, download=True)

            if self.cancel_requested:
                self.on_completion(False, "İndirme kullanıcı tarafından iptal edildi.", None)
                return

            video_title = info.get("title", "Medya Dosyası") if info else "Medya Dosyası"
            downloaded_file = self._resolve_output_file(info)

            if not downloaded_file:
                limit_note = ""
                if self.max_filesize:
                    limit_note = f" Dosya {format_bytes(self.max_filesize)} sınırını aşıyor olabilir."
                self.on_completion(False, f"Video indirilemedi, çıktı dosyası oluşmadı.{limit_note}", None)
                return

            self._log(f"Başarıyla indirildi: {video_title}")
            result: Dict[str, Any] = {
                "title": video_title,
                "downloaded_file": downloaded_file,
                "subtitled_video": None,
                "srt": None,
                "extractor": info.get("extractor_key"),
            }

            if self.auto_subtitle and not self._is_audio_only():
                self._log("Otomatik altyazı modülü başlatılıyor...")
                try:
                    sub_res = process_auto_subtitles(
                        video_path=downloaded_file,
                        output_dir=self.output_dir,
                        source_lang=self.sub_source_lang,
                        target_lang=self.sub_target_lang,
                        subtitle_style=self.subtitle_style,
                        subtitle_position=self.subtitle_position,
                        clean_audio=self.clean_audio,
                        auto_split=self.auto_split,
                        progress_callback=self.on_sub_progress,
                        log_callback=self._log,
                        cancel_check=lambda: self.cancel_requested
                    )
                    result["srt"] = sub_res.get("srt") or None
                    if sub_res.get("burned"):
                        result["subtitled_video"] = sub_res.get("video")
                        self.on_completion(
                            True,
                            f"Video indirildi ve altyazı eklendi!\nDosya: '{os.path.basename(sub_res['video'])}'",
                            result
                        )
                    else:
                        reason = sub_res.get("note") or "Altyazı videoya gömülemedi."
                        self.on_completion(
                            True,
                            f"Video indirildi fakat altyazı eklenemedi: {reason}\nDosya: '{os.path.basename(downloaded_file)}'",
                            result
                        )
                except Exception as sub_ex:
                    if self.cancel_requested:
                        self.on_completion(False, "İşlem kullanıcı tarafından iptal edildi.", None)
                        return
                    self._log(f"[HATA] Otomatik Altyazı Ekleme Başarısız: {sub_ex}")
                    self.on_completion(
                        True,
                        f"Video indirildi fakat altyazı eklenirken hata oluştu:\n{sub_ex}\nDosya: '{os.path.basename(downloaded_file)}'",
                        result
                    )
            else:
                self.on_completion(True, f"İndirme tamamlandı:\n'{video_title}'", result)

        except DownloadRejected as rej:
            self._log(f"Reddedildi: {rej}")
            self.on_completion(False, str(rej), None)

        except yt_dlp.utils.DownloadCancelled:
            self._log("İndirme iptal edildi.")
            self.on_completion(False, "İndirme işlemi iptal edildi.", None)

        except yt_dlp.utils.DownloadError as de:
            err_msg = str(de)
            self._log(f"İndirme Hatası: {err_msg}")
            self.on_completion(False, friendly_error(err_msg), None)

        except Exception as ex:
            self._log(f"Bilinmeyen Hata: {str(ex)}")
            self.on_completion(False, f"Beklenmeyen bir hata oluştu:\n{str(ex)}", None)


def friendly_error(err_msg: str) -> str:
    """Turns a raw yt-dlp error into a short Turkish message."""
    if "Sign in to confirm" in err_msg or "not a bot" in err_msg:
        return ("YouTube bu sunucuyu bot olarak işaretledi. "
                "Biraz sonra tekrar deneyin ya da masaüstü uygulamasını kullanın.")
    if "Unsupported URL" in err_msg or "is not a valid URL" in err_msg:
        return "Geçersiz veya desteklenmeyen video adresi (URL).\nLütfen bağlantıyı kontrol edin."
    if "Private video" in err_msg:
        return "Bu video gizli veya erişime kapalı."
    if "Video unavailable" in err_msg:
        return "Video bulunamadı veya silinmiş."
    if "age" in err_msg.lower() and "confirm" in err_msg.lower():
        return "Bu video yaş doğrulaması istiyor, sunucudan indirilemiyor."
    if "HTTP Error 404" in err_msg:
        return "Sayfa bulunamadı (404 Error)."
    if "HTTP Error 403" in err_msg or "Forbidden" in err_msg:
        return "Erişim reddedildi (403 Forbidden). Bağlantı veya sunucu kısıtlaması."
    if "Requested format is not available" in err_msg:
        return "Seçilen kalite bu video için mevcut değil. Başka bir kalite deneyin."
    clean_err = err_msg.split("\n")[0]
    return f"İndirme başarısız:\n{clean_err}"
