"""
Media Downloader Hub - web API.

Run locally:   python -m uvicorn backend.main:app --port 8000
Then open:     http://127.0.0.1:8000   (the site in /web is served by this app)
"""
import mimetypes
import os
import shutil
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Deque, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from downloader.engine import DownloaderTask  # noqa: E402
from downloader.utils import is_valid_url, is_public_http_url, is_youtube_url, format_seconds  # noqa: E402
from backend.config import load_settings  # noqa: E402
from backend.task_manager import task_manager  # noqa: E402

settings = load_settings()
os.makedirs(settings.data_dir, exist_ok=True)

WEB_DIR = os.path.join(PROJECT_ROOT, "web")

# Quality choices offered by the site -> option strings understood by DownloaderTask.
# "best" is capped at 1080p on the server to keep files and download times reasonable.
FORMAT_MAP = {
    "best": "1080p Full HD MP4",
    "720p": "720p HD MP4",
    "480p": "480p SD MP4",
    "mp3": "Sadece Ses (MP3 Yüksek Kalite)",
}
LANGS = {"tr", "en", "es", "de", "fr", "ar", "ru"}
STYLES = {"hormozi", "minimalist", "cyberpunk"}
POSITIONS = {"bottom", "center", "top"}


# ---------------------------------------------------------------- rate limit
class RateLimiter:
    """Sliding one-hour window per client IP, kept in memory."""

    def __init__(self, limit_per_hour: int):
        self.limit = limit_per_hour
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter(settings.rate_limit_per_hour)
executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs, thread_name_prefix="job")

youtube_health: Dict[str, Any] = {"ok": None, "checked_at": None, "error": None}
_stop_event = threading.Event()


def _youtube_options(url: str) -> Dict[str, Any]:
    """Proxy / PO token / cookie options for a URL. Only YouTube goes through WARP."""
    if is_youtube_url(url):
        extractor_args = None
        if settings.pot_base_url:
            extractor_args = {"youtubepot-bgutilhttp": {"base_url": [settings.pot_base_url]}}
        return {
            "proxy": settings.youtube_proxy,
            "extractor_args": extractor_args,
            "cookies_file": settings.youtube_cookies_file,
        }
    return {"proxy": settings.other_proxy, "extractor_args": None, "cookies_file": None}


# ---------------------------------------------------------------- background loops
def _cleanup_loop():
    ttl = settings.file_ttl_min * 60
    while not _stop_event.wait(60):
        try:
            cleanup_expired(ttl)
        except Exception as ex:  # never let the cleaner die
            print(f"[cleanup] {ex}", flush=True)


def cleanup_expired(ttl_sec: float):
    """Deletes finished jobs' files after the TTL, plus orphan folders left by a restart."""
    for task_id, folder in task_manager.expired(ttl_sec):
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        task_manager.remove(task_id)

    known = set(task_manager.known_dirs())
    now = time.time()
    for name in os.listdir(settings.data_dir):
        path = os.path.abspath(os.path.join(settings.data_dir, name))
        if path in known or not os.path.isdir(path):
            continue
        try:
            if now - os.path.getmtime(path) > ttl_sec:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def run_youtube_health_check() -> bool:
    """Downloads the smallest audio stream of a short public video through the real pipeline."""
    probe_dir = tempfile.mkdtemp(prefix="mdh_probe_")
    result: Dict[str, Any] = {}

    def _done(success, msg, extra):
        result["ok"] = bool(success)
        result["msg"] = msg

    try:
        DownloaderTask(
            url=settings.health_check_url,
            output_dir=probe_dir,
            format_option="__probe__",
            on_progress=lambda _p: None,
            on_completion=_done,
            **_youtube_options(settings.health_check_url),
        ).run()
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)

    ok = result.get("ok", False)
    youtube_health.update(ok=ok, checked_at=time.time(), error=None if ok else result.get("msg"))
    print(f"[health] YouTube {'OK' if ok else 'FAILED: ' + str(result.get('msg'))}", flush=True)
    return ok


