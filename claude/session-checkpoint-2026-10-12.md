# Session Checkpoint — October 12, 2026

**Deadline:** Tuesday October 13, 2026 at noon MT  
**Project:** Colorado road condition classifier from CDOT traffic cameras

---

## What Was Done Today

1. **Swapped live predictor from ResNet-18 → CLIP zero-shot** (`src/predict.py` rewritten)
   - ResNet had 90.8% val accuracy on UDOT (Utah) but only ~20% on Colorado cameras (domain shift)
   - CLIP ViT-B/32 zero-shot generalizes across camera angles and lighting

2. **Fixed CLIP temperature scaling bug**
   - Without `logit_scale` (100), softmax on raw cosine sims gave ~33% confidence on all images
   - Applied `model.logit_scale.exp()` before softmax → confidence now 40–99%, median 60%

3. **Re-predicted all 3,408 snapshots** with corrected CLIP

4. **Rebuilt gold layer + ice risk**
   - 39 cameras, 13 MEDIUM / 26 LOW ice risk
   - Model vs official agreement: 59.8%

5. **Verified dashboard is live** at http://localhost:8501 (HTTP 200, health check ok)

6. **Wrote README.md**

---

## Current State

- `ENV=dev` still in `.env` (not switched to prod — waiting on API key regeneration)
- COTRIP_API_KEY needs to be regenerated at manage-api.cotrip.org (was exposed in terminal)
- ResNet checkpoint preserved at `model/models/resnet18_v1.pt` (not used for live predictions)
- `clip_prelabel.py` still uses the old un-scaled CLIP — does NOT affect live system (labeling is done)

---

## Remaining Work

### Still needed before noon Tuesday

1. **Regenerate COtrip API key** at manage-api.cotrip.org (manual browser step)
2. **Switch to prod**: update `.env` with new key + `ENV=prod`
3. **Re-run ingest**: `.venv/bin/python3 src/run_ingest.py` (or `--once` for a single cycle)
4. **Re-run pipeline**: `.venv/bin/python3 src/run_pipeline.py`
5. **Final commit** (README + all modified files)
6. README is done — may want to add architecture diagram or confusion matrix screenshot

---

## Key Commands

```bash
# Switch to prod and re-run after key regeneration
.venv/bin/python3 src/run_ingest.py --once
.venv/bin/python3 src/run_pipeline.py
.venv/bin/streamlit run dashboard/app.py --server.headless true --browser.gatherUsageStats false

# Commit everything
git add -A && git commit -m "CLIP zero-shot predictor, temperature fix, README"
```
