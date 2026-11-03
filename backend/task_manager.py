import os
import time
import uuid
import threading
from typing import Dict, Any, Optional, List, Tuple

# Fields that are safe to send to the browser (no server paths, no URLs of other users)
PUBLIC_FIELDS = (
    "task_id", "status", "progress_pct", "step_name", "detail", "error",
    "filename", "filesize", "expires_at", "created_at", "queue_position",
)

ACTIVE_STATUSES = ("queued", "processing")
FINISHED_STATUSES = ("completed", "failed", "cancelled")


class TaskManager:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_task(self, url: str, auto_subtitle: bool, target_lang: str, client_ip: Optional[str] = None) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "url": url,
                "auto_subtitle": auto_subtitle,
                "target_lang": target_lang,
                "client_ip": client_ip,
                "status": "queued",
                "progress_pct": 0.0,
                "step_name": "Sırada bekliyor",
                "detail": "İşlem kuyruğa alındı...",
                "error": None,
                "file_path": None,
                "filename": None,
                "filesize": None,
                "dir": None,
                "created_at": time.time(),
                "finished_at": None,
                "expires_at": None,
                "task_runner": None,
                "cancel_requested": False,
            }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            # A finished task never goes back to "processing" (late progress callbacks)
            if task["status"] in FINISHED_STATUSES and kwargs.get("status") == "processing":
                return
            task.update(kwargs)

    def _queue_position(self, task: Dict[str, Any]) -> Optional[int]:
        if task["status"] != "queued":
            return None
        earlier = [t for t in self._tasks.values() if t["status"] == "queued" and t["created_at"] <= task["created_at"]]
        return len(earlier)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Public view of a task, safe to return from the API."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            view = {k: task.get(k) for k in PUBLIC_FIELDS if k != "queue_position"}
            view["queue_position"] = self._queue_position(task)
            return view

    def get_internal(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Shallow copy including server-side fields (runner, paths)."""
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def get_task_file_path(self, task_id: str) -> Optional[str]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.get("status") == "completed":
                return task.get("file_path")
            return None

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t["status"] in ACTIVE_STATUSES)

    def expired(self, ttl_sec: float) -> List[Tuple[str, Optional[str]]]:
        """Finished tasks older than ttl_sec: [(task_id, output_dir)]."""
        now = time.time()
        with self._lock:
            return [
                (tid, t.get("dir"))
                for tid, t in self._tasks.items()
                if t["status"] in FINISHED_STATUSES and t.get("finished_at") and now - t["finished_at"] > ttl_sec
            ]

    def known_dirs(self) -> List[str]:
        with self._lock:
            return [os.path.abspath(t["dir"]) for t in self._tasks.values() if t.get("dir")]

    def remove(self, task_id: str):
        with self._lock:
            self._tasks.pop(task_id, None)


task_manager = TaskManager()
