import csv
import gzip
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import BRONZE_DIR, CAMERA_SNAPSHOT_URL, CAMERAS_CSV
from src.db import get_conn, last_sha256
from src.http_utils import get, make_session

logger = logging.getLogger(__name__)


def load_cameras() -> list[dict]:
    if not CAMERAS_CSV.exists():
        logger.warning("cameras.csv not found at %s", CAMERAS_CSV)
        return []
    with open(CAMERAS_CSV, newline="") as f:
        return list(csv.DictReader(f))


def _image_path(camera_id: str, ts: datetime) -> Path:
    day = ts.strftime("%Y-%m-%d")
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    dest = BRONZE_DIR / "images" / camera_id / day
    dest.mkdir(parents=True, exist_ok=True)
    return dest / f"{stamp}.png"


def ingest_cameras():
    cameras = load_cameras()
    if not cameras:
        logger.warning("No cameras to ingest.")
        return

    session = make_session()
    fetched_at = datetime.now(timezone.utc)
    rows = []

    with get_conn() as conn:
        for cam in cameras:
            camera_id = cam["camera_id"]
            url = CAMERA_SNAPSHOT_URL.format(camera_id=camera_id)
            snapshot_id = str(uuid.uuid4())
            row = {
                "snapshot_id": snapshot_id,
                "camera_id": camera_id,
                "fetched_at": fetched_at.isoformat(),
                "http_status": None,
                "content_type": None,
                "bytes": None,
                "sha256": None,
                "is_duplicate": 0,
                "image_path": None,
                "error": None,
            }

            try:
                resp = get(url, session=session)
                row["http_status"] = resp.status_code
                row["content_type"] = resp.headers.get("Content-Type", "")

                if resp.status_code != 200:
                    row["error"] = f"HTTP {resp.status_code}"
                    rows.append(row)
                    continue

                data = resp.content
                row["bytes"] = len(data)
                digest = hashlib.sha256(data).hexdigest()
                row["sha256"] = digest

                prev = last_sha256(conn, camera_id)
                if prev == digest:
                    row["is_duplicate"] = 1
                    logger.debug("%s duplicate image, skipping save", camera_id)
                else:
                    path = _image_path(camera_id, fetched_at)
                    path.write_bytes(data)
                    row["image_path"] = str(path)
                    logger.info("%s saved %d bytes -> %s", camera_id, len(data), path)

            except Exception as exc:
                row["error"] = str(exc)
                logger.error("%s error: %s", camera_id, exc)

            rows.append(row)

        conn.executemany(
            """
            INSERT OR IGNORE INTO bronze_camera_snapshots
            (snapshot_id, camera_id, fetched_at, http_status, content_type,
             bytes, sha256, is_duplicate, image_path, error)
            VALUES
            (:snapshot_id, :camera_id, :fetched_at, :http_status, :content_type,
             :bytes, :sha256, :is_duplicate, :image_path, :error)
            """,
            rows,
        )

    logger.info("Camera ingest complete: %d cameras processed", len(rows))
