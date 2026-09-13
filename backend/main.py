import os
import sys
import tempfile
import pathlib
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from downloader.engine import DownloaderTask
from backend.task_manager import task_manager

app = FastAPI(
    title="Media Downloader Hub REST API",
    description="Asynchronous REST API for video downloading and AI auto-subtitles",
    version="1.0.0"
)

# Enable CORS for mobile app requests (Android/iOS/Web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    url: str
    auto_subtitle: bool = True
    target_lang: str = "tr"
    format_option: str = "best"

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "Media Downloader Hub REST API",
        "version": "1.0.0"
    }

@app.post("/api/process")
def process_video(req: ProcessRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Geçerli bir URL giriniz.")

    # Create task record
    task_id = task_manager.create_task(
        url=req.url.strip(),
        auto_subtitle=req.auto_subtitle,
        target_lang=req.target_lang
    )

    # Prepare temporary output directory for task
    temp_dir = os.path.join(tempfile.gettempdir(), "media_downloader_hub", task_id)
    os.makedirs(temp_dir, exist_ok=True)

    # Progress Callbacks
    def _on_progress(pdata):
        pct = pdata.get("percent_float", 0.0)
        # Download phase takes 0% to 50% if auto_subtitle enabled, else 0% to 100%
        scaled_pct = (pct * 0.5) if req.auto_subtitle else pct
        speed = pdata.get("speed_str", "")
        eta = pdata.get("eta_str", "")
        detail = f"Hız: {speed} • Kalan: {eta}" if speed else "İndiriliyor..."
        
        task_manager.update_task(
            task_id,
            status="processing",
            progress_pct=round(scaled_pct, 1),
            step_name="1/3 Video İndiriliyor...",
            detail=detail
        )

    def _on_sub_progress(step_idx, step_name, sub_pct, detail):
        # Subtitle phase scales from 50% to 100%
        scaled_pct = 50.0 + (sub_pct * 0.5)
        task_manager.update_task(
            task_id,
            status="processing",
            progress_pct=round(scaled_pct, 1),
            step_name=f"Altyazı: {step_name}",
            detail=detail
        )

    def _on_completion(success, msg, extra_info):
        if success:
            file_path = None
            if extra_info and isinstance(extra_info, dict):
                # If subtitled video was created, prefer it
                if extra_info.get("subtitled_video") and os.path.exists(extra_info["subtitled_video"]):
                    file_path = extra_info["subtitled_video"]
                elif extra_info.get("downloaded_file") and os.path.exists(extra_info["downloaded_file"]):
                    file_path = extra_info["downloaded_file"]

            if file_path and os.path.exists(file_path):
                task_manager.update_task(
                    task_id,
                    status="completed",
                    progress_pct=100.0,
                    step_name="İşlem Tamamlandı 🎉",
                    detail="Video indirmeye hazır.",
                    file_path=file_path
                )
            else:
                task_manager.update_task(
                    task_id,
                    status="failed",
                    step_name="Hata Oluştu ❌",
                    error="Çıktı dosyası oluşturulamadı."
                )
        else:
            task_manager.update_task(
                task_id,
                status="failed",
                step_name="Hata Oluştu ❌",
                error=msg or "İşlem sırasında hata oluştu."
            )

    # Create & Start Downloader Task
    task_runner = DownloaderTask(
        url=req.url.strip(),
        output_dir=temp_dir,
        format_option=req.format_option,
        on_progress=_on_progress,
        on_completion=_on_completion,
        auto_subtitle=req.auto_subtitle,
        sub_source_lang="auto",
        sub_target_lang=req.target_lang,
        on_sub_progress=_on_sub_progress
    )

    task_manager.update_task(
        task_id,
        status="processing",
        progress_pct=0.0,
        step_name="İşlem Başlatılıyor...",
        detail="Sunucu bağlantısı sağlandı.",
        task_runner=task_runner
    )

    task_runner.start()

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "İşlem başarıyla başlatıldı."
    }

@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    task_info = task_manager.get_task(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Belirtilen görev bulunamadı.")
    return task_info

@app.get("/api/download/{task_id}")
def download_task_file(task_id: str):
    file_path = task_manager.get_task_file_path(task_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Video henüz tamamlanmadı veya dosya bulunamadı.")
    
    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
