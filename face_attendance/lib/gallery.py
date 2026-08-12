"""Enrollment gallery: one .npy embedding + preview jpg per person."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from .camera import DATA, FacePipeline, ensure_data_dirs


def gallery_dir() -> Path:
    ensure_data_dirs()
    return DATA / "gallery"


def enroll_from_image(pipeline: FacePipeline, image_path: Path, person_id: str) -> Path:
    ensure_data_dirs()
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"อ่านรูปไม่ได้: {image_path}")

    hits = pipeline.detect(img)
    if not hits:
        raise SystemExit(f"ไม่พบใบหน้าในรูป: {image_path}")
    # ใช้ใบหน้าที่คะแนนสูงสุด
    hit = max(hits, key=lambda h: h.score)
    emb = pipeline.embed(img, hit)

    person_dir = gallery_dir() / person_id
    person_dir.mkdir(parents=True, exist_ok=True)
    np.save(person_dir / "embedding.npy", emb)

    x, y, w, h = hit.box
    crop = img[max(0, y) : y + h, max(0, x) : x + w]
    cv2.imwrite(str(person_dir / "preview.jpg"), crop)

    meta = {
        "person_id": person_id,
        "source_image": str(image_path),
        "face_score": float(hit.score),
        "box": [int(v) for v in hit.box],
    }
    (person_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return person_dir


def load_gallery(pipeline: FacePipeline) -> dict[str, np.ndarray]:
    _ = pipeline  # kept for API symmetry / future preprocessing
    gallery: dict[str, np.ndarray] = {}
    root = gallery_dir()
    if not root.exists():
        return gallery
    for person_dir in sorted(root.iterdir()):
        emb_path = person_dir / "embedding.npy"
        if person_dir.is_dir() and emb_path.exists():
            gallery[person_dir.name] = np.load(emb_path)
    return gallery


def match_embedding(
    pipeline: FacePipeline,
    embedding: np.ndarray,
    gallery: dict[str, np.ndarray],
    threshold: float,
) -> tuple[str, float]:
    best_name = "unknown"
    best_score = -1.0
    for name, ref in gallery.items():
        score = pipeline.cosine(embedding, ref)
        if score > best_score:
            best_score = score
            best_name = name
    if best_score < threshold:
        return "unknown", best_score
    return best_name, best_score
