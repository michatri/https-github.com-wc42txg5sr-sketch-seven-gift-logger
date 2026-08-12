"""School attendance logging: check-in / check-out."""

from __future__ import annotations

import csv
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from .camera import DATA, FacePipeline, draw_hits, ensure_data_dirs, load_camera_env
from .gallery import get_person, load_gallery, match_embedding

Direction = Literal["in", "out"]

_lock = threading.Lock()
_last_marked: dict[tuple[str, Direction], float] = {}

TZ_NAME = os.getenv("ATTENDANCE_TZ", "Asia/Bangkok")


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(TZ_NAME)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def attendance_dir() -> Path:
    ensure_data_dirs()
    path = DATA / "attendance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _day_paths(now: datetime | None = None) -> tuple[Path, Path]:
    now = now or datetime.now(_tz())
    day = now.strftime("%Y%m%d")
    base = attendance_dir()
    return base / f"attendance_{day}.csv", base / f"attendance_{day}.jsonl"


def _threshold() -> float:
    load_camera_env()
    return float(os.getenv("MATCH_THRESHOLD", "0.42"))


def _cooldown() -> int:
    load_camera_env()
    return int(os.getenv("COOLDOWN_SECONDS", "120"))


def _person_snapshot(person_id: str) -> dict:
    try:
        person = get_person(person_id)
        return {
            "display_name": str(person.get("display_name") or person_id),
            "academic_year": str(person.get("academic_year") or ""),
            "term": str(person.get("term") or ""),
            "grade": str(person.get("grade") or ""),
            "room": str(person.get("room") or ""),
        }
    except Exception:  # noqa: BLE001
        return {
            "display_name": person_id,
            "academic_year": "",
            "term": "",
            "grade": "",
            "room": "",
        }


def _append_record(record: dict) -> None:
    csv_path, jsonl_path = _day_paths()
    fieldnames = [
        "timestamp_local",
        "timestamp_utc",
        "direction",
        "person_id",
        "display_name",
        "academic_year",
        "term",
        "grade",
        "room",
        "similarity",
        "snapshot",
    ]
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow({k: record.get(k, "") for k in fieldnames})
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _iter_jsonl_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(attendance_dir().glob("attendance_*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    return rows


def list_records(
    direction: Direction | None = None,
    limit: int = 50,
    person_id: str | None = None,
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    today_only: bool = True,
) -> list[dict]:
    if today_only:
        _, jsonl_path = _day_paths()
        source_rows: list[dict] = []
        if jsonl_path.exists():
            with jsonl_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        source_rows.append(row)
    else:
        source_rows = _iter_jsonl_rows()

    year_f = (academic_year or "").strip()
    term_f = (term or "").strip()
    grade_f = (grade or "").strip()
    room_f = (room or "").strip()
    person_f = (person_id or "").strip()

    rows: list[dict] = []
    for row in source_rows:
        if direction and row.get("direction") != direction:
            continue
        if person_f and row.get("person_id") != person_f:
            continue
        if year_f and str(row.get("academic_year") or "") != year_f:
            continue
        if term_f and str(row.get("term") or "") != term_f:
            continue
        if grade_f and str(row.get("grade") or "") != grade_f:
            continue
        if room_f and str(row.get("room") or "") != room_f:
            continue
        rows.append(row)
    rows.reverse()
    return rows[: max(1, min(limit, 1000))]


def list_student_history(person_id: str, limit: int = 200) -> list[dict]:
    return list_records(person_id=person_id, limit=limit, today_only=False)


def process_frame(
    pipeline: FacePipeline,
    frame: np.ndarray,
    direction: Direction,
) -> dict:
    """Detect/match faces in frame and mark attendance for known people."""
    if direction not in {"in", "out"}:
        raise ValueError("direction ต้องเป็น in หรือ out")

    gallery = load_gallery(pipeline)
    threshold = _threshold()
    cooldown = _cooldown()
    now_ts = time.time()
    now_local = datetime.now(_tz())
    now_utc = datetime.now(timezone.utc)

    hits = pipeline.detect(frame)
    marked: list[dict] = []
    skipped: list[dict] = []
    unknown = 0

    with _lock:
        for hit in hits:
            emb = pipeline.embed(frame, hit)
            name, sim = match_embedding(pipeline, emb, gallery, threshold)
            hit.name = name
            hit.similarity = sim
            if name == "unknown":
                unknown += 1
                continue

            key = (name, direction)
            prev = _last_marked.get(key, 0.0)
            if now_ts - prev < cooldown:
                profile = _person_snapshot(name)
                skipped.append(
                    {
                        "person_id": name,
                        "display_name": profile["display_name"],
                        "similarity": round(float(sim), 4),
                        "reason": "cooldown",
                        "retry_in_sec": int(cooldown - (now_ts - prev)),
                    }
                )
                continue

            x, y, w, h = hit.box
            crop = frame[max(0, y) : y + h, max(0, x) : x + w]
            snap_name = (
                f"{now_local.strftime('%Y%m%d_%H%M%S')}_{direction}_{name}.jpg"
            )
            snap_path = attendance_dir() / snap_name
            cv2.imwrite(str(snap_path), crop)

            profile = _person_snapshot(name)
            record = {
                "timestamp_local": now_local.isoformat(timespec="seconds"),
                "timestamp_utc": now_utc.isoformat(timespec="seconds"),
                "direction": direction,
                "person_id": name,
                "display_name": profile["display_name"],
                "academic_year": profile["academic_year"],
                "term": profile["term"],
                "grade": profile["grade"],
                "room": profile["room"],
                "similarity": round(float(sim), 4),
                "snapshot": str(snap_path),
                "snapshot_url": f"/api/attendance/snapshot-file/{snap_name}",
            }
            _append_record(record)
            _last_marked[key] = now_ts
            marked.append(record)

    annotated = draw_hits(frame, hits)
    ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("encode รูปไม่สำเร็จ")

    return {
        "ok": True,
        "direction": direction,
        "face_count": len(hits),
        "marked": marked,
        "skipped": skipped,
        "unknown": unknown,
        "threshold": threshold,
        "cooldown_seconds": cooldown,
        "image_jpeg": buf.tobytes(),
    }
