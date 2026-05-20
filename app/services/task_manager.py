import asyncio
import uuid
import time
from typing import Optional


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, dict] = {}

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "status": "queued",
            "message": "Task queued",
            "questions": [],
            "total_so_far": 0,
            "error": None,
            "created_at": time.time(),
        }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        if task_id in self._tasks:
            self._tasks[task_id].update(kwargs)

    def get_task(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        if task:
            return {
                "status": task["status"],
                "message": task.get("message"),
                "questions": task.get("questions", []),
                "total_so_far": task.get("total_so_far", 0),
                "error": task.get("error"),
            }
        return None

    def cleanup_old(self, max_age: int = 1800):
        now = time.time()
        to_delete = [
            tid
            for tid, t in self._tasks.items()
            if now - t.get("created_at", 0) > max_age
        ]
        for tid in to_delete:
            del self._tasks[tid]


task_manager = TaskManager()