def _health_loop():
    if _stop_event.wait(15):  # let the PO token / WARP containers start first
        return
    while True:
        try:
            run_youtube_health_check()
        except Exception as ex:
            youtube_health.update(ok=False, checked_at=time.time(), error=str(ex))
        # Re-check sooner while failing so the site recovers quickly
        wait = settings.health_interval_sec if youtube_health.get("ok") else min(600, settings.health_interval_sec)
        if _stop_event.wait(wait):
            return


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_cleanup_loop, daemon=True, name="cleanup").start()
    if settings.health_interval_sec > 0:
        threading.Thread(target=_health_loop, daemon=True, name="yt-health").start()
    yield
    _stop_event.set()


app = FastAPI(
    title="Media Downloader Hub API",
    description="Link yapıştır, indir. İsteğe bağlı yapay zekâ altyazı ve Shorts klipleri.",
    version="2.0.0",
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


# ---------------------------------------------------------------- models
class ProcessRequest(BaseModel):
    url: str = Field(..., max_length=2048)
    format: str = "best"
    auto_subtitle: bool = False
    target_lang: str = "tr"
    auto_split: bool = False
    subtitle_style: str = "hormozi"
    subtitle_position: str = "bottom"
    clean_audio: bool = False


def _client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- job runner
def _run_job(task_id: str, req: ProcessRequest, url: str):
    task = task_manager.get_internal(task_id)
    if not task or task.get("cancel_requested"):
        task_manager.update_task(task_id, status="cancelled", step_name="İptal edildi", finished_at=time.time())
        return

    out_dir = os.path.join(settings.data_dir, task_id)
    subtitle_on = req.auto_subtitle and req.format != "mp3"
    dl_weight = 0.4 if subtitle_on else 1.0  # share of the progress bar used by the download step

    def _on_progress(pdata):
        pct = float(pdata.get("percent", 0.0) or 0.0)
        if pdata.get("status") == "downloading":
            speed, eta = pdata.get("speed_str", ""), pdata.get("eta_str", "")
            detail = f"{pdata.get('size_str', '')} • {speed} • Kalan {eta}".strip(" •")
            step = "Video indiriliyor..."
        else:
            detail, step = "Dosya birleştiriliyor / dönüştürülüyor...", "İşleniyor..."
        task_manager.update_task(
            task_id, status="processing", progress_pct=round(pct * dl_weight, 1), step_name=step, detail=detail,
        )

    def _on_sub_progress(step_idx, step_name, sub_pct, detail):
        # steps 1..3 share the remaining (1 - dl_weight) of the bar equally
        span = (1.0 - dl_weight) * 100.0 / 3.0
        overall = dl_weight * 100.0 + (step_idx - 1) * span + (sub_pct / 100.0) * span
        task_manager.update_task(
            task_id, status="processing", progress_pct=round(min(99.0, overall), 1),
            step_name=f"Altyazı: {step_name}", detail=detail,
        )

    def _on_completion(success, msg, extra):
        now = time.time()
        if not success:
            cancelled = "iptal" in (msg or "").lower()
            task_manager.update_task(
                task_id,
                status="cancelled" if cancelled else "failed",
                step_name="İptal edildi" if cancelled else "Hata oluştu",
                error=msg or "İşlem sırasında hata oluştu.",
                finished_at=now,
            )
            return

        extra = extra or {}
        file_path = None
        for key in ("subtitled_video", "downloaded_file"):
            candidate = extra.get(key)
            if candidate and os.path.exists(candidate):
                file_path = candidate
                break

        if not file_path:
            task_manager.update_task(
                task_id, status="failed", step_name="Hata oluştu",
                error="Çıktı dosyası oluşturulamadı.", finished_at=now,
            )
            return

        detail = "Dosya indirmeye hazır."
        if subtitle_on and not extra.get("subtitled_video"):
            detail = "Video hazır, ancak altyazı eklenemedi."
        task_manager.update_task(
            task_id,
            status="completed",
            progress_pct=100.0,
            step_name="Hazır",
            detail=detail,
            file_path=file_path,
            filename=os.path.basename(file_path),
            filesize=os.path.getsize(file_path),
            finished_at=now,
            expires_at=now + settings.file_ttl_min * 60,
        )

    runner = DownloaderTask(
        url=url,
        output_dir=out_dir,
        format_option=FORMAT_MAP[req.format],
        on_progress=_on_progress,
        on_completion=_on_completion,
        auto_subtitle=subtitle_on,
        sub_source_lang="auto",
        sub_target_lang=req.target_lang,
        on_sub_progress=_on_sub_progress,
        auto_split=req.auto_split,
        subtitle_style=req.subtitle_style,
        subtitle_position=req.subtitle_position,
        clean_audio=req.clean_audio,
        max_duration=settings.max_subtitle_duration_sec if subtitle_on else settings.max_duration_sec,
        max_filesize=settings.max_filesize_mb * 1024 * 1024,
        **_youtube_options(url),
    )

    task_manager.update_task(
        task_id, status="processing", step_name="Başlatılıyor...", detail="Video bilgileri alınıyor...",
        task_runner=runner, dir=out_dir,
    )
    try:
        runner.run()
    except Exception as ex:  # safety net, DownloaderTask normally reports its own errors
        task_manager.update_task(task_id, status="failed", step_name="Hata oluştu", error=str(ex), finished_at=time.time())


# ---------------------------------------------------------------- endpoints
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "Media Downloader Hub",
        "version": app.version,
        "youtube": youtube_health,
        "queue": task_manager.active_count(),
        "limits": {
            "max_duration_sec": settings.max_duration_sec,
            "max_duration_str": format_seconds(settings.max_duration_sec),
            "max_subtitle_duration_sec": settings.max_subtitle_duration_sec,
            "max_subtitle_duration_str": format_seconds(settings.max_subtitle_duration_sec),
            "max_filesize_mb": settings.max_filesize_mb,
            "file_ttl_min": settings.file_ttl_min,
            "rate_limit_per_hour": settings.rate_limit_per_hour,
            "subtitles_enabled": settings.allow_subtitles,
        },
        "desktop_app_url": settings.desktop_app_url,
    }


