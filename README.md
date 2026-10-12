# Colorado Road Conditions

Live road-condition classifier for Colorado mountain corridors using CDOT traffic cameras.
Pulls camera snapshots every 15 minutes, classifies road surface (dry / wet / snow_ice) with CLIP,
compares against official COtrip API reports, and displays everything on an interactive Streamlit map.

---

## What it does

- **Ingests** PNG/JPG snapshots from 39 CDOT cameras (I-70 mountain corridor, I-25, Vail, Floyd Hill)
- **Classifies** each snapshot with CLIP ViT-B/32 zero-shot (dry / wet / snow_ice)
- **Cross-checks** against official COtrip road-condition and weather-station feeds
- **Scores ice risk** (HIGH / MEDIUM / LOW) using surface/air temperature rules
- **Displays** a live Folium map with per-camera popups, confidence scores, and 24-hour history charts

---

## Architecture

```
CDOT cameras  ──►  src/ingest_cameras.py  ──►  bronze_camera_snapshots  (SQLite)
COtrip API    ──►  src/ingest_cotrip.py   ──►  bronze_api_raw            (gzip JSON)
                                                      │
                                         src/build_silver.py
                                                      │
                                          silver_snapshots   ◄── src/predict.py (CLIP)
                                          silver_road_conditions
                                          silver_weather_stations
                                                      │
                                          src/build_gold.py + src/ice_risk.py
                                                      │
                                          gold_current_conditions
                                          gold_condition_history
                                          gold_model_vs_official
                                                      │
                                          dashboard/app.py  (Streamlit)
```

All layers live in a single SQLite file (`data/{dev,prod}/pipeline.db`).
Switch environments by setting `ENV=prod` in `.env`.

---

## Quickstart

```bash
# 1. Clone and create virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env          # set COTRIP_API_KEY and ENV=dev

# 3. Start ingesting (runs every 15 min; Ctrl-C to stop)
python src/run_ingest.py

# 4. Run the pipeline (silver → predict → gold → ice risk)
python src/run_pipeline.py

# 5. Launch the dashboard
streamlit run dashboard/app.py --server.headless true --browser.gatherUsageStats false
```

After a few ingestion cycles (30–45 min) you'll have enough data to see meaningful trends.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ENV` | `dev` | `dev` uses `data/dev/`, `prod` uses `data/prod/` |
| `COTRIP_API_KEY` | — | COtrip API key from [manage-api.cotrip.org](https://manage-api.cotrip.org) |

Camera list: `config/cameras.csv` — 39 cameras with lat/lon and snapshot URLs.

---

## Data pipeline

### Bronze
Raw, immutable inputs. Camera images are deduped by SHA-256 so re-runs are safe.
COtrip API responses are gzipped and stored with a timestamp filename.

### Silver
Cleaned, joined rows. `silver_snapshots` links each image to its camera metadata and
the nearest official road-condition report within a 1-hour window.
A quality filter (`src/quality_checks.py`) marks night/blank/corrupt images as `is_usable=0`
so they are excluded from prediction.

### Gold
Dashboard-ready aggregates:
- `gold_current_conditions` — latest prediction + official condition per camera
- `gold_condition_history` — hourly dominant condition per camera (24h rolling)
- `gold_model_vs_official` — hourly agreement between CLIP and official report

---

## Model

**CLIP ViT-B/32 zero-shot** (`open-clip-torch`, OpenAI weights).

Three classes with prompt ensembles:

| Class | Example prompts |
|---|---|
| `dry` | "a photo of a dry road", "dry pavement on a highway" |
| `wet` | "a photo of a wet road", "wet pavement reflecting light" |
| `snow_ice` | "a photo of a snowy road", "road covered in snow and ice" |

Predictions use CLIP's learned temperature scale (`logit_scale ≈ 100`) before softmax,
which separates cosine similarities into crisp probabilities (median confidence ~60%).

A ResNet-18 was fine-tuned on the [UDOT public road surface dataset](https://udot.utah.gov)
(6,245 images, 90.8% val accuracy at epoch 8) but was not used for live predictions due to
domain shift — the Utah camera angles and lighting differ significantly from Colorado CDOT cameras.
The trained checkpoint is saved at `model/models/resnet18_v1.pt` for reference.

---

## Ice risk rules

| Level | Condition |
|---|---|
| **HIGH** | `wet` or `snow_ice` AND surface/air temp ≤ 0 °C |
| **MEDIUM** | `wet` AND 0 °C < temp ≤ 3 °C, or `snow_ice` with no temp data |
| **LOW** | everything else |

Temperature comes from COtrip weather stations when available; ice risk defaults to MEDIUM for
snow_ice predictions when no station data is present.

---

## Dataset stats (as of Oct 11, 2026)

| Layer | Count |
|---|---|
| Bronze camera snapshots | 3,807 |
| Silver usable snapshots | 3,669 |
| Gold history rows | 967 |
| Cameras covered | 39 |
| Date range | Oct 9 – Oct 11, 2026 |
| Model vs official agreement | 59.8% |

---

## Project layout

```
config/
  cameras.csv          camera list (39 cameras, lat/lon, snapshot URLs)
src/
  config.py            ENV switch, path constants
  db.py                SQLite connection helper
  http_utils.py        retry/backoff HTTP
  ingest_cameras.py    bronze: camera snapshot ingestion
  ingest_cotrip.py     bronze: COtrip API ingestion
  run_ingest.py        scheduler loop (--once for single run)
  build_silver.py      silver layer
  quality_checks.py    night/blank/corrupt image filter
  predict.py           CLIP zero-shot predictions on silver_snapshots
  build_gold.py        gold aggregates
  ice_risk.py          rule-based ice risk scoring
  run_pipeline.py      chains silver → predict → gold → ice_risk
labeling/
  clip_prelabel.py     CLIP pre-labeler (generates data/dev/labels.csv)
  label_tool.py        keyboard labeling tool (d/w/s keys)
model/
  train.py             ResNet-18 fine-tuning on UDOT dataset
  evaluate.py          evaluation vs CLIP baseline and official reports
  models/
    resnet18_v1.pt     best checkpoint (epoch 8, 90.8% val acc)
dashboard/
  app.py               Streamlit map dashboard
data/
  dev/                 dev environment (SQLite DB, bronze images, labels)
  prod/                prod environment
```

---

## Notes

- Run all Python commands with `.venv/bin/python3` — the system Python lacks torch/CLIP.
- Streamlit requires `--server.headless true --browser.gatherUsageStats false` on headless servers.
- `num_workers=0` in DataLoaders — WSL multiprocessing deadlocks otherwise.
- Floyd Hill cameras use `/Cellular/` URL paths and `.jpg` extension; ingest handles this automatically.
