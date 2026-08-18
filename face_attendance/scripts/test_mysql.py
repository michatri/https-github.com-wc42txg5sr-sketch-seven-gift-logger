#!/usr/bin/env python3
"""ทดสอบการเชื่อมต่อ MySQL/MariaDB."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.db import mysql_enabled, mysql_settings, ping  # noqa: E402


def main() -> None:
    cfg = mysql_settings()
    print("MYSQL_ENABLED =", mysql_enabled())
    print(
        f"connecting {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )
    try:
        info = ping()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"FAIL: {exc}") from exc
    print("OK")
    print("  database:", info["database"])
    print("  version :", info["version"])
    print("  tables  :", ", ".join(info["tables"]) or "(none)")
    needed = {
        "students",
        "attendance",
        "school_option_years",
        "school_option_rooms",
        "app_meta",
    }
    missing = sorted(needed - set(info["tables"]))
    if missing:
        raise SystemExit(
            "FAIL: ยังไม่มีตาราง "
            + ", ".join(missing)
            + " — รัน scripts/setup_mysql_ubuntu.sh หรือ mysql < sql/schema.sql"
        )
    print("schema OK")


if __name__ == "__main__":
    main()
