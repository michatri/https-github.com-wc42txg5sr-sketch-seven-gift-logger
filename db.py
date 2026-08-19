from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS branches (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS branch_contacts (
    branch_code TEXT PRIMARY KEY,
    branch_name TEXT,
    contact_name TEXT,
    phone TEXT,
    position TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    pickup_date TEXT NOT NULL,
    store_name TEXT NOT NULL,
    branch_code TEXT NOT NULL,
    pieces INTEGER NOT NULL,
    weight_kg REAL NOT NULL DEFAULT 0,
    baskets INTEGER,
    contact_name TEXT,
    position TEXT,
    phone TEXT,
    source TEXT NOT NULL DEFAULT 'web',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS donation_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donation_id INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    FOREIGN KEY (donation_id) REFERENCES donations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS branch_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS branch_group_members (
    group_id INTEGER NOT NULL,
    branch_code TEXT NOT NULL,
    PRIMARY KEY (group_id, branch_code),
    FOREIGN KEY (group_id) REFERENCES branch_groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS line_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    group_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL DEFAULT 'full',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS password_resets (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_donations_pickup ON donations(pickup_date, branch_code);
CREATE INDEX IF NOT EXISTS idx_donations_branch ON donations(branch_code);
"""

# สาขาตั้งต้นจากระบบ saintmarkpathum.com
DEFAULT_BRANCHES = [
    ("15005", "หมู่บ้านเมืองเอก-รังสิต"),
    ("2664", "เมืองเอก 3"),
    ("1250", "เมืองเอก 2"),
    ("6941", "โฮมเพลสเมืองเอก"),
    ("12022", "มาลีญาเพลส (หลักหก)"),
    ("1690", "เมืองเอก 6"),
    ("4034", "เมืองเอก 9"),
    ("5336", "เมืองเอก 12"),
    ("15589", "เมืองเอก 12 จุด 2"),
    ("208", "เมืองเอก"),
    ("13109", "Plum Condo พหลโยธิน 89 จุด 3"),
    ("13056", "Plum คอนโด พหลโยธิน 89 จุด 1"),
    ("11433", "STUDENT CENTER ม.รังสิต"),
    ("18044", "ดิวานนท์-ปากเกร็ด 56จุด2"),
    ("19643", "ดิวานนท์-ปากเกร็ด 56จุด3"),
    ("13660", "ปทุมทอง - ปทุมวิไล"),
    ("9512", "ตลาดสดอินเตอร์มาร์ท"),
    ("11583", "สี่แยกปทุมธานี"),
    ("9960", "รพ.ปทุมธานี"),
    ("14733", "เทศบำรุง-สะพานปทุมธานี"),
    ("22839", "ถนน346-เลียบคลองบางไพรี่"),
    ("02196", "ไพร่ฟ้า"),
    ("03919", "ด็อกเตอร์วู๊ด"),
    ("15662", "ศุภาลัยวิลล์ กรุงเทพ-ปทุมธานี"),
    ("23154", "เทศบาล 5 เมืองปทุมธานี"),
    ("23161", "S Market คูบางหลวง"),
    ("07285", "CP RAM (ลาดหลุมแก้ว) จุด1"),
    ("07562", "ตลาดระแหง"),
    ("14842", "ศูนย์การเรียนรู้ CP RAM"),
    ("23014", "ตลาดปทุมไลฟ์"),
    ("02267", "สามโคก"),
    ("11141", "ซีสเปซ สามโคก"),
    ("04201", "หมู่บ้านกฤษณาสามโคก"),
    ("09469", "ภัทรไพเวท 2"),
    ("12125", "เทศบาล 10 สามโคก"),
    ("16300", "จันทร์กะพ้อ"),
    ("17601", "เทศบาล 10 สามโคก จุด 2"),
    ("18992", "เทศบาล 10 สามโคก จุด 3"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection, admin_email: str, admin_password: str) -> None:
    conn.executescript(SCHEMA)
    now = utc_now()
    for code, name in DEFAULT_BRANCHES:
        conn.execute(
            "INSERT OR IGNORE INTO branches(code, name, created_at) VALUES (?,?,?)",
            (code, name, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO branch_contacts(branch_code, branch_name, updated_at) VALUES (?,?,?)",
            (code, name, now),
        )
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users(email, password_hash, created_at) VALUES (?,?,?)",
            (admin_email.lower().strip(), generate_password_hash(admin_password), now),
        )
    conn.commit()
