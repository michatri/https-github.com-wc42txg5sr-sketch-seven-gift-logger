#!/usr/bin/env python3
"""Import Catholic.mdb (or CSV exports) into SQLite."""
from __future__ import annotations

import csv
import io
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "app" / "data" / "catholic.db"
MDB_CANDIDATES = [
    ROOT / "data" / "Catholic.mdb",
    Path("/home/ubuntu/.cursor/projects/workspace/uploads/Catholic_115e.mdb"),
]


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip('"')
    if not value:
        return None
    for fmt in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().replace("\x00", "")
    return value or None


def mdb_export(mdb: Path, table: str) -> list[dict]:
    raw = subprocess.check_output(["mdb-export", str(mdb), table])
    text = raw.decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parish_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    church_th TEXT,
    church_en TEXT,
    addr_th TEXT,
    addr_en TEXT,
    father TEXT,
    id_prefix TEXT,
    religion TEXT,
    province TEXT,
    church1 TEXT,
    church2 TEXT,
    church3 TEXT,
    sen TEXT,
    prefix TEXT
);

CREATE TABLE IF NOT EXISTS churches (
    id TEXT PRIMARY KEY,
    name TEXT,
    gen_name TEXT,
    address1 TEXT,
    address2 TEXT,
    tel TEXT,
    minister TEXT,
    asst1 TEXT,
    asst2 TEXT,
    asst3 TEXT,
    is_header INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    num TEXT,
    saint_name TEXT,
    updated_at TEXT,
    first_name TEXT,
    last_name TEXT,
    old_first_name TEXT,
    old_last_name TEXT,
    occupation TEXT,
    gang TEXT,
    birth_date TEXT,
    religion TEXT,
    sex TEXT,
    go_church TEXT,
    address1 TEXT,
    address2 TEXT,
    tel TEXT,
    email TEXT,
    papa_st TEXT,
    papa_nm TEXT,
    papa_relig TEXT,
    mama_st TEXT,
    mama_nm TEXT,
    mama_relig TEXT,
    date_in TEXT,
    from_church TEXT,
    date_out TEXT,
    to_church TEXT,
    btsm_no TEXT,
    btsm_date TEXT,
    btsm_wat TEXT,
    btsm_parent TEXT,
    btsm_st TEXT,
    btsm_priest TEXT,
    fm_no TEXT,
    fm_date TEXT,
    fm_wat TEXT,
    fm_parent TEXT,
    fm_st TEXT,
    fm_priest TEXT,
    cnfm_no TEXT,
    cnfm_date TEXT,
    cnfm_wat TEXT,
    cnfm_parent TEXT,
    cnfm_st TEXT,
    cnfm_priest TEXT,
    mtmn_no TEXT,
    mtmn_date TEXT,
    mtmn_wat TEXT,
    refer1 TEXT,
    refer2 TEXT,
    from_family TEXT,
    family_no TEXT,
    mtmn_father TEXT,
    mtmn_father_st TEXT,
    mtmn_mother TEXT,
    mtmn_mother_st TEXT,
    mtmn_priest TEXT,
    couple_nm TEXT,
    couple_religion TEXT,
    couple_st TEXT,
    couple_no TEXT,
    couple_btsm_date TEXT,
    couple_btsm_no TEXT,
    couple_btsm_place TEXT,
    couple_church TEXT,
    couple_fr_nm TEXT,
    couple_fr_st TEXT,
    couple_fr_relig TEXT,
    couple_mo_nm TEXT,
    couple_mo_st TEXT,
    couple_mo_relig TEXT,
    couple_memo TEXT,
    fimn_date TEXT,
    fimn_priest TEXT,
    dead_no TEXT,
    citydead_no TEXT,
    dead_date TEXT,
    keep_date TEXT,
    keep_place TEXT,
    keep_priest TEXT,
    reason TEXT,
    note1 TEXT,
    note2 TEXT,
    note3 TEXT,
    note4 TEXT
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY,
    num TEXT,
    date_in TEXT,
    move_in_by TEXT,
    from_church TEXT,
    move_from_no TEXT,
    from_fr TEXT,
    date_out TEXT,
    move_out_by TEXT,
    to_church TEXT,
    move_to_no TEXT,
    receive_in_by TEXT,
    member_id INTEGER,
    FOREIGN KEY(member_id) REFERENCES members(id)
);

