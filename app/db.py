from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from app.report_schema import ensure_report_schema

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "catholic.db"

DIOCESES = {
    "01": "อัครสังฆมณฑลกรุงเทพฯ",
    "02": "สังฆมณฑลจันทบุรี",
    "03": "สังฆมณฑลเชียงใหม่",
    "04": "สังฆมณฑลนครราชสีมา",
    "05": "สังฆมณฑลอุบลราชธานี",
    "06": "สังฆมณฑลอุดรธานี",
    "07": "สังฆมณฑลราชบุรี",
    "08": "สังฆมณฑลสุราษฎร์ธานี",
    "09": "สังฆมณฑลนครสวรรค์",
    "10": "อัครสังฆมณฑลท่าแร่-หนองแสง",
    "11": "สังฆมณฑลเชียงราย",
}


def diocese_name(church_id: str | None) -> str:
    if not church_id or len(church_id) < 2:
        return ""
    return DIOCESES.get(church_id[:2], "")


@contextmanager
def get_db() -> Iterable[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS report_designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            layout TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    ensure_report_schema(conn)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [{k: r[k] for k in r.keys()} for r in rows]


def today() -> str:
    return date.today().isoformat()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def thai_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d")
        return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"
    except ValueError:
        return value


def display_name(member: dict[str, Any] | None) -> str:
    if not member:
        return ""
    parts = [member.get("saint_name") or "", member.get("first_name") or "", member.get("last_name") or ""]
    return " ".join(p for p in parts if p).strip()


SEARCH_FIELDS = [
    ("name", "ชื่อ"),
    ("last_name", "นามสกุล"),
    ("num", "รหัสประจำตัว"),
    ("saint", "ชื่อนักบุญ"),
    ("gang", "กลุ่ม/สาย"),
    ("address", "บ้านเลขที่"),
    ("family", "ครอบครัวที่"),
    ("occupation", "ลักษณะงาน"),
    ("btsm_parent", "พ่อ/แม่ทูนหัวศีลล้างบาป"),
    ("cnfm_parent", "พ่อ/แม่ทูนหัวศีลกำลัง"),
    ("marriage_witness", "พ่อ/แม่พยานศีลสมรส"),
    ("father", "ชื่อบิดา"),
    ("mother", "ชื่อมารดา"),
    ("btsm_wat", "วัดที่ล้างบาป"),
]


def search_members(conn: sqlite3.Connection, q: str = "", field: str = "name", extra: str = "") -> list[dict[str, Any]]:
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    q = (q or "").strip()
    like = f"%{q}%"

    mapping = {
        "name": "(first_name LIKE ? OR last_name LIKE ? OR saint_name LIKE ?)",
        "last_name": "last_name LIKE ?",
        "num": "num LIKE ?",
        "saint": "saint_name LIKE ?",
        "gang": "gang LIKE ?",
        "address": "(address1 LIKE ? OR address2 LIKE ?)",
        "family": "(from_family LIKE ? OR family_no LIKE ?)",
        "occupation": "occupation LIKE ?",
        "btsm_parent": "btsm_parent LIKE ?",
        "cnfm_parent": "cnfm_parent LIKE ?",
        "marriage_witness": "(mtmn_father LIKE ? OR mtmn_mother LIKE ?)",
        "father": "papa_nm LIKE ?",
        "mother": "mama_nm LIKE ?",
        "btsm_wat": "btsm_wat LIKE ?",
        "birth": "birth_date LIKE ?",
        "death": "dead_date LIKE ?",
    }

    if q:
        sql_part = mapping.get(field, mapping["name"])
        n = sql_part.count("?")
        if field == "name":
            params.extend([like, like, like])
        else:
            params.extend([like] * n)
        clauses.append(sql_part)

    if extra == "alive":
        clauses.append("(dead_date IS NULL OR dead_date = '')")
        clauses.append("(date_out IS NULL OR date_out = '')")
    elif extra == "dead":
        clauses.append("(dead_date IS NOT NULL AND dead_date != '')")
    elif extra == "moved":
        clauses.append("(date_out IS NOT NULL AND date_out != '')")
    elif extra == "single":
        clauses.append("(mtmn_date IS NULL OR mtmn_date = '')")
        clauses.append("(dead_date IS NULL OR dead_date = '')")
    elif extra == "married":
        clauses.append("(mtmn_date IS NOT NULL AND mtmn_date != '')")
    elif extra == "male":
        clauses.append("sex LIKE '%ชาย%'")
    elif extra == "female":
        clauses.append("sex LIKE '%หญิง%'")
    elif extra == "no_baptism":
        clauses.append("(btsm_date IS NULL OR btsm_date = '')")
    elif extra == "no_communion":
        clauses.append("(fm_date IS NULL OR fm_date = '')")
    elif extra == "no_confirm":
        clauses.append("(cnfm_date IS NULL OR cnfm_date = '')")
    elif extra == "no_marriage":
        clauses.append("(mtmn_date IS NULL OR mtmn_date = '')")

    sql = f"SELECT * FROM members WHERE {' AND '.join(clauses)} ORDER BY last_name, first_name, num"
    return rows_to_dicts(conn.execute(sql, params).fetchall())


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    def count(where: str = "1=1") -> int:
        return conn.execute(f"SELECT COUNT(*) FROM members WHERE {where}").fetchone()[0]

    return {
        "members": count(),
        "alive": count("(dead_date IS NULL OR dead_date = '') AND (date_out IS NULL OR date_out = '')"),
        "male": count("sex LIKE '%ชาย%' AND (dead_date IS NULL OR dead_date = '')"),
        "female": count("sex LIKE '%หญิง%' AND (dead_date IS NULL OR dead_date = '')"),
        "families": conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(family_no,''), from_family)) FROM members WHERE family_no IS NOT NULL OR from_family IS NOT NULL"
        ).fetchone()[0]
        or 0,
        "gangs": conn.execute("SELECT COUNT(DISTINCT gang) FROM members WHERE gang IS NOT NULL AND gang != ''").fetchone()[0],
        "baptized": count("btsm_date IS NOT NULL AND btsm_date != ''"),
        "confirmed": count("cnfm_date IS NOT NULL AND cnfm_date != ''"),
        "married": count("mtmn_date IS NOT NULL AND mtmn_date != ''"),
        "deceased": count("dead_date IS NOT NULL AND dead_date != ''"),
        "churches": conn.execute("SELECT COUNT(*) FROM churches WHERE is_header = 0").fetchone()[0],
        "marriages": conn.execute("SELECT COUNT(*) FROM marriage_notifies").fetchone()[0],
        "moves": conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0],
    }


