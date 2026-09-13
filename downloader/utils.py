import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse

CONFIG_FILE_PATH = Path.home() / ".media_downloader_config.json"

def get_default_download_dir() -> Path:
    """Returns the default download directory (~/Downloads/Rutube_Downloads). Creates it if it doesn't exist."""
    user_home = Path.home()
    download_dir = user_home / "Downloads" / "Rutube_Downloads"
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        fallback_dir = user_home / "Downloads"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir
    return download_dir

def load_saved_download_dir() -> str:
    """Loads saved download directory from config file, or defaults to ~/Downloads/Rutube_Downloads."""
    default_dir = str(get_default_download_dir())
    try:
        if CONFIG_FILE_PATH.exists():
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_path = data.get("download_dir", "")
                if saved_path and os.path.exists(saved_path):
                    return saved_path
    except Exception:
        pass
    return default_dir

def save_download_dir(path_str: str) -> None:
    """Saves chosen download directory to config file for persistence across application restarts."""
    if not path_str or not os.path.exists(path_str):
        return
    try:
        config_data = {}
        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception:
                config_data = {}
        config_data["download_dir"] = path_str
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def is_valid_url(url: str) -> bool:
    """Validates if the provided string is a valid web URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    parsed = urlparse(url)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc)

def format_bytes(bytes_count: float) -> str:
    """Converts a byte count into a human readable string (e.g. 15.4 MB)."""
    if bytes_count is None or bytes_count < 0:
        return "Bilinmiyor"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    val = float(bytes_count)
    
    while val >= 1024.0 and unit_index < len(units) - 1:
        val /= 1024.0
        unit_index += 1
        
    return f"{val:.1f} {units[unit_index]}"

def format_speed(speed_bytes: float) -> str:
    """Converts bytes per second speed into a human readable string (e.g. 4.2 MB/s)."""
    if speed_bytes is None or speed_bytes <= 0:
        return "0 B/s"
    formatted = format_bytes(speed_bytes)
    return f"{formatted}/s"

def format_seconds(seconds: float) -> str:
    """Converts seconds into formatted time string (e.g. 02:45 or 01:15:30)."""
    if seconds is None or seconds < 0:
        return "--:--"
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def clean_filename(filename: str) -> str:
    """Sanitizes filename for cross-platform filesystem safety."""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()
