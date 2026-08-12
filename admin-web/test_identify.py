#!/usr/bin/env python3
"""Quick sensor identify test for top-up troubleshooting."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pyfingerprint.pyfingerprint import PyFingerprint

DB = Path(os.environ.get("SCHOOL_DB", "/home/master/fingerprint-test/school.db"))
PORT = os.environ.get("FINGERPRINT_PORT", "/dev/serial0")
BAUD = int(os.environ.get("FINGERPRINT_BAUD", "57600"))


def main() -> None:
    print(f"port={PORT} baud={BAUD}")
    print(f"db={DB} exists={DB.exists()}")
    sensor = PyFingerprint(PORT, BAUD, 0xFFFFFFFF, 0x00000000)
    if not sensor.verifyPassword():
        raise SystemExit("เซนเซอร์ไม่พร้อม")
    print("templates:", sensor.getTemplateCount(), "/", sensor.getStorageCapacity())
    print("วางนิ้วเพื่อทดสอบ...")
    while not sensor.readImage():
        pass
    sensor.convertImage(0x01)
    position, score = sensor.searchTemplate()
    print(f"search position={position} score={score}")
    if position < 0:
        raise SystemExit("ไม่พบลายนิ้วมือในเซนเซอร์")

    if not DB.exists():
        raise SystemExit("ไม่พบไฟล์ school.db")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT student_code, first_name, last_name, name, balance,
               finger_left_id, finger_right_id, finger_id
        FROM students
        WHERE finger_left_id = ? OR finger_right_id = ? OR finger_id = ?
        """,
        (position, position, position),
    ).fetchone()
    conn.close()
    if not row:
        raise SystemExit(f"นิ้ว #{position} ไม่ได้ผูกกับนักเรียนในฐานข้อมูล")
    print(
        "OK:",
        row["student_code"],
        f"{row['first_name'] or row['name']} {row['last_name'] or ''}".strip(),
        "balance=",
        row["balance"],
    )


if __name__ == "__main__":
    main()
