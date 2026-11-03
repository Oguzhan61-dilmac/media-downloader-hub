"""
End-to-end tests for the web API without touching YouTube: a local HTTP server
serves a small generated video, and the real download pipeline (yt-dlp generic
extractor + FFmpeg) fetches it.

Run:  pip install -r requirements-dev.txt && pytest
"""
import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(not FFMPEG, reason="ffmpeg is required for these tests")


@pytest.fixture(scope="session")
def media_server(tmp_path_factory):
    media = tmp_path_factory.mktemp("media")
    src = media / "test.mp4"
    subprocess.run(
        [FFMPEG, "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440",
         "-t", "4", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)],
        check=True,
    )
    shutil.copy(src, media / "Şarkı Güzel ğ.mp4")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(media))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", media
    srv.shutdown()


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    os.environ.update({
        "DATA_DIR": str(tmp_path_factory.mktemp("data")),
        "ALLOW_PRIVATE_URLS": "1",      # the test server is on 127.0.0.1
        "HEALTH_INTERVAL_SEC": "0",     # no YouTube health check in tests
        "RATE_LIMIT_PER_HOUR": "0",
        "MAX_CONCURRENT_JOBS": "2",
    })
    from fastapi.testclient import TestClient
    import backend.main as bm
    with TestClient(bm.app) as c:
        yield c


def _wait(client, task_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = client.get(f"/api/status/{task_id}").json()
        if st["status"] in ("completed", "failed", "cancelled"):
            return st
        time.sleep(0.3)
    raise AssertionError("task did not finish in time")


def test_download_completes_and_file_is_served(client, media_server):
    base, media = media_server
    r = client.post("/api/process", json={"url": f"{base}/test.mp4", "format": "best"})
    assert r.status_code == 200, r.text
    st = _wait(client, r.json()["task_id"])
    assert st["status"] == "completed", st
    assert st["filename"].endswith(".mp4")
    assert "file_path" not in st  # server paths are never exposed

    dl = client.get(f"/api/download/{st['task_id']}")
    assert dl.status_code == 200
    assert len(dl.content) == st["filesize"] > 0
    assert dl.headers["content-type"] == "video/mp4"


def test_turkish_title_downloads(client, media_server):
    base, _ = media_server
    r = client.post("/api/process", json={"url": f"{base}/%C5%9Eark%C4%B1%20G%C3%BCzel%20%C4%9F.mp4"})
    st = _wait(client, r.json()["task_id"])
    assert st["status"] == "completed", st
    dl = client.get(f"/api/download/{st['task_id']}")
    assert dl.status_code == 200
    assert "filename*=utf-8''" in dl.headers["content-disposition"]


def test_mp3_returns_converted_file(client, media_server):
    base, _ = media_server
    r = client.post("/api/process", json={"url": f"{base}/test.mp4", "format": "mp3"})
    st = _wait(client, r.json()["task_id"])
    assert st["status"] == "completed", st
    assert st["filename"].endswith(".mp3")


def test_invalid_input_rejected(client):
    assert client.post("/api/process", json={"url": "ftp://example.com/x"}).status_code == 400
    assert client.post("/api/process", json={"url": "https://example.com/v", "format": "8k"}).status_code == 400
    assert client.get("/api/status/does-not-exist").status_code == 404
    assert client.get("/api/download/does-not-exist").status_code == 404


def test_limits_reject_long_and_live_videos():
    from downloader.engine import DownloaderTask, DownloadRejected
    task = DownloaderTask("https://x", "/tmp", "best", lambda p: None, lambda *a: None, max_duration=600)
    task._check_limits({"duration": 300})  # fine
    with pytest.raises(DownloadRejected, match="uzun"):
        task._check_limits({"duration": 3600})
    with pytest.raises(DownloadRejected, match="Canlı"):
        task._check_limits({"is_live": True})
    with pytest.raises(DownloadRejected, match="listeleri"):
        task._check_limits({"_type": "playlist"})


def test_rate_limit(client, media_server, monkeypatch):
    import backend.main as bm
    limiter = bm.RateLimiter(2)
    monkeypatch.setattr(bm, "rate_limiter", limiter)
    base, _ = media_server
    codes = [client.post("/api/process", json={"url": f"{base}/test.mp4"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_site_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Media Downloader Hub" in r.text


def test_private_addresses_are_blocked():
    from downloader.utils import is_public_http_url
    for url in ("http://127.0.0.1/x", "http://localhost:8000/", "http://169.254.169.254/latest/meta-data",
                "http://10.0.0.5/v.mp4", "http://192.168.1.1/", "http://[::1]/"):
        assert not is_public_http_url(url), url


def test_youtube_detection():
    from downloader.utils import is_youtube_url
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert is_youtube_url("https://music.youtube.com/watch?v=abc")
    assert not is_youtube_url("https://notyoutube.com/watch?v=abc")
    assert not is_youtube_url("https://rutube.ru/video/abc/")


def test_burn_subtitles_with_apostrophe_in_title(tmp_path, media_server):
    from subtitle.engine import burn_subtitles, build_ass_force_style, generate_srt
    _, media = media_server
    video = tmp_path / "Don't Stop Me Now.mp4"
    shutil.copy(media / "test.mp4", video)
    srt = tmp_path / "Don't Stop Me Now_tr.srt"
    srt.write_text(generate_srt([{"start": 0.2, "end": 3.0, "text": "Merhaba dünya bu bir test"}]), encoding="utf-8")
    out = tmp_path / "Don't Stop Me Now_altyazili.mp4"
    ok, err = burn_subtitles(str(video), str(srt), str(out), build_ass_force_style(), FFMPEG)
    assert ok, err
    assert out.stat().st_size > 0


def test_word_timestamps_drive_subtitle_timing():
    from subtitle.engine import generate_srt
    seg = {
        "start": 0.0, "end": 4.0, "text": "bir iki üç dört beş altı yedi",
        "words": [{"start": i * 0.5, "end": i * 0.5 + 0.4, "word": f" {w}"}
                  for i, w in enumerate("bir iki üç dört beş altı yedi".split())],
    }
    srt = generate_srt([seg])
    # second block starts exactly when its first word ("altı", 6th word) is spoken: 2.5 s
    assert "00:00:02,500 -->" in srt