MEMBER_FIELDS = [
    "num", "saint_name", "first_name", "last_name", "old_first_name", "old_last_name",
    "occupation", "gang", "birth_date", "religion", "sex", "go_church", "address1", "address2",
    "tel", "email", "papa_st", "papa_nm", "papa_relig", "mama_st", "mama_nm", "mama_relig",
    "date_in", "from_church", "date_out", "to_church",
    "btsm_no", "btsm_date", "btsm_wat", "btsm_parent", "btsm_st", "btsm_priest",
    "fm_no", "fm_date", "fm_wat", "fm_parent", "fm_st", "fm_priest",
    "cnfm_no", "cnfm_date", "cnfm_wat", "cnfm_parent", "cnfm_st", "cnfm_priest",
    "mtmn_no", "mtmn_date", "mtmn_wat", "refer1", "refer2", "from_family", "family_no",
    "mtmn_father", "mtmn_father_st", "mtmn_mother", "mtmn_mother_st", "mtmn_priest",
    "couple_nm", "couple_religion", "couple_st", "couple_no", "couple_btsm_date", "couple_btsm_no",
    "couple_btsm_place", "couple_church", "couple_fr_nm", "couple_fr_st", "couple_fr_relig",
    "couple_mo_nm", "couple_mo_st", "couple_mo_relig", "couple_memo", "fimn_date", "fimn_priest",
    "dead_no", "citydead_no", "dead_date", "keep_date", "keep_place", "keep_priest", "reason",
    "note1", "note2", "note3", "note4",
]


def next_member_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM members").fetchone()
    return int(row[0])


