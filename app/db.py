from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

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
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


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
