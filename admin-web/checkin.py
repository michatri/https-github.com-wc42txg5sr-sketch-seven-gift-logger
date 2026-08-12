#!/usr/bin/env python3
"""CLI check-in: accept left or right enrolled finger."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pyfingerprint.pyfingerprint import PyFingerprint

DB = Path(os.environ.get("SCHOOL_DB", Path(__file__).with_name("school.db")))
PORT = os.environ.get("FINGERPRINT_PORT", "/dev/serial0")
BAUD = int(os.environ.get("FINGERPRINT_BAUD", "57600"))


def main() -> None:
    sensor = PyFingerprint(PORT, BAUD, 0xFFFFFFFF, 0x00000000)
    if not sensor.verifyPassword():
        raise SystemExit("เซนเซอร์ไม่พร้อม")

    print("วางนิ้วเพื่อเช็คเข้า (ซ้ายหรือขวา)...")
    while not sensor.readImage():
        pass
    sensor.convertImage(0x01)
    position, score = sensor.searchTemplate()
    if position < 0:
        raise SystemExit("ไม่พบลายนิ้วมือในระบบ")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT id, student_code, first_name, last_name, name,
               finger_left_id, finger_right_id, finger_id
        FROM students
        WHERE finger_left_id = ? OR finger_right_id = ? OR finger_id = ?
        """,
        (position, position, position),
    ).fetchone()
    if not row:
        conn.close()
        raise SystemExit(f"พบนิ้ว #{position} แต่ยังไม่ได้ผูกชื่อนักเรียน")

    if row["finger_left_id"] == position:
        hand = "left"
        hand_th = "ซ้าย"
    elif row["finger_right_id"] == position or row["finger_id"] == position:
        hand = "right"
        hand_th = "ขวา"
    else:
        hand = "unknown"
        hand_th = "-"

    conn.execute(
        """
        INSERT INTO attendance(student_id, matched_hand, matched_finger_id)
        VALUES (?, ?, ?)
        """,
        (row["id"], hand, position),
    )
    conn.commit()
    when = conn.execute("SELECT datetime('now','localtime')").fetchone()[0]
    conn.close()

    name = f"{row['first_name'] or row['name']} {row['last_name'] or ''}".strip()
    print(f"เช็คเข้าสำเร็จ: {row['student_code']} {name}")
    print(f"มือ{hand_th} #{position} คะแนน {score}")
    print(f"เวลา: {when}")


if __name__ == "__main__":
    main()