REPORT_SOURCES = {
    "members": {"label": "สัตบุรุษ", "table": "members", "order": "last_name, first_name, id"},
    "churches": {"label": "รายชื่อวัด", "table": "churches", "order": "id", "where": "is_header = 0"},
    "marriages": {"label": "ใบแจ้งการสมรส", "table": "marriage_notifies", "order": "notify_no, id"},
    "moves": {"label": "การย้ายวัด", "table": "moves", "order": "id DESC"},
    "parish": {"label": "ข้อมูลวัด / หัวกระดาษ", "table": "parish_settings", "order": "id"},
}

REPORT_FIELDS: dict[str, list[tuple[str, str]]] = {
    "members": [
        ("_full_name", "ชื่อเต็ม (นักบุญ+ชื่อ+นามสกุล)"),
        ("num", "รหัสประจำตัว"),
        ("saint_name", "ชื่อนักบุญ"),
        ("first_name", "ชื่อ"),
        ("last_name", "นามสกุล"),
        ("sex", "เพศ"),
        ("religion", "ศาสนา"),
        ("birth_date", "วันเกิด"),
        ("gang", "กลุ่ม/สาย"),
        ("occupation", "ลักษณะงาน"),
        ("go_church", "วัดที่สังกัด"),
        ("_address", "ที่อยู่รวม"),
        ("address1", "ที่อยู่ 1"),
        ("address2", "ที่อยู่ 2"),
        ("tel", "โทรศัพท์"),
        ("email", "อีเมล"),
        ("from_family", "ครอบครัวที่"),
        ("family_no", "เลขที่ครอบครัว"),
        ("_father", "บิดา"),
        ("_mother", "มารดา"),
        ("btsm_no", "เลขที่ศีลล้างบาป"),
        ("btsm_date", "วันที่ล้างบาป"),
        ("btsm_wat", "วัดที่ล้างบาป"),
        ("btsm_parent", "ทูนหัวล้างบาป"),
        ("btsm_priest", "พระสงฆ์ผู้ล้างบาป"),
        ("fm_no", "เลขที่ศีลมหาสนิท"),
        ("fm_date", "วันที่มหาสนิทแรก"),
        ("fm_wat", "วัดมหาสนิทแรก"),
        ("cnfm_no", "เลขที่ศีลกำลัง"),
        ("cnfm_date", "วันที่ศีลกำลัง"),
        ("cnfm_wat", "วัดศีลกำลัง"),
        ("cnfm_parent", "ทูนหัวศีลกำลัง"),
        ("mtmn_no", "เลขที่ศีลสมรส"),
        ("mtmn_date", "วันที่สมรส"),
        ("mtmn_wat", "วัดที่สมรส"),
        ("couple_nm", "ชื่อคู่สมรส"),
        ("couple_st", "นามนักบุญคู่สมรส"),
        ("date_in", "วันที่ย้ายเข้า"),
        ("from_church", "ย้ายมาจากวัด"),
        ("date_out", "วันที่ย้ายออก"),
        ("to_church", "ย้ายไปวัด"),
        ("dead_date", "วันมรณะ"),
        ("keep_place", "สถานที่เก็บศพ"),
        ("note1", "บันทึก 1"),
    ],
    "churches": [
        ("id", "รหัสวัด"),
        ("name", "ชื่อวัด (ทางการ)"),
        ("gen_name", "ชื่อสามัญ"),
        ("address1", "ที่อยู่ 1"),
        ("address2", "ที่อยู่ 2"),
        ("tel", "โทรศัพท์"),
        ("minister", "เจ้าอาวาส"),
        ("asst1", "ผู้ช่วย 1"),
        ("asst2", "ผู้ช่วย 2"),
        ("asst3", "ผู้ช่วย 3"),
    ],
    "marriages": [
        ("notify_no", "เลขที่ใบแจ้ง"),
        ("marriage_id", "เลขที่ทะเบียนสมรส"),
        ("marriage_date", "วันที่สมรส"),
        ("groom", "เจ้าบ่าว"),
        ("gr_religion", "ศาสนาเจ้าบ่าว"),
        ("gr_bap_place", "วัดล้างบาปเจ้าบ่าว"),
        ("gr_bap_date", "วันที่ล้างบาปเจ้าบ่าว"),
        ("bride", "เจ้าสาว"),
        ("br_religion", "ศาสนาเจ้าสาว"),
        ("br_bap_place", "วัดล้างบาปเจ้าสาว"),
        ("br_bap_date", "วันที่ล้างบาปเจ้าสาว"),
        ("witness1", "พยาน 1"),
        ("witness2", "พยาน 2"),
        ("priest", "พระสงฆ์"),
        ("notify_to", "แจ้งไปยังวัด"),
        ("certify_by", "ผู้รับรอง"),
        ("certify_date", "วันที่รับรอง"),
    ],
    "moves": [
        ("num", "รหัสบุคคล"),
        ("date_in", "วันที่ย้ายเข้า"),
        ("from_church", "จากวัด"),
        ("move_from_no", "เลขที่ย้ายจาก"),
        ("from_fr", "เจ้าอาวาสวัดเดิม"),
        ("move_in_by", "ผู้บันทึกย้ายเข้า"),
        ("date_out", "วันที่ย้ายออก"),
        ("to_church", "ไปวัด"),
        ("move_to_no", "เลขที่ย้ายไป"),
        ("receive_in_by", "ผู้รับสังกัด"),
        ("move_out_by", "ผู้บันทึกย้ายออก"),
    ],
    "parish": [
        ("church_th", "ชื่อวัด (ไทย)"),
        ("church_en", "ชื่อวัด (อังกฤษ)"),
        ("addr_th", "ที่อยู่ไทย"),
        ("addr_en", "ที่อยู่อังกฤษ"),
        ("father", "เจ้าอาวาส"),
        ("id_prefix", "รหัสนำหน้า"),
        ("religion", "ศาสนา"),
        ("province", "อำเภอ/จังหวัด"),
        ("church1", "ชื่อวัดสำหรับบัตร"),
        ("sen", "คำขึ้นต้นจดหมาย"),
        ("prefix", "คำนำหน้าชื่อ"),
    ],
}

