"""MySQL/MariaDB connection helpers for face attendance."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def load_database_env() -> None:
    path = CONFIG / "database.env"
    example = CONFIG / "database.example.env"
    if path.exists():
        load_dotenv(path, override=False)
    elif example.exists():
        load_dotenv(example, override=False)


def mysql_enabled() -> bool:
    load_database_env()
    return os.getenv("MYSQL_ENABLED", "0").strip() in {"1", "true", "True", "yes"}


def mysql_settings() -> dict[str, Any]:
    load_database_env()
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "faceapp").strip(),
        "password": os.getenv("MYSQL_PASSWORD", "").strip(),
        "database": os.getenv("MYSQL_DATABASE", "face_attendance").strip(),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": None,  # filled after import
    }


def get_connection():
    """Return a new PyMySQL connection."""
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:
        raise RuntimeError(
            "ยังไม่ได้ติดตั้ง pymysql — รัน: pip install pymysql"
        ) from exc

    cfg = mysql_settings()
    if not cfg["password"]:
        raise RuntimeError("ตั้ง MYSQL_PASSWORD ใน config/database.env ก่อน")
    cfg["cursorclass"] = DictCursor
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
        autocommit=False,
        cursorclass=cfg["cursorclass"],
    )


@contextmanager
def db_cursor(*, commit: bool = False) -> Iterator[Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping() -> dict[str, Any]:
    with db_cursor() as cur:
        cur.execute("SELECT DATABASE() AS db, VERSION() AS version")
        row = cur.fetchone() or {}
        cur.execute(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() ORDER BY table_name"
        )
        tables = [r["name"] for r in cur.fetchall()]
    return {
        "ok": True,
        "database": row.get("db"),
        "version": row.get("version"),
        "tables": tables,
        "enabled": mysql_enabled(),
    }