@app.post("/api/process")
def process_video(req: ProcessRequest, request: Request):
    url = req.url.strip()
    if not is_valid_url(url):
        raise HTTPException(status_code=400, detail="Geçerli bir http(s) bağlantısı girin.")
    if not settings.allow_private_urls and not is_public_http_url(url):
        raise HTTPException(status_code=400, detail="Bu adrese erişilemiyor. Herkese açık bir video bağlantısı girin.")
    if req.format not in FORMAT_MAP:
        raise HTTPException(status_code=400, detail="Geçersiz kalite seçimi.")
    if req.auto_subtitle:
        if not settings.allow_subtitles:
            raise HTTPException(status_code=400, detail="Altyazı özelliği bu sunucuda kapalı.")
        if req.target_lang not in LANGS or req.subtitle_style not in STYLES or req.subtitle_position not in POSITIONS:
            raise HTTPException(status_code=400, detail="Geçersiz altyazı ayarı.")

    if task_manager.active_count() >= settings.max_queue:
        raise HTTPException(status_code=503, detail="Sunucu şu an çok yoğun. Birkaç dakika sonra tekrar deneyin.")

    client = _client_ip(request)
    if not rate_limiter.allow(client):
        raise HTTPException(
            status_code=429,
            detail=f"Saatlik indirme sınırına ({settings.rate_limit_per_hour}) ulaştınız. Biraz sonra tekrar deneyin.",
        )

    task_id = task_manager.create_task(
        url=url, auto_subtitle=req.auto_subtitle, target_lang=req.target_lang, client_ip=client,
    )
    executor.submit(_run_job, task_id, req, url)
    return {"task_id": task_id, "status": "queued", "message": "İşlem sıraya alındı."}


@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    task_info = task_manager.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Görev bulunamadı ya da süresi doldu.")
    return task_info


@app.post("/api/cancel/{task_id}")
def cancel_task(task_id: str):
    task = task_manager.get_internal(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı.")
    task_manager.update_task(task_id, cancel_requested=True)
    runner: Optional[DownloaderTask] = task.get("task_runner")
    if runner:
        runner.cancel()
    elif task["status"] == "queued":
        task_manager.update_task(task_id, status="cancelled", step_name="İptal edildi", finished_at=time.time())
    return {"task_id": task_id, "status": "cancelling"}


@app.get("/api/download/{task_id}")
def download_task_file(task_id: str):
    file_path = task_manager.get_task_file_path(task_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya hazır değil ya da süresi doldu.")

    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    # FileResponse builds an RFC 5987 Content-Disposition itself, so Turkish
    # characters and emoji in titles are safe. Do not set the header by hand.
    return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type=media_type)


# The website (web/index.html) is served from the same origin, so no CORS is needed.
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)
