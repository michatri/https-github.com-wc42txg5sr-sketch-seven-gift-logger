#!/usr/bin/env python3
"""ย้ายข้อมูลจากไฟล์ (gallery/attendance/school_options) เข้า MySQL."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.camera import DATA  # noqa: E402
from face_attendance.lib.db import ping  # noqa: E402
from face_attendance.lib import db_store  # noqa: E402


def migrate_students() -> int:
    gallery = DATA / "gallery"
    if not gallery.exists():
        return 0
    count = 0
    for person_dir in sorted(gallery.iterdir()):
        if not person_dir.is_dir():
            continue
        emb_path = person_dir / "embedding.npy"
        if not emb_path.exists():
            continue
        meta = {"person_id": person_dir.name, "display_name": person_dir.name}
        meta_path = person_dir / "meta.json"
        if meta_path.exists():
            try:
                meta.update(json.loads(meta_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        emb = np.load(emb_path)
        preview = None
        preview_path = person_dir / "preview.jpg"
        if preview_path.exists():
            preview = preview_path.read_bytes()
        db_store.upsert_student(meta, embedding=emb, preview_jpeg=preview)
        count += 1
        print(f"  student {meta['person_id']}")
    return count


def migrate_attendance() -> int:
    att_dir = DATA / "attendance"
    if not att_dir.exists():
        return 0
    # ensure students exist for FK — unknown ids get placeholder
    count = 0
    for path in sorted(att_dir.glob("attendance_*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                person_id = str(row.get("person_id") or "").strip()
                if not person_id:
                    continue
                if db_store.get_student(person_id) is None:
                    db_store.upsert_student(
                        {
                            "person_id": person_id,
                            "display_name": row.get("display_name") or person_id,
                            "academic_year": row.get("academic_year") or "",
                            "term": row.get("term") or "",
                            "grade": row.get("grade") or "",
                            "room": row.get("room") or "",
                        },
                        embedding=None,
                        preview_jpeg=None,
                    )
                db_store.insert_attendance(row)
                count += 1
    return count


def migrate_options() -> tuple[int, int]:
    years = 0
    rooms = 0
    opt_path = ROOT / "config" / "school_options.json"
    if opt_path.exists():
        try:
            data = json.loads(opt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for y in data.get("academic_years") or []:
            db_store.add_option_year(str(y))
            years += 1
        for r in data.get("rooms") or []:
            db_store.add_option_room(str(r))
            rooms += 1
    # also collect from students already migrated
    for s in db_store.list_students():
        if s.get("academic_year"):
            db_store.add_option_year(str(s["academic_year"]))
        if s.get("room"):
            db_store.add_option_room(str(s["room"]))
    return years, rooms


def main() -> None:
    print("ping MySQL...")
    info = ping()
    print("  db:", info["database"], "tables:", len(info["tables"]))

    print("migrate students...")
    n_students = migrate_students()
    print(f"  -> {n_students} students")

    print("migrate attendance...")
    n_att = migrate_attendance()
    print(f"  -> {n_att} attendance rows")

    print("migrate options...")
    y, r = migrate_options()
    print(f"  -> years added from file: {y}, rooms: {r}")

    print("DONE")
    print("ตั้ง MYSQL_ENABLED=1 ใน config/database.env เมื่อพร้อมใช้งานจริง")


if __name__ == "__main__":
    main()
