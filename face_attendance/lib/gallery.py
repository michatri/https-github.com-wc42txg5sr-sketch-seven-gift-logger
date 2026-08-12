"""Enrollment gallery: one .npy embedding + preview jpg per person."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import cv2
import numpy as np

from .camera import DATA, FacePipeline, ensure_data_dirs

PERSON_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class EnrollmentError(ValueError):
    """User-facing enrollment failure."""


def gallery_dir() -> Path:
    ensure_data_dirs()
    return DATA / "gallery"


def validate_person_id(person_id: str) -> str:
    person_id = (person_id or "").strip()
    if not PERSON_ID_RE.match(person_id):
        raise EnrollmentError(
            "รหัสไม่ถูกต้อง ใช้เฉพาะ a-z, 0-9, _ , - และยาวไม่เกิน 64 ตัว"
        )
    return person_id


def enroll_from_image(
    pipeline: FacePipeline,
    image_path: Path,
    person_id: str,
    display_name: str | None = None,
) -> dict:
    ensure_data_dirs()
    person_id = validate_person_id(person_id)
    img = cv2.imread(str(image_path))
    if img is None:
        raise EnrollmentError(f"อ่านรูปไม่ได้: {image_path}")

    hits = pipeline.detect(img)
    if not hits:
        raise EnrollmentError("ไม่พบใบหน้าในรูป — ใช้รูปตรงหน้า แสงพอ และใบหน้าชัด")

    hit = max(hits, key=lambda h: h.score)
    emb = pipeline.embed(img, hit)

    person_dir = gallery_dir() / person_id
    person_dir.mkdir(parents=True, exist_ok=True)
    np.save(person_dir / "embedding.npy", emb)

    x, y, w, h = hit.box
    crop = img[max(0, y) : y + h, max(0, x) : x + w]
    cv2.imwrite(str(person_dir / "preview.jpg"), crop)

    # เก็บต้นฉบับด้วย
    suffix = image_path.suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"
    source_copy = person_dir / f"source{suffix}"
    shutil.copyfile(image_path, source_copy)

    meta = {
        "person_id": person_id,
        "display_name": (display_name or person_id).strip() or person_id,
        "source_image": str(source_copy),
        "face_score": float(hit.score),
        "box": [int(v) for v in hit.box],
        "face_count_in_image": len(hits),
    }
    (person_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def enroll_from_ndarray(
    pipeline: FacePipeline,
    image_bgr: np.ndarray,
    person_id: str,
    display_name: str | None = None,
) -> dict:
    ensure_data_dirs()
    person_id = validate_person_id(person_id)
    tmp = DATA / "enrolled" / f"{person_id}_upload.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(tmp), image_bgr):
        raise EnrollmentError("บันทึกรูปชั่วคราวไม่สำเร็จ")
    return enroll_from_image(pipeline, tmp, person_id, display_name=display_name)


def list_people() -> list[dict]:
    root = gallery_dir()
    people: list[dict] = []
    if not root.exists():
        return people
    for person_dir in sorted(root.iterdir()):
        if not person_dir.is_dir():
            continue
        emb = person_dir / "embedding.npy"
        preview = person_dir / "preview.jpg"
        meta_path = person_dir / "meta.json"
        if not emb.exists():
            continue
        meta: dict = {"person_id": person_dir.name, "display_name": person_dir.name}
        if meta_path.exists():
            try:
                meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        meta["has_preview"] = preview.exists()
        meta["preview_url"] = f"/api/people/{person_dir.name}/preview"
        people.append(meta)
    return people


def delete_person(person_id: str) -> None:
    person_id = validate_person_id(person_id)
    person_dir = gallery_dir() / person_id
    if not person_dir.exists():
        raise EnrollmentError("ไม่พบรายการนี้ในระบบ")
    shutil.rmtree(person_dir)


def load_gallery(pipeline: FacePipeline) -> dict[str, np.ndarray]:
    _ = pipeline
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
