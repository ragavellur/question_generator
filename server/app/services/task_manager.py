import json
import uuid
import time
import logging
from typing import Optional

from app.services.db import _get_conn

logger = logging.getLogger(__name__)


def _log_task_event(task_id: str, event_type: str, details: str = ""):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO generation_log (task_id, event_type, details) VALUES (?, ?, ?)",
            (task_id, event_type, details),
        )
        conn.commit()
    except Exception:
        pass


class TaskManager:
    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._cleanup_stale_tasks()

    def _cleanup_stale_tasks(self):
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id               TEXT PRIMARY KEY,
                status           TEXT NOT NULL DEFAULT 'queued',
                message          TEXT DEFAULT '',
                questions        TEXT DEFAULT '[]',
                total_so_far     INTEGER DEFAULT 0,
                error            TEXT,
                selected_types   TEXT DEFAULT '[]',
                completed_types  TEXT DEFAULT '[]',
                current_type     TEXT,
                total_target     INTEGER DEFAULT 0,
                created_at       REAL NOT NULL,
                updated_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generation_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id    TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details    TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN config TEXT DEFAULT '{}'")
        except Exception:
            pass
        conn.commit()
        stale = conn.execute(
            "SELECT id FROM tasks WHERE status IN ('queued','running')"
        ).fetchall()
        for row in stale:
            tid = row["id"]
            conn.execute(
                "UPDATE tasks SET status='error', error=?, updated_at=datetime('now') WHERE id=?",
                ("Server was restarted — task aborted.", tid),
            )
            logger.warning("Marked stale task %s as error (server restart)", tid)
            _log_task_event(tid, "stale_cleanup", "Server was restarted — task aborted")
        conn.commit()

    def _load(self, task_id: str) -> Optional[dict]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        for key in ("questions", "selected_types", "completed_types", "config"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key] = {} if key == "config" else ([] if key != "error" else None)
        return d

    def _save(self, task_id: str):
        task = self._cache.get(task_id)
        if not task:
            return
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (id, status, message, questions, total_so_far, error,
                    selected_types, completed_types, current_type, total_target,
                    config, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (
                    task_id,
                    task.get("status", "queued"),
                    task.get("message", ""),
                    json.dumps(task.get("questions", [])),
                    task.get("total_so_far", 0),
                    task.get("error"),
                    json.dumps(task.get("selected_types", [])),
                    json.dumps(task.get("completed_types", [])),
                    task.get("current_type"),
                    task.get("total_target", 0),
                    json.dumps(task.get("config", {})),
                    task.get("created_at", time.time()),
                ),
            )
            conn.commit()
        except Exception as e:
            logger.error("Failed to save task %s: %s", task_id, e)

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        now = time.time()
        task = {
            "status": "queued",
            "message": "Task queued",
            "questions": [],
            "total_so_far": 0,
            "error": None,
            "selected_types": [],
            "completed_types": [],
            "current_type": None,
            "total_target": 0,
            "config": {},
            "created_at": now,
        }
        self._cache[task_id] = task
        self._save(task_id)
        _log_task_event(task_id, "created", "Task queued")
        return task_id

    def update_task(self, task_id: str, **kwargs):
        if task_id not in self._cache:
            loaded = self._load(task_id)
            if loaded:
                self._cache[task_id] = loaded
            else:
                logger.warning("update_task: task %s not found", task_id)
                return
        self._cache[task_id].update(kwargs)
        self._save(task_id)

    def get_task(self, task_id: str) -> Optional[dict]:
        cached = self._cache.get(task_id)
        if cached:
            return cached
        loaded = self._load(task_id)
        if loaded:
            self._cache[task_id] = loaded
        return loaded

    def list_tasks(self, status: str | None = None) -> list[dict]:
        conn = _get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        result = []
        for row in rows:
            d = self._row_to_dict(row)
            d["task_id"] = d.pop("id", "")
            result.append(d)
        return result

    def has_active_task(self) -> bool:
        conn = _get_conn()
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE status IN ('queued','running') LIMIT 1"
        ).fetchone()
        return row is not None

    def delete_task(self, task_id: str) -> bool:
        conn = _get_conn()
        deleted = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,)).rowcount
        conn.commit()
        self._cache.pop(task_id, None)
        if deleted:
            logger.info("Deleted task %s", task_id)
        return deleted > 0

    def last_done_task_id(self) -> str | None:
        conn = _get_conn()
        row = conn.execute(
            "SELECT id FROM tasks WHERE status='done' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None

    def cleanup_old(self, max_age: int = 7200) -> int:
        cutoff = time.time() - max_age
        conn = _get_conn()
        deleted = conn.execute(
            "DELETE FROM tasks WHERE status IN ('done','error') AND created_at < ?", (cutoff,)
        ).rowcount
        conn.execute(
            "DELETE FROM generation_log WHERE created_at < datetime('now', ?)",
            (f"-{max_age} seconds",),
        )
        conn.commit()
        if deleted:
            logger.info("Cleaned up %d old finished tasks", deleted)
        stale_ids = [tid for tid, t in list(self._cache.items())
                     if t.get("created_at", 0) < cutoff and t.get("status") in ("done", "error")]
        for tid in stale_ids:
            del self._cache[tid]
        return deleted


task_manager = TaskManager()
