"""Server settings, read from environment variables (see deploy/.env.example)."""
import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str) -> Optional[str]:
    raw = os.environ.get(name, "").strip()
    return raw or None


@dataclass
class Settings:
    data_dir: str
    max_concurrent_jobs: int
    max_queue: int
    max_duration_sec: int
    max_subtitle_duration_sec: int
    max_filesize_mb: int
    file_ttl_min: int
    rate_limit_per_hour: int
    youtube_proxy: Optional[str]
    other_proxy: Optional[str]
    pot_base_url: Optional[str]
    youtube_cookies_file: Optional[str]
    allow_private_urls: bool
    allow_subtitles: bool
    trust_proxy_headers: bool
    health_check_url: str
    health_interval_sec: int
    desktop_app_url: str
    contact_email: Optional[str]
    turnstile_site_key: Optional[str]
    turnstile_secret_key: Optional[str]
    blocklist_file: Optional[str]
    cors_origins: List[str] = field(default_factory=list)


def load_settings() -> Settings:
    return Settings(
        data_dir=os.environ.get("DATA_DIR") or os.path.join(tempfile.gettempdir(), "media_downloader_hub"),
        max_concurrent_jobs=max(1, _env_int("MAX_CONCURRENT_JOBS", 2)),
        max_queue=max(1, _env_int("MAX_QUEUE", 20)),
        max_duration_sec=_env_int("MAX_DURATION_SEC", 900),
        max_subtitle_duration_sec=_env_int("MAX_SUBTITLE_DURATION_SEC", 300),
        max_filesize_mb=_env_int("MAX_FILESIZE_MB", 500),
        file_ttl_min=max(1, _env_int("FILE_TTL_MIN", 60)),
        rate_limit_per_hour=_env_int("RATE_LIMIT_PER_HOUR", 15),
        youtube_proxy=_env_str("YOUTUBE_PROXY"),
        other_proxy=_env_str("OTHER_PROXY"),
        pot_base_url=_env_str("POT_BASE_URL"),
        youtube_cookies_file=_env_str("YOUTUBE_COOKIES_FILE"),
        allow_private_urls=_env_bool("ALLOW_PRIVATE_URLS", False),
        allow_subtitles=_env_bool("ALLOW_SUBTITLES", True),
        trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
        # "Me at the zoo" (19 s, the first YouTube video) - small and unlikely to disappear
        health_check_url=os.environ.get("HEALTH_CHECK_URL", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
        health_interval_sec=_env_int("HEALTH_INTERVAL_SEC", 3600),
        desktop_app_url=os.environ.get("DESKTOP_APP_URL", "https://github.com/Oguzhan61-dilmac/media-downloader-hub"),
        contact_email=_env_str("CONTACT_EMAIL"),
        # Cloudflare Turnstile bot protection; active only when both keys are set
        turnstile_site_key=_env_str("TURNSTILE_SITE_KEY"),
        turnstile_secret_key=_env_str("TURNSTILE_SECRET_KEY"),
        # One URL fragment / video ID per line; matching links are refused (copyright takedowns)
        blocklist_file=_env_str("BLOCKLIST_FILE"),
        cors_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    )
