#!/usr/bin/env python3
"""Delete orphan fingerprint templates that are not linked to any student."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pyfingerprint.pyfingerprint import PyFingerprint

DB = Path(os.environ.get("SCHOOL_DB", "/home/master/fingerprint-test/school.db"))
PORT = os.environ.get("FINGERPRINT_PORT", "/dev/serial0")
BAUD = int(os.environ.get("FINGERPRINT_BAUD", "57600"))


def used_positions(db_path: Path) -> set[int]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT finger_id, finger_left_id, finger_right_id
        FROM students
        """
    ).fetchall()
    conn.close()
    used: set[int] = set()
    for finger_id, left_id, right_id in rows:
        for value in (finger_id, left_id, right_id):
            if value is not None:
                used.add(int(value))
    return used


def main() -> None:
    sensor = PyFingerprint(PORT, BAUD, 0xFFFFFFFF, 0x00000000)
    if not sensor.verifyPassword():
        raise SystemExit("เซนเซอร์ไม่พร้อม")

    used = used_positions(DB)
    capacity = sensor.getStorageCapacity()
    deleted: list[int] = []

    # Scan known indexes via template index tables
    for page in range((capacity // 256) + 1):
        try:
            table = sensor.getTemplateIndex(page)
        except Exception:
            break
        for offset, filled in enumerate(table):
            if not filled:
                continue
            pos = page * 256 + offset
            if pos >= capacity:
                continue
            if pos in used:
                continue
            try:
                sensor.deleteTemplate(pos)
                deleted.append(pos)
                print(f"ลบนิ้วค้าง #{pos}")
            except Exception as exc:
                print(f"ลบ #{pos} ไม่ได้: {exc}")

    print(f"เสร็จแล้ว ลบนิ้วค้าง {len(deleted)} รายการ")
    print(f"นิ้วที่ผูกนักเรียนไว้: {sorted(used) if used else '-'}")


if __name__ == "__main__":
    main()