DATE_FIELDS = {
    "birth_date", "btsm_date", "fm_date", "cnfm_date", "mtmn_date", "date_in", "date_out",
    "dead_date", "keep_date", "fimn_date", "couple_btsm_date", "marriage_date",
    "gr_bap_date", "br_bap_date", "certify_date", "return_date", "updated_at",
}


def field_label(source: str, field: str) -> str:
    for key, label in REPORT_FIELDS.get(source, []):
        if key == field:
            return label
    return field


def enrich_record(source: str, row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    if source == "members":
        data["_full_name"] = display_name(row)
        data["_address"] = " ".join(p for p in [row.get("address1"), row.get("address2")] if p)
        data["_father"] = " ".join(p for p in [row.get("papa_st"), row.get("papa_nm")] if p)
        data["_mother"] = " ".join(p for p in [row.get("mama_st"), row.get("mama_nm")] if p)
    return data


def format_report_value(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if field in DATE_FIELDS or str(field).endswith("_date"):
        return thai_date(value) or "-"
    if value is None or str(value).strip() == "":
        return "-"
    return str(value).strip()


def fetch_report_rows(
    conn: sqlite3.Connection,
    source: str,
    q: str = "",
    limit: int = 100,
    record_id: int | str | None = None,
) -> list[dict[str, Any]]:
    spec = REPORT_SOURCES.get(source)
    if not spec:
        return []
    table = spec["table"]
    clauses: list[str] = []
    params: list[Any] = []
    if spec.get("where"):
        clauses.append(spec["where"])
    if record_id not in (None, ""):
        clauses.append("id = ?")
        params.append(record_id)
    elif q:
        like = f"%{q.strip()}%"
        if source == "members":
            clauses.append("(first_name LIKE ? OR last_name LIKE ? OR saint_name LIKE ? OR num LIKE ?)")
            params.extend([like, like, like, like])
        elif source == "churches":
            clauses.append("(id LIKE ? OR name LIKE ? OR gen_name LIKE ?)")
            params.extend([like, like, like])
        elif source == "marriages":
            clauses.append("(groom LIKE ? OR bride LIKE ? OR CAST(notify_no AS TEXT) LIKE ?)")
            params.extend([like, like, like])
        elif source == "moves":
            clauses.append("(num LIKE ? OR from_church LIKE ? OR to_church LIKE ?)")
            params.extend([like, like, like])
    sql = f"SELECT * FROM {table}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {spec['order']} LIMIT ?"
    params.append(max(1, min(int(limit or 100), 500)))
    return [enrich_record(source, r) for r in rows_to_dicts(conn.execute(sql, params).fetchall())]
