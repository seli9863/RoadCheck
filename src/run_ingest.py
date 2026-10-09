"""
Usage:
    python src/run_ingest.py --once   # single ingest cycle then exit
    python src/run_ingest.py          # loop every INGEST_INTERVAL_SECONDS
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running as `python src/run_ingest.py` from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import INGEST_INTERVAL_SECONDS, LOG_PATH, ENV
from src.db import init_db
from src.ingest_cameras import ingest_cameras
from src.ingest_cotrip import ingest_cotrip


def setup_logging():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_PATH),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_cycle():
    start = datetime.now(timezone.utc)
    logging.getLogger(__name__).info("--- ingest cycle start (ENV=%s) ---", ENV)
    try:
        ingest_cameras()
    except Exception as exc:
        logging.getLogger(__name__).error("Camera ingest failed: %s", exc)
    try:
        ingest_cotrip()
    except Exception as exc:
        logging.getLogger(__name__).error("COtrip ingest failed: %s", exc)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logging.getLogger(__name__).info("--- ingest cycle done in %.1fs ---", elapsed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    args = parser.parse_args()

    setup_logging()
    init_db()

    if args.once:
        run_cycle()
    else:
        logging.getLogger(__name__).info(
            "Starting scheduler — interval %ds", INGEST_INTERVAL_SECONDS
        )
        while True:
            run_cycle()
            time.sleep(INGEST_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
