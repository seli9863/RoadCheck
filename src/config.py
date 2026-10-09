import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv("ENV", "dev")
COTRIP_API_KEY = os.getenv("COTRIP_API_KEY", "")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / ENV
BRONZE_DIR = DATA_DIR / "bronze"
DB_PATH = DATA_DIR / "pipeline.db"
LOG_PATH = DATA_DIR / "ingest.log"
CAMERAS_CSV = BASE_DIR / "config" / "cameras.csv"

COTRIP_BASE_URL = "https://data.cotrip.org/api/v1"
CAMERA_SNAPSHOT_URL = "https://cocam.carsprogram.org/Snapshots/{camera_id}.flv.png"

COTRIP_FEEDS = ["roadConditions", "weatherStations", "snowPlows"]

INGEST_INTERVAL_SECONDS = 15 * 60  # 15 minutes
HTTP_TIMEOUT = 30
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_FACTOR = 2
