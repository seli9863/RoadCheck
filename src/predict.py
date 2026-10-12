"""
Run CLIP zero-shot predictions on new snapshots and write to silver_snapshots.
Run: python src/predict.py
     python src/predict.py --all   (re-predict everything, not just new snapshots)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from PIL import Image

from src.db import get_conn

CLASSES = ["dry", "wet", "snow_ice"]
MODEL_VERSION = "clip_vit_b32"

# Ensemble of prompts per class — averaged into a single class embedding
PROMPTS = {
    "dry": [
        "a photo of a dry road",
        "dry pavement on a highway",
        "clear dry road surface with no moisture",
    ],
    "wet": [
        "a photo of a wet road",
        "wet pavement reflecting light",
        "road surface covered in rain or moisture",
    ],
    "snow_ice": [
        "a photo of a snowy road",
        "road covered in snow and ice",
        "icy or snowy highway in winter",
    ],
}


def load_clip():
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
    model.eval()
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    logit_scale = model.logit_scale.exp().item()
    return model, preprocess, tokenizer, logit_scale


def build_class_embeddings(model, tokenizer) -> dict:
    class_embeddings = {}
    with torch.no_grad():
        for cls, prompts in PROMPTS.items():
            tokens = tokenizer(prompts)
            emb = model.encode_text(tokens)
            emb = emb / emb.norm(dim=-1, keepdim=True)
            mean_emb = emb.mean(dim=0)
            class_embeddings[cls] = mean_emb / mean_emb.norm()
    return class_embeddings


def predict_image(image_path: str, model, preprocess, class_embeddings, logit_scale: float) -> tuple[str, float]:
    img = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        img_emb = model.encode_image(img)
        img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True)
    text_stack = torch.stack([class_embeddings[c] for c in CLASSES])
    probs = (logit_scale * img_emb @ text_stack.T).squeeze(0).softmax(dim=0)
    best = probs.argmax().item()
    return CLASSES[best], probs[best].item()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Re-predict already-predicted snapshots")
    args = parser.parse_args()

    print("Loading CLIP ViT-B/32...")
    model, preprocess, tokenizer, logit_scale = load_clip()
    class_embeddings = build_class_embeddings(model, tokenizer)
    print(f"Model ready  |  version: {MODEL_VERSION}  |  logit_scale: {logit_scale:.1f}")

    with get_conn() as conn:
        if args.all:
            rows = conn.execute("""
                SELECT ss.snapshot_id, b.image_path
                FROM silver_snapshots ss
                JOIN bronze_camera_snapshots b USING (snapshot_id)
                WHERE ss.is_usable = 1 AND b.image_path IS NOT NULL
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT ss.snapshot_id, b.image_path
                FROM silver_snapshots ss
                JOIN bronze_camera_snapshots b USING (snapshot_id)
                WHERE ss.is_usable = 1
                  AND ss.predicted_condition IS NULL
                  AND b.image_path IS NOT NULL
            """).fetchall()

        print(f"Predicting {len(rows)} snapshots...")
        updated = 0
        for row in rows:
            try:
                cls, conf = predict_image(row["image_path"], model, preprocess, class_embeddings, logit_scale)
            except Exception as e:
                print(f"  [skip] {row['snapshot_id']}: {e}")
                continue
            conn.execute("""
                UPDATE silver_snapshots
                SET predicted_condition = ?, confidence = ?, model_version = ?
                WHERE snapshot_id = ?
            """, (cls, conf, MODEL_VERSION, row["snapshot_id"]))
            updated += 1

        print(f"Updated {updated} rows in silver_snapshots.")

        counts = conn.execute("""
            SELECT predicted_condition, COUNT(*) as n FROM silver_snapshots
            WHERE predicted_condition IS NOT NULL
            GROUP BY predicted_condition
        """).fetchall()
        print("\nPrediction breakdown:")
        for r in counts:
            print(f"  {r[0]}: {r[1]}")


if __name__ == "__main__":
    main()
