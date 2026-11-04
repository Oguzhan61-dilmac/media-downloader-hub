"""
mdhub:// links: lets the website open the desktop app and start a download.

    mdhub://download?url=<encoded video url>&format=best|720p|480p|mp3

On Windows the app registers the scheme for the current user (no admin rights)
every time it starts, so moving the .exe keeps the link working.
"""
import os
import sys
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs

SCHEME = "mdhub"

# website format value -> desktop FORMAT_OPTIONS index (see ui/theme.py)
FORMAT_INDEX = {"best": 0, "1080p": 1, "720p": 2, "480p": 3, "mp3": 4}


def parse_link(arg: str) -> Optional[Dict[str, str]]:
    """Returns {"url": ..., "format": ...} for a valid mdhub:// link, otherwise None."""
    if not arg or not arg.lower().startswith(f"{SCHEME}:"):
        return None
    parsed = urlparse(arg)
    params = parse_qs(parsed.query)
    url = (params.get("url") or [""])[0].strip()
    target = urlparse(url)
    # only plain web links; never file://, javascript: etc.
    if target.scheme not in ("http", "https") or not target.netloc or len(url) > 2048:
        return None
    fmt = (params.get("format") or ["best"])[0]
    if fmt not in FORMAT_INDEX:
        fmt = "best"
    return {"url": url, "format": fmt}


def link_from_argv(argv=None) -> Optional[Dict[str, str]]:
    for arg in (argv if argv is not None else sys.argv)[1:]:
        link = parse_link(arg)
        if link:
            return link
    return None


def _launch_command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller .exe
        return f'"{sys.executable}" "%1"'
    python = sys.executable
    pythonw = os.path.join(os.path.dirname(python), "pythonw.exe")
    if os.path.exists(pythonw):
        python = pythonw
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    return f'"{python}" "{script}" "%1"'


def register_protocol() -> bool:
    """Registers mdhub:// for the current Windows user. No-op elsewhere."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        base = rf"Software\Classes\{SCHEME}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Media Downloader Hub")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _launch_command())
        return True
    except OSError:
        return False


def add_bundled_tools_to_path():
    """Inside the .exe, put the bundled deno.exe (YouTube JS challenges) on PATH."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle and os.path.isdir(bundle):
        os.environ["PATH"] = bundle + os.pathsep + os.environ.get("PATH", "")
