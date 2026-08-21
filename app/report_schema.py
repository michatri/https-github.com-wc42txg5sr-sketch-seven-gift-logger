"""Report-metadata tables and live schema browsing. Catholic data tables are never altered."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

TABLE_LABELS = {
    "members": "สัตบุรุษ (Cattolici)",
    "churches": "วัด (Church)",
    "marriage_notifies": "ใบแจ้งสมรส (MarriageNotify)",
    "moves": "การย้ายวัด (Move)",
    "parish_settings": "หัวกระดาษ (Print)",
    "report_designs": "แบบรายงานเดิม (ไม่ใช่ทะเบียน)",
    "reports": "รายงานที่บันทึก",
    "report_datasets": "ชุดข้อมูลรายงาน",
    "report_data_sources": "แหล่งข้อมูลรายงาน",
    "report_parameters": "พารามิเตอร์รายงาน",
    "report_permissions": "สิทธิ์รายงาน",
    "report_versions": "เวอร์ชันรายงาน",
}

COLUMN_LABELS: dict[str, dict[str, str]] = {
    "members": {
        "id": "ID",
        "num": "รหัสประจำตัว",
        "saint_name": "ชื่อนักบุญ",
        "first_name": "ชื่อ",
        "last_name": "นามสกุล",
        "occupation": "ลักษณะงาน",
        "gang": "กลุ่ม/สาย",
        "birth_date": "วันเกิด",
        "religion": "ศาสนา",
        "sex": "เพศ",
        "go_church": "วัดที่สังกัด",
        "address1": "ที่อยู่ 1",
        "address2": "ที่อยู่ 2",
        "tel": "โทรศัพท์",
        "email": "อีเมล",
        "papa_nm": "ชื่อบิดา",
        "mama_nm": "ชื่อมารดา",
        "btsm_date": "วันที่ล้างบาป",
        "btsm_wat": "วัดที่ล้างบาป",
        "cnfm_date": "วันที่ศีลกำลัง",
        "mtmn_date": "วันที่สมรส",
        "family_no": "เลขที่ครอบครัว",
        "dead_date": "วันมรณะ",
        "btsm_priest": "พระสงฆ์ผู้ล้างบาป",
        "from_family": "ครอบครัวที่",
    },
    "marriage_notifies": {
        "marriage_id": "เลขที่ทะเบียนสมรส (MarriageID)",
        "marriage_date": "วันที่สมรส",
        "groom": "เจ้าบ่าว",
        "bride": "เจ้าสาว",
        "priest": "พระสงฆ์",
        "witness1": "พยาน 1",
        "witness2": "พยาน 2",
        "notify_to": "แจ้งไปยังวัด",
    },
    "churches": {
        "id": "รหัสวัด",
        "name": "ชื่อวัด",
        "gen_name": "ชื่อสามัญ",
        "minister": "เจ้าอาวาส",
    },
    "moves": {
        "num": "รหัสบุคคล",
        "from_church": "จากวัด",
        "to_church": "ไปวัด",
        "member_id": "รหัสสัตบุรุษ",
    },
}

# Suggested joins only — never applied unless the user picks them.
SUGGESTED_JOINS = [
    {
        "from_table": "moves",
        "from_column": "member_id",
        "to_table": "members",
        "to_column": "id",
        "label": "การย้ายวัด → สัตบุรุษ",
    },
    {
        "from_table": "marriage_notifies",
        "from_column": "member_id",
        "to_table": "members",
        "to_column": "id",
        "label": "ใบแจ้งสมรส → สัตบุรุษ",
    },
]

import re

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HIDDEN_TABLES = {"sqlite_sequence"}
SECRET_COLUMNS = {("users", "password_hash")}
METADATA_TABLES = {
    "report_data_sources",
    "report_datasets",
    "reports",
    "report_parameters",
    "report_permissions",
    "report_versions",
    "report_designs",
    "users",
}

DDL = """
CREATE TABLE IF NOT EXISTS report_data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    adapter TEXT NOT NULL,
    connection_info TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    data_source_id INTEGER,
    query_config_json TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(data_source_id) REFERENCES report_data_sources(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    dataset_id INTEGER,
    layout_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_by TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(dataset_id) REFERENCES report_datasets(id)
);

CREATE TABLE IF NOT EXISTS report_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    label TEXT,
    data_type TEXT NOT NULL DEFAULT 'text',
    default_value TEXT,
    required INTEGER NOT NULL DEFAULT 0,
    options_json TEXT,
    FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    can_view INTEGER NOT NULL DEFAULT 1,
    can_edit INTEGER NOT NULL DEFAULT 0,
    can_print INTEGER NOT NULL DEFAULT 1,
    can_export_pdf INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS report_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    layout_json TEXT NOT NULL,
    query_config_json TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reports_updated ON reports(updated_at);
CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports(created_by);
CREATE INDEX IF NOT EXISTS idx_report_params_report ON report_parameters(report_id);
CREATE INDEX IF NOT EXISTS idx_report_perm_report ON report_permissions(report_id);
CREATE INDEX IF NOT EXISTS idx_report_ver_report ON report_versions(report_id);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_report_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    row = conn.execute(
        "SELECT id FROM report_data_sources WHERE adapter = 'sqlite' ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        conn.execute(
            """INSERT INTO report_data_sources (name, description, adapter, connection_info, created_at)
               VALUES (?,?,?,?,?)""",
            (
                "ทะเบียนสัตบุรุษ (Catholic.mdb)",
                "นำเข้าจาก Microsoft Access แล้วอ่านผ่านแบ็กเอนด์เท่านั้น เบราว์เซอร์ไม่เชื่อมต่อไฟล์ MDB",
                "sqlite",
                json.dumps({"kind": "local-sqlite", "note": "app/data/catholic.db"}),
                _now(),
            ),
        )


def is_ident(name: str | None) -> bool:
    return bool(name and IDENT_RE.match(name))


def quote_ident(name: str) -> str:
    if not is_ident(name):
        raise ValueError("invalid identifier")
    return '"' + name + '"'


def is_secret_column(table: str, column: str) -> bool:
    return (table, column) in SECRET_COLUMNS


def list_objects(conn: sqlite3.Connection, include_metadata: bool = True) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT name, type FROM sqlite_master
           WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
           ORDER BY name"""
    ).fetchall()
    out = []
    for row in rows:
        name = row["name"]
        if name in HIDDEN_TABLES:
            continue
        if name == "users" and not include_metadata:
            continue
        if name in METADATA_TABLES and not include_metadata:
            continue
        out.append(
            {
                "name": name,
                "type": row["type"],
                "label": TABLE_LABELS.get(name, name),
                "isMetadata": name in METADATA_TABLES,
            }
        )
    return out


def table_columns(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    q = quote_ident(table)
    info = conn.execute(f"PRAGMA table_info({q})").fetchall()
    fks = conn.execute(f"PRAGMA foreign_key_list({q})").fetchall()
    fk_cols = {r["from"]: {"table": r["table"], "to": r["to"]} for r in fks}
    labels = COLUMN_LABELS.get(table, {})
    cols = []
    for row in info:
        name = row["name"]
        if is_secret_column(table, name):
            continue
        cols.append(
            {
                "name": name,
                "type": row["type"] or "TEXT",
                "notNull": bool(row["notnull"]),
                "pk": bool(row["pk"]),
                "default": row["dflt_value"],
                "label": labels.get(name, name),
                "fk": fk_cols.get(name),
            }
        )
    return cols


def table_relationships(conn: sqlite3.Connection, table: str | None = None) -> list[dict[str, Any]]:
    rels: list[dict[str, Any]] = []
    objects = list_objects(conn, include_metadata=True)
    names = {o["name"] for o in objects}
    for obj in objects:
        if table and obj["name"] != table:
            continue
        if not is_ident(obj["name"]):
            continue
        for row in conn.execute(f"PRAGMA foreign_key_list({quote_ident(obj['name'])})").fetchall():
            rels.append(
                {
                    "from_table": obj["name"],
                    "from_column": row["from"],
                    "to_table": row["table"],
                    "to_column": row["to"],
                    "source": "foreign_key",
                    "label": f"{obj['name']}.{row['from']} → {row['table']}.{row['to']}",
                }
            )
    seen = {(r["from_table"], r["from_column"], r["to_table"], r["to_column"]) for r in rels}
    for sug in SUGGESTED_JOINS:
        key = (sug["from_table"], sug["from_column"], sug["to_table"], sug["to_column"])
        if key in seen:
            continue
        if sug["from_table"] in names and sug["to_table"] in names:
            if table and table not in (sug["from_table"], sug["to_table"]):
                continue
            rels.append({**sug, "source": "suggested"})
    return rels


def schema_catalog(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = []
    for obj in list_objects(conn, include_metadata=False):
        cols = table_columns(conn, obj["name"])
        tables.append({**obj, "columns": cols, "primaryKeys": [c["name"] for c in cols if c["pk"]]})
    return {
        "tables": tables,
        "relationships": table_relationships(conn),
        "suggestedJoins": SUGGESTED_JOINS,
    }
