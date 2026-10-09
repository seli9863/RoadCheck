import gzip
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import BRONZE_DIR, COTRIP_API_KEY, COTRIP_BASE_URL, COTRIP_FEEDS
from src.db import get_conn
from src.http_utils import get, make_session

logger = logging.getLogger(__name__)


def _api_path(feed: str, ts: datetime) -> Path:
    day = ts.strftime("%Y-%m-%d")
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    dest = BRONZE_DIR / "api" / feed / day
    dest.mkdir(parents=True, exist_ok=True)
    return dest / f"{stamp}.json.gz"


def ingest_cotrip():
    if not COTRIP_API_KEY:
        logger.error("COTRIP_API_KEY not set — skipping API ingest")
        return

    session = make_session()
    fetched_at = datetime.now(timezone.utc)
    rows = []

    with get_conn() as conn:
        for feed in COTRIP_FEEDS:
            url = f"{COTRIP_BASE_URL}/{feed}?apiKey={COTRIP_API_KEY}"
            fetch_id = str(uuid.uuid4())
            row = {
                "fetch_id": fetch_id,
                "feed": feed,
                "fetched_at": fetched_at.isoformat(),
                "http_status": None,
                "feature_count": None,
                "file_path": None,
                "error": None,
            }

            try:
                resp = get(url, session=session)
                row["http_status"] = resp.status_code

                if resp.status_code != 200:
                    row["error"] = f"HTTP {resp.status_code}"
                    rows.append(row)
                    continue

                body = resp.json()
                features = body.get("features", [])
                row["feature_count"] = len(features)

                if len(features) == 0:
                    logger.warning("%s returned 0 features", feed)

                path = _api_path(feed, fetched_at)
                with gzip.open(path, "wt", encoding="utf-8") as f:
                    json.dump(body, f)
                row["file_path"] = str(path)
                logger.info("%s: %d features -> %s", feed, len(features), path)

            except Exception as exc:
                row["error"] = str(exc)
                logger.error("%s error: %s", feed, exc)

            rows.append(row)

        conn.executemany(
            """
            INSERT OR IGNORE INTO bronze_api_raw
            (fetch_id, feed, fetched_at, http_status, feature_count, file_path, error)
            VALUES
            (:fetch_id, :feed, :fetched_at, :http_status, :feature_count, :file_path, :error)
            """,
            rows,
        )

    logger.info("COtrip ingest complete: %d feeds processed", len(rows))
