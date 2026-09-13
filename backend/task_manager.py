import uuid
import threading
from typing import Dict, Any, Optional

class TaskManager:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_task(self, url: str, auto_subtitle: bool, target_lang: str) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "url": url,
                "auto_subtitle": auto_subtitle,
                "target_lang": target_lang,
                "status": "pending",
                "progress_pct": 0.0,
                "step_name": "İşlem Bekleniyor",
                "detail": "Kuyruğa alındı...",
                "error": None,
                "file_path": None,
                "task_runner": None
            }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                # Return clean shallow copy without non-serializable objects
                clean_task = {k: v for k, v in task.items() if k != "task_runner"}
                return clean_task
            return None

    def get_task_file_path(self, task_id: str) -> Optional[str]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.get("status") == "completed":
                return task.get("file_path")
            return None

task_manager = TaskManager()
