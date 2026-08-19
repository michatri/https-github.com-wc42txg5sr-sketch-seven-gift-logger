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
    id TEXT PRIMARY KEY,
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
    donation_id TEXT NOT NULL,
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
    id TEXT PRIMARY KEY,
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_donation_photos_path ON donation_photos(storage_path);
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
    ("23529", "ชุมชนบางกระดีสายใน"),
    ("11681", "ชุมชนบางกุฎีทอง(ติวานนท์)"),
    ("4534", "ตลาดฐานเพชรปทุม"),
    ("7442", "ตลาดฐานเพชรปทุม จุด 2"),
    ("15503", "อุตสาหกรรมบางกระดี2"),
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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _column_decl(conn: sqlite3.Connection, table: str, column: str) -> str:
    if not _table_exists(conn, table):
        return ""
    for row in conn.execute(f"PRAGMA table_info({table})"):
        if row[1] == column:
            return (row[2] or "").upper()
    return ""


def _is_integer_decl(decl: str) -> bool:
    return "INT" in decl and "TEXT" not in decl


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Upgrade INTEGER primary keys from the first deploy to TEXT UUIDs.

    CREATE TABLE IF NOT EXISTS does not change an existing donations table, so
    importing saintmarkpathum UUIDs into that INTEGER id raised datatype mismatch.
    """
    need_donations = _table_exists(conn, "donations") and _is_integer_decl(
        _column_decl(conn, "donations", "id")
    )
    need_photos = _table_exists(conn, "donation_photos") and _is_integer_decl(
        _column_decl(conn, "donation_photos", "donation_id")
    )
    need_line = _table_exists(conn, "line_groups") and _is_integer_decl(
        _column_decl(conn, "line_groups", "id")
    )
    if not (need_donations or need_photos or need_line):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    if need_donations:
        conn.executescript(
            """
            CREATE TABLE donations_new (
                id TEXT PRIMARY KEY,
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
            INSERT INTO donations_new(
                id, date, pickup_date, store_name, branch_code, pieces, weight_kg,
                baskets, contact_name, position, phone, source, created_at
            )
            SELECT CAST(id AS TEXT), date, pickup_date, store_name, branch_code, pieces, weight_kg,
                   baskets, contact_name, position, phone, source, created_at
            FROM donations;
            DROP TABLE donations;
            ALTER TABLE donations_new RENAME TO donations;
            """
        )
    if need_photos:
        conn.executescript(
            """
            CREATE TABLE donation_photos_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id TEXT NOT NULL,
                storage_path TEXT NOT NULL
            );
            INSERT INTO donation_photos_new(id, donation_id, storage_path)
            SELECT id, CAST(donation_id AS TEXT), storage_path FROM donation_photos;
            DROP TABLE donation_photos;
            ALTER TABLE donation_photos_new RENAME TO donation_photos;
            """
        )
    if need_line:
        conn.executescript(
            """
            CREATE TABLE line_groups_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                group_id TEXT NOT NULL UNIQUE,
                message_type TEXT NOT NULL DEFAULT 'full',
                created_at TEXT NOT NULL
            );
            INSERT INTO line_groups_new(id, name, group_id, message_type, created_at)
            SELECT CAST(id AS TEXT), name, group_id, message_type, created_at FROM line_groups;
            DROP TABLE line_groups;
            ALTER TABLE line_groups_new RENAME TO line_groups;
            """
        )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def init_db(conn: sqlite3.Connection, admin_email: str, admin_password: str) -> None:
    migrate_schema(conn)
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


def default_snapshot_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "import" / "snapshot.json"


def import_snapshot(conn: sqlite3.Connection, snapshot_path: Path | None = None) -> dict[str, int]:
    """Load saintmarkpathum.com dump into an empty (or partial) local database."""
    path = snapshot_path or default_snapshot_path()
    if not path.exists():
        return {"donations": 0, "line_groups": 0, "contacts": 0, "photos": 0}
    import json

    data = json.loads(path.read_text())
    now = utc_now()
    extra = 0
    for b in data.get("extra_branches") or []:
        conn.execute(
            "INSERT OR IGNORE INTO branches(code, name, created_at) VALUES (?,?,?)",
            (b["code"], b["name"], now),
        )
        extra += 1
    contacts = 0
    for c in data.get("branch_contacts") or []:
        conn.execute(
            """
            INSERT INTO branch_contacts(branch_code, branch_name, contact_name, phone, position, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(branch_code) DO UPDATE SET
                branch_name=excluded.branch_name,
                contact_name=excluded.contact_name,
                phone=excluded.phone,
                position=excluded.position,
                updated_at=excluded.updated_at
            """,
            (
                c.get("branch_code"),
                c.get("branch_name"),
                c.get("contact_name"),
                c.get("phone"),
                c.get("position"),
                c.get("updated_at") or now,
            ),
        )
        contacts += 1
        if c.get("branch_code") and c.get("branch_name"):
            conn.execute(
                "INSERT OR IGNORE INTO branches(code, name, created_at) VALUES (?,?,?)",
                (c["branch_code"], c["branch_name"], now),
            )
    donations = 0
    for r in data.get("donations") or []:
        baskets = r.get("baskets")
        try:
            baskets_i = int(baskets) if baskets not in (None, "") else None
        except (TypeError, ValueError):
            baskets_i = None
        conn.execute(
            """
            INSERT OR IGNORE INTO donations(
                id, date, pickup_date, store_name, branch_code, pieces, weight_kg,
                baskets, contact_name, position, phone, source, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(r["id"]),
                r.get("date") or r.get("pickup_date"),
                r.get("pickup_date") or r.get("date"),
                r.get("store_name") or "",
                str(r.get("branch_code") or ""),
                int(r.get("pieces") or 0),
                float(r.get("weight_kg") or 0),
                baskets_i,
                None if r.get("contact_name") in (None, "") else str(r.get("contact_name")),
                None if r.get("position") in (None, "") else str(r.get("position")),
                None if r.get("phone") in (None, "") else str(r.get("phone")),
                r.get("source") or "web",
                r.get("created_at") or now,
            ),
        )
        donations += 1
    line_groups = 0
    for g in data.get("line_groups") or []:
        conn.execute(
            """
            INSERT OR IGNORE INTO line_groups(id, name, group_id, message_type, created_at)
            VALUES (?,?,?,?,?)
            """,
            (
                g["id"],
                g.get("name") or "",
                g.get("group_id") or "",
                g.get("message_type") or "summary",
                g.get("created_at") or now,
            ),
        )
        line_groups += 1
    photos = 0
    for rel in data.get("photos") or []:
        donation_id = str(rel).split("/", 1)[0]
        if not conn.execute("SELECT 1 FROM donations WHERE id=?", (donation_id,)).fetchone():
            continue
        conn.execute(
            "INSERT OR IGNORE INTO donation_photos(donation_id, storage_path) VALUES (?,?)",
            (donation_id, rel),
        )
        photos += 1
    conn.commit()
    return {
        "donations": donations,
        "line_groups": line_groups,
        "contacts": contacts,
        "photos": photos,
        "extra_branches": extra,
    }


def download_imported_photos(snapshot_path: Path | None, photos_dir: Path) -> int:
    """Download donation photos from the public saintmarkpathum storage."""
    import json
    import urllib.request

    path = snapshot_path or default_snapshot_path()
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    photos_dir.mkdir(parents=True, exist_ok=True)
    base = "https://uzunhlbxwpqzdquikoiu.supabase.co/storage/v1/object/public/donation-photos/"
    ok = 0
    for rel in data.get("photos") or []:
        dest = photos_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            ok += 1
            continue
        try:
            urllib.request.urlretrieve(base + rel, dest)
            ok += 1
        except Exception:
            continue
    return ok