CREATE TABLE IF NOT EXISTS marriage_notifies (
    id INTEGER PRIMARY KEY,
    notify_no INTEGER,
    marriage_id TEXT,
    marriage_date TEXT,
    groom TEXT,
    gr_religion TEXT,
    gr_bap_place TEXT,
    gr_bap_date TEXT,
    gr_bap_no TEXT,
    groom_fr TEXT,
    gr_fr_religion TEXT,
    groom_mo TEXT,
    gr_mo_religion TEXT,
    bride TEXT,
    br_religion TEXT,
    br_bap_place TEXT,
    br_bap_date TEXT,
    br_bap_no TEXT,
    bride_fr TEXT,
    br_fr_religion TEXT,
    bride_mo TEXT,
    br_mo_religion TEXT,
    witness1 TEXT,
    witness2 TEXT,
    priest TEXT,
    certify_by TEXT,
    certify_date TEXT,
    notify_to TEXT,
    return_date TEXT,
    return_by TEXT,
    member_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_members_name ON members(first_name, last_name);
CREATE INDEX IF NOT EXISTS idx_members_num ON members(num);
CREATE INDEX IF NOT EXISTS idx_members_gang ON members(gang);
CREATE INDEX IF NOT EXISTS idx_members_family ON members(from_family, family_no);
CREATE INDEX IF NOT EXISTS idx_churches_name ON churches(name, gen_name);

CREATE TABLE IF NOT EXISTS report_designs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    layout TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def seed_user(conn: sqlite3.Connection) -> None:
    from passlib.hash import pbkdf2_sha256

    exists = conn.execute("SELECT 1 FROM users WHERE username = ?", ("admin",)).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name, created_at) VALUES (?,?,?,?)",
        ("admin", pbkdf2_sha256.hash("password"), "ผู้ดูแลระบบ", datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def import_all(mdb: Path) -> None:
    conn = connect()
    init_schema(conn)

    churches = mdb_export(mdb, "Church")
    conn.execute("DELETE FROM churches")
    for row in churches:
        cid = clean(row.get("id-church"))
        if not cid:
            continue
        name = clean(row.get("name-church")) or ""
        is_header = 1 if cid.endswith("0000") or name.startswith("(") else 0
        conn.execute(
            """INSERT INTO churches (id, name, gen_name, address1, address2, tel, minister, asst1, asst2, asst3, is_header)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                name,
                clean(row.get("gen-name-church")),
                clean(row.get("address1")),
                clean(row.get("address2")),
                clean(row.get("tel")),
                clean(row.get("minister-church")),
                clean(row.get("asst1")),
                clean(row.get("asst2")),
                clean(row.get("asst3")),
                is_header,
            ),
        )

    prints = mdb_export(mdb, "Print")
    conn.execute("DELETE FROM parish_settings")
    if prints:
        p = prints[0]
        conn.execute(
            """INSERT INTO parish_settings
               (id, church_th, church_en, addr_th, addr_en, father, id_prefix, religion, province, church1, church2, church3, sen, prefix)
               VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                clean(p.get("ChurchT")),
                clean(p.get("ChurchE")),
                clean(p.get("AddrT")),
                clean(p.get("AddrE")),
                clean(p.get("Father")),
                clean(p.get("ID")),
                clean(p.get("Religion")) or "คาทอลิก",
                clean(p.get("Provience")),
                clean(p.get("Church1")),
                clean(p.get("Church2")),
                clean(p.get("Church3")),
                clean(p.get("sen")) or "เรียน",
                clean(p.get("Prefix")) or "คุณ",
            ),
        )

    members = mdb_export(mdb, "Cattolici")
    conn.execute("DELETE FROM marriage_notifies")
    conn.execute("DELETE FROM moves")
    conn.execute("DELETE FROM members")
    for row in members:
        conn.execute(
            """INSERT INTO members (
                id, num, saint_name, updated_at, first_name, last_name, old_first_name, old_last_name,
                occupation, gang, birth_date, religion, sex, go_church, address1, address2, tel, email,
                papa_st, papa_nm, papa_relig, mama_st, mama_nm, mama_relig, date_in, from_church, date_out, to_church,
                btsm_no, btsm_date, btsm_wat, btsm_parent, btsm_st, btsm_priest,
                fm_no, fm_date, fm_wat, fm_parent, fm_st, fm_priest,
                cnfm_no, cnfm_date, cnfm_wat, cnfm_parent, cnfm_st, cnfm_priest,
                mtmn_no, mtmn_date, mtmn_wat, refer1, refer2, from_family, family_no,
                mtmn_father, mtmn_father_st, mtmn_mother, mtmn_mother_st, mtmn_priest,
                couple_nm, couple_religion, couple_st, couple_no, couple_btsm_date, couple_btsm_no,
                couple_btsm_place, couple_church, couple_fr_nm, couple_fr_st, couple_fr_relig,
                couple_mo_nm, couple_mo_st, couple_mo_relig, couple_memo, fimn_date, fimn_priest,
                dead_no, citydead_no, dead_date, keep_date, keep_place, keep_priest, reason,
                note1, note2, note3, note4
            ) VALUES ("""
            + ",".join(["?"] * 86)
            + ")",
            (
                int(row["ID"]) if row.get("ID") else None,
                clean(row.get("NUM")),
                clean(row.get("st")),
                parse_date(row.get("Update")),
                clean(row.get("nm")),
                clean(row.get("sur")),
                clean(row.get("old_nm")),
                clean(row.get("old_sur")),
                clean(row.get("occupation")),
                clean(row.get("Gang")),
                parse_date(row.get("birth_date")),
                clean(row.get("religion")) or "คาทอลิก",
                clean(row.get("sex")),
                clean(row.get("go_church")),
                clean(row.get("address1")),
                clean(row.get("address2")),
                clean(row.get("tel")),
                clean(row.get("e_mail")),
                clean(row.get("papa_st")),
                clean(row.get("papa_nm")),
                clean(row.get("papa_relig")),
                clean(row.get("mama_st")),
                clean(row.get("mama_nm")),
                clean(row.get("mama_relig")),
                parse_date(row.get("DateIn")),
                clean(row.get("From_church")),
                parse_date(row.get("DateOut")),
                clean(row.get("To_church")),
                clean(row.get("btsm_No")),
                parse_date(row.get("btsm_date")),
                clean(row.get("btsm_wat")),
                clean(row.get("btsm_parent")),
                clean(row.get("btsm_st")),
                clean(row.get("btsm_priest")),
                clean(row.get("fm_No")),
                parse_date(row.get("fm_date")),
                clean(row.get("fm_wat")),
                clean(row.get("fm_parent")),
                clean(row.get("fm_st")),
                clean(row.get("fm_priest")),
                clean(row.get("cnfm_No")),
                parse_date(row.get("cnfm_date")),
                clean(row.get("cnfm_wat")),
                clean(row.get("cnfm_parent")),
                clean(row.get("cnfm_st")),
                clean(row.get("cnfm_priest")),
                clean(row.get("mtmn_No")),
                parse_date(row.get("mtmn_date")),
                clean(row.get("mtmn_wat")),
                clean(row.get("refer1")),
                clean(row.get("refer2")),
                clean(row.get("from_family")),
                clean(row.get("family_No")),
                clean(row.get("mtmn_father")),
                clean(row.get("mtmn_fatherSt")),
                clean(row.get("mtmn_mother")),
                clean(row.get("mtmn_motherSt")),
                clean(row.get("mtmn_priest")),
                clean(row.get("couple_nm")),
                clean(row.get("couple_Religion")),
                clean(row.get("couple_St")),
                clean(row.get("couple_No")),
                parse_date(row.get("couple_btsmDate")),
                clean(row.get("couple_btsmNo")),
                clean(row.get("couple_btsmPlace")),
                clean(row.get("couple_church")),
                clean(row.get("couple_FrNm")),
                clean(row.get("couple_FrSt")),
                clean(row.get("couple_FrRelig")),
                clean(row.get("couple_MoNm")),
                clean(row.get("couple_MoSt")),
                clean(row.get("couple_MoRelig")),
                clean(row.get("couple_Memo")),
                parse_date(row.get("fimn_date")),
                clean(row.get("fimn_priest")),
                clean(row.get("dead_No")),
                clean(row.get("citydead_No")),
                parse_date(row.get("dead_date")),
                parse_date(row.get("keep_date")),
                clean(row.get("keep_place")),
                clean(row.get("keep_priest")),
                clean(row.get("reason")),
                clean(row.get("note1")),
                clean(row.get("note2")),
                clean(row.get("note3")),
                clean(row.get("note4")),
            ),
        )

    for row in mdb_export(mdb, "Move"):
        conn.execute(
            """INSERT INTO moves (id, num, date_in, move_in_by, from_church, move_from_no, from_fr,
               date_out, move_out_by, to_church, move_to_no, receive_in_by, member_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                int(row["ID"]) if row.get("ID") else None,
                clean(row.get("Num")),
                parse_date(row.get("DateIn")),
                clean(row.get("MoveInBy")),
                clean(row.get("FromChurch")),
                clean(row.get("MoveFromNo")),
                clean(row.get("FromFr")),
                parse_date(row.get("DateOut")),
                clean(row.get("MoveOutBy")),
                clean(row.get("ToChurch")),
                clean(row.get("MoveToNo")),
                clean(row.get("ReceiveInBy")),
                int(row["CatID"]) if row.get("CatID") else None,
            ),
        )

    for row in mdb_export(mdb, "MarriageNotify"):
        conn.execute(
            """INSERT INTO marriage_notifies (
                id, notify_no, marriage_id, marriage_date, groom, gr_religion, gr_bap_place, gr_bap_date, gr_bap_no,
                groom_fr, gr_fr_religion, groom_mo, gr_mo_religion, bride, br_religion, br_bap_place, br_bap_date, br_bap_no,
                bride_fr, br_fr_religion, bride_mo, br_mo_religion, witness1, witness2, priest, certify_by, certify_date,
                notify_to, return_date, return_by
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                int(row["ID"]) if row.get("ID") else None,
                int(row["Notify_No"]) if row.get("Notify_No") else None,
                clean(row.get("MarriageID")),
                parse_date(row.get("Marriage_Date")),
                clean(row.get("Groom")),
                clean(row.get("Gr_religion")),
                clean(row.get("GrBap_place")),
                parse_date(row.get("GrBap_Date")),
                clean(row.get("GrBap_No")),
                clean(row.get("Groom_Fr")),
                clean(row.get("GrFr_religion")),
                clean(row.get("Groom_Mo")),
                clean(row.get("GrMo_religion")),
                clean(row.get("Bride")),
                clean(row.get("Br_religion")),
                clean(row.get("BrBap_place")),
                parse_date(row.get("BrBap_Date")),
                clean(row.get("BrBap_No")),
                clean(row.get("Bride_Fr")),
                clean(row.get("BrFr_religion")),
                clean(row.get("Bride_Mo")),
                clean(row.get("BrMo_religion")),
                clean(row.get("Witness1")),
                clean(row.get("Witness2")),
                clean(row.get("Priest")),
                clean(row.get("Certify_By")),
                parse_date(row.get("Certify_Date")),
                clean(row.get("Notify_to")),
                parse_date(row.get("Return_Date")),
                clean(row.get("Return_By")),
            ),
        )

    seed_user(conn)
    conn.commit()
    conn.close()
    print(f"Imported into {DB_PATH}")


def main() -> None:
    mdb = next((p for p in MDB_CANDIDATES if p.exists()), None)
    if not mdb:
        raise SystemExit("Catholic.mdb not found")
    import_all(mdb)


if __name__ == "__main__":
    main()
