#!/usr/bin/env python3
"""นำเข้าข้อมูลจาก saintmarkpathum.com ลง SQLite และดาวน์โหลดรูป"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db as dbmod  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.environ.get("GIFT_DB", str(ROOT / "data" / "gift_logger.db")))
    parser.add_argument("--photos-dir", default=os.environ.get("GIFT_PHOTOS_DIR", str(ROOT / "data" / "photos")))
    parser.add_argument("--snapshot", default=str(dbmod.default_snapshot_path()))
    parser.add_argument("--no-photos", action="store_true")
    parser.add_argument("--admin-email", default=os.environ.get("GIFT_ADMIN_EMAIL", "admin@saintmarkpathum.com"))
    parser.add_argument("--admin-password", default=os.environ.get("GIFT_ADMIN_PASSWORD", "admin123"))
    args = parser.parse_args()

    db_path = Path(args.db)
    photos_dir = Path(args.photos_dir)
    snapshot = Path(args.snapshot)
    conn = dbmod.connect(db_path)
    dbmod.init_db(conn, args.admin_email, args.admin_password)
    stats = dbmod.import_snapshot(conn, snapshot)
    print("imported", stats)
    if not args.no_photos:
        n = dbmod.download_imported_photos(snapshot, photos_dir)
        print("photos downloaded/present", n)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
