import sqlite3
import logging
from src.config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bronze_camera_snapshots (
                snapshot_id   TEXT PRIMARY KEY,
                camera_id     TEXT NOT NULL,
                fetched_at    TEXT NOT NULL,
                http_status   INTEGER,
                content_type  TEXT,
                bytes         INTEGER,
                sha256        TEXT,
                is_duplicate  INTEGER DEFAULT 0,
                image_path    TEXT,
                error         TEXT
            );

            CREATE TABLE IF NOT EXISTS bronze_api_raw (
                fetch_id      TEXT PRIMARY KEY,
                feed          TEXT NOT NULL,
                fetched_at    TEXT NOT NULL,
                http_status   INTEGER,
                feature_count INTEGER,
                file_path     TEXT,
                error         TEXT
            );
        """)
    logger.info("Database initialized at %s", DB_PATH)


def last_sha256(conn: sqlite3.Connection, camera_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT sha256 FROM bronze_camera_snapshots
        WHERE camera_id = ? AND sha256 IS NOT NULL
        ORDER BY fetched_at DESC LIMIT 1
        """,
        (camera_id,),
    ).fetchone()
    return row["sha256"] if row else None
