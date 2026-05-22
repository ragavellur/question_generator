import sqlite3
import os
import threading
from datetime import datetime

from app.config import CHROMA_DB_PATH

DB_PATH = os.path.join(CHROMA_DB_PATH, "processing.db")
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db():
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processing_queue (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id      TEXT NOT NULL UNIQUE,
            filename    TEXT NOT NULL,
            filepath    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'queued',
            progress    INTEGER DEFAULT 0,
            message     TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            started_at  TEXT,
            completed_at TEXT
        )
    """)
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
    conn.commit()


def set_processing_status(doc_id: str, status: str, progress: int, message: str):
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE processing_queue SET status=?, progress=?, message=? WHERE doc_id=?",
        (status, progress, message, doc_id),
    )
    if status in ("extracting", "profiling", "queued"):
        conn.execute(
            "UPDATE processing_queue SET started_at=COALESCE(started_at,?) WHERE doc_id=?",
            (now, doc_id),
        )
    if status in ("done", "error"):
        conn.execute(
            "UPDATE processing_queue SET completed_at=? WHERE doc_id=? AND completed_at IS NULL",
            (now, doc_id),
        )
    conn.commit()


def get_processing_status(doc_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT doc_id, status, progress, message FROM processing_queue WHERE doc_id=?",
        (doc_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "document_id": row["doc_id"],
        "status": row["status"],
        "progress": row["progress"],
        "message": row["message"],
    }


def enqueue(doc_id: str, filename: str, filepath: str):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO processing_queue (doc_id, filename, filepath, status) VALUES (?,?,?,'queued')",
        (doc_id, filename, filepath),
    )
    conn.commit()


def dequeue_next() -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM processing_queue WHERE status='queued' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE processing_queue SET status='extracting', started_at=? WHERE id=?",
        (now, row["id"]),
    )
    conn.commit()
    return dict(row)


def get_active() -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM processing_queue WHERE status NOT IN ('queued','done','error') ORDER BY id ASC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def is_processing() -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM processing_queue WHERE status NOT IN ('done','error') LIMIT 1"
    ).fetchone()
    return row is not None


def queue_length() -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM processing_queue WHERE status='queued'"
    ).fetchone()
    return row["cnt"] if row else 0


def get_queue() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM processing_queue ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return [dict(r) for r in rows]


def get_queue_position(doc_id: str) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT created_at FROM processing_queue WHERE doc_id=?",
        (doc_id,),
    ).fetchone()
    if row is None:
        return 0
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM processing_queue WHERE status='queued' AND created_at < ?",
        (row["created_at"],),
    ).fetchone()
    active = conn.execute(
        "SELECT 1 FROM processing_queue WHERE status NOT IN ('queued','done','error') LIMIT 1"
    ).fetchone()
    pos = count["cnt"] if count else 0
    if active:
        pos += 1
    return pos


def mark_completed(doc_id: str):
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    conn.execute(
        "UPDATE processing_queue SET status='done', progress=100, completed_at=? WHERE doc_id=?",
        (now, doc_id),
    )
    conn.commit()


def mark_error(doc_id: str, error: str):
    now = datetime.utcnow().isoformat()
    conn = _get_conn()
    conn.execute(
        "UPDATE processing_queue SET status='error', message=?, completed_at=? WHERE doc_id=?",
        (error, now, doc_id),
    )
    conn.commit()
