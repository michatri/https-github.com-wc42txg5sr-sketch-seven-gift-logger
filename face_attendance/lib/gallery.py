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
PROFILE_KEYS = ("academic_year", "term", "grade", "room")


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


def normalize_profile(
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
) -> dict[str, str]:
    raw = {
        "academic_year": academic_year,
        "term": term,
        "grade": grade,
        "room": room,
    }
    out: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        text = str(value).strip()
        if len(text) > 32:
            raise EnrollmentError(f"{key} ยาวเกินไป")
        out[key] = text
    return out


def _read_meta(person_dir: Path) -> dict:
    meta: dict = {"person_id": person_dir.name, "display_name": person_dir.name}
    for key in PROFILE_KEYS:
        meta[key] = ""
    meta_path = person_dir / "meta.json"
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta.update(loaded)
        except json.JSONDecodeError:
            pass
    for key in PROFILE_KEYS:
        meta[key] = str(meta.get(key) or "")
    return meta


def _write_meta(person_dir: Path, meta: dict) -> dict:
    clean = dict(meta)
    clean.pop("has_preview", None)
    clean.pop("preview_url", None)
    (person_dir / "meta.json").write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    clean["has_preview"] = (person_dir / "preview.jpg").exists()
    clean["preview_url"] = f"/api/people/{person_dir.name}/preview"
    return clean


def enroll_from_image(
    pipeline: FacePipeline,
    image_path: Path,
    person_id: str,
    display_name: str | None = None,
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
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
    existing = _read_meta(person_dir) if (person_dir / "meta.json").exists() else {}
    np.save(person_dir / "embedding.npy", emb)

    x, y, w, h = hit.box
    crop = img[max(0, y) : y + h, max(0, x) : x + w]
    cv2.imwrite(str(person_dir / "preview.jpg"), crop)

    suffix = image_path.suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"
    source_copy = person_dir / f"source{suffix}"
    shutil.copyfile(image_path, source_copy)

    profile = normalize_profile(
        academic_year=academic_year,
        term=term,
        grade=grade,
        room=room,
    )
    # ถ้าไม่ได้ส่งค่าใหม่ ให้คงค่าเดิมไว้
    for key in PROFILE_KEYS:
        if key not in profile:
            profile[key] = str(existing.get(key) or "")

    meta = {
        "person_id": person_id,
        "display_name": (display_name or existing.get("display_name") or person_id).strip()
        or person_id,
        "source_image": str(source_copy),
        "face_score": float(hit.score),
        "box": [int(v) for v in hit.box],
        "face_count_in_image": len(hits),
        **{k: profile.get(k, "") for k in PROFILE_KEYS},
    }
    return _write_meta(person_dir, meta)


def enroll_from_ndarray(
    pipeline: FacePipeline,
    image_bgr: np.ndarray,
    person_id: str,
    display_name: str | None = None,
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
) -> dict:
    ensure_data_dirs()
    person_id = validate_person_id(person_id)
    tmp = DATA / "enrolled" / f"{person_id}_upload.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(tmp), image_bgr):
        raise EnrollmentError("บันทึกรูปชั่วคราวไม่สำเร็จ")
    return enroll_from_image(
        pipeline,
        tmp,
        person_id,
        display_name=display_name,
        academic_year=academic_year,
        term=term,
        grade=grade,
        room=room,
    )


def list_people(
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    q: str | None = None,
) -> list[dict]:
    root = gallery_dir()
    people: list[dict] = []
    if not root.exists():
        return people

    year_f = (academic_year or "").strip()
    term_f = (term or "").strip()
    grade_f = (grade or "").strip()
    room_f = (room or "").strip()
    query = (q or "").strip().lower()

    for person_dir in sorted(root.iterdir()):
        if not person_dir.is_dir():
            continue
        if not (person_dir / "embedding.npy").exists():
            continue
        meta = _read_meta(person_dir)
        meta["has_preview"] = (person_dir / "preview.jpg").exists()
        meta["preview_url"] = f"/api/people/{person_dir.name}/preview"

        if year_f and str(meta.get("academic_year") or "") != year_f:
            continue
        if term_f and str(meta.get("term") or "") != term_f:
            continue
        if grade_f and str(meta.get("grade") or "") != grade_f:
            continue
        if room_f and str(meta.get("room") or "") != room_f:
            continue
        if query:
            blob = " ".join(
                [
                    str(meta.get("person_id") or ""),
                    str(meta.get("display_name") or ""),
                    str(meta.get("academic_year") or ""),
                    str(meta.get("term") or ""),
                    str(meta.get("grade") or ""),
                    str(meta.get("room") or ""),
                ]
            ).lower()
            if query not in blob:
                continue
        people.append(meta)
    return people


def profile_options() -> dict[str, list[str]]:
    options = {key: set() for key in PROFILE_KEYS}
    for person in list_people():
        for key in PROFILE_KEYS:
            value = str(person.get(key) or "").strip()
            if value:
                options[key].add(value)
    return {key: sorted(values) for key, values in options.items()}


def get_person(person_id: str) -> dict:
    person_id = validate_person_id(person_id)
    person_dir = gallery_dir() / person_id
    if not person_dir.exists() or not (person_dir / "embedding.npy").exists():
        raise EnrollmentError("ไม่พบรายการนี้ในระบบ")
    meta = _read_meta(person_dir)
    meta["has_preview"] = (person_dir / "preview.jpg").exists()
    meta["preview_url"] = f"/api/people/{person_id}/preview"
    return meta


def update_person(
    person_id: str,
    display_name: str | None = None,
    pipeline: FacePipeline | None = None,
    image_bgr: np.ndarray | None = None,
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
) -> dict:
    """แก้ไขชื่อ/ชั้นเรียน และ/หรือ อัปเดตรูปใบหน้า."""
    current = get_person(person_id)
    new_name = (
        display_name.strip()
        if display_name is not None and display_name.strip()
        else current.get("display_name") or person_id
    )
    profile_updates = normalize_profile(
        academic_year=academic_year,
        term=term,
        grade=grade,
        room=room,
    )

    if image_bgr is not None:
        if pipeline is None:
            raise EnrollmentError("ไม่สามารถอัปเดตรูปได้")
        return enroll_from_ndarray(
            pipeline,
            image_bgr,
            person_id,
            display_name=new_name,
            academic_year=profile_updates.get("academic_year", current.get("academic_year")),
            term=profile_updates.get("term", current.get("term")),
            grade=profile_updates.get("grade", current.get("grade")),
            room=profile_updates.get("room", current.get("room")),
        )

    person_dir = gallery_dir() / person_id
    meta = dict(current)
    meta["person_id"] = person_id
    meta["display_name"] = new_name
    for key in PROFILE_KEYS:
        if key in profile_updates:
            meta[key] = profile_updates[key]
        else:
            meta[key] = str(current.get(key) or "")
    return _write_meta(person_dir, meta)


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
