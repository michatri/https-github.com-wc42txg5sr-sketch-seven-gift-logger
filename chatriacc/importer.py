"""นำเข้าข้อมูลจากไฟล์โปรแกรมบัญชีวัด AC25 (.xlsb)."""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
from pathlib import Path

from .dates import iso_date
from .money import baht_to_satang

SEED_XLSB = Path(__file__).resolve().parent / "seed" / "AC25-209.xlsb"


def _cell(row: dict, col: int):
    return row.get(col)


def _num(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip().upper()
        if not text or text == "X":
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _code(value):
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().upper() == "X":
        return "X"
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _money(value) -> int:
    if value in (None, ""):
        return 0
    try:
        return baht_to_satang(value)
    except Exception:
        return 0


def _sheet_rows(path: Path, name: str) -> list[dict]:
    from pyxlsb import open_workbook

    rows = []
    with open_workbook(str(path)) as wb:
        with wb.get_sheet(name) as sheet:
            for row in sheet.rows():
                cells = {c.c: c.v for c in row if c.v not in (None, "")}
                rows.append(cells)
    return rows


def _collect_vouchers(rows: list[dict], kind: str) -> list[dict]:
    if kind == "rv":
        cols = {
            "number": 8,
            "detail": 9,
            "money": 10,
            "code": 11,
            "bank": 12,
            "officer": 13,
            "reviewer": 14,
            "year": 15,
            "date": 7,
            "cq_no": 19,
            "cq_date": 20,
            "cq_from": 21,
            "orig_code": 22,
            "cancel_time": 23,
        }
    else:
        cols = {
            "number": 54,
            "detail": 55,
            "money": 56,
            "code": 57,
            "bank": 58,
            "officer": 59,
            "reviewer": 60,
            "year": 61,
            "date": 53,
            "cq_no": 65,
            "cq_date": 66,
            "cq_from": 67,
            "orig_code": 68,
            "cancel_time": 69,
        }

    grouped: dict[tuple, dict] = {}
    order: list[tuple] = []
    for cells in rows[2:]:
        number = _num(_cell(cells, cols["number"]))
        detail = str(_cell(cells, cols["detail"]) or "").strip()
        amount = _money(_cell(cells, cols["money"]))
        year = _num(_cell(cells, cols["year"]))
        txn = iso_date(_cell(cells, cols["date"]))
        if not number or not detail or not year or not txn:
            continue
        raw_code = _code(_cell(cells, cols["code"]))
        orig = _code(_cell(cells, cols["orig_code"]))
        cancelled = raw_code == "X"
        account = orig if cancelled and orig not in (None, "X") else raw_code
        if account in (None, "X"):
            continue
        key = (kind, year, number)
        if key not in grouped:
            grouped[key] = {
                "kind": kind,
                "number": number,
                "year": year,
                "officer": str(_cell(cells, cols["officer"]) or "").strip("() "),
                "reviewer": str(_cell(cells, cols["reviewer"]) or "").strip("() "),
                "cancelled": cancelled,
                "cancelled_at": iso_date(_cell(cells, cols["cancel_time"])) or None,
                "created_at": iso_date(_cell(cells, cols["date"])) or None,
                "lines": [],
                "transfers": [],
            }
            order.append(key)
        else:
            grouped[key]["cancelled"] = grouped[key]["cancelled"] or cancelled
        grouped[key]["lines"].append(
            {
                "txn_date": txn,
                "detail": detail,
                "amount_satang": amount,
                "account_code": int(account),
                "bank_flag": 1 if _cell(cells, cols["bank"]) else 0,
            }
        )
        cq_no = _cell(cells, cols["cq_no"])
        if cq_no not in (None, "", 0, 0.0):
            grouped[key]["transfers"].append(
                {
                    "number": str(cq_no).strip(),
                    "transfer_date": iso_date(_cell(cells, cols["cq_date"])),
                    "party": str(_cell(cells, cols["cq_from"]) or "").strip(),
                    "amount_satang": amount if _cell(cells, cols["bank"]) else 0,
                }
            )
    return [grouped[k] for k in order]


def parse_assets(rows: list[dict]) -> list[dict]:
    items = []
    for cells in rows[5:]:
        if _cell(cells, 2) and _cell(cells, 1):
            items.append(
                {
                    "direction": "in",
                    "txn_date": iso_date(_cell(cells, 1)),
                    "description": str(_cell(cells, 2)).strip(),
                    "qty": _num(_cell(cells, 4)),
                    "amount_satang": _money(_cell(cells, 5)),
                    "location": str(_cell(cells, 6) or "").strip(),
                    "code": str(_cell(cells, 7) or "").strip(),
                    "reason": "",
                }
            )
        if _cell(cells, 11) and _cell(cells, 9):
            items.append(
                {
                    "direction": "out",
                    "txn_date": iso_date(_cell(cells, 9)),
                    "description": str(_cell(cells, 11)).strip(),
                    "qty": _num(_cell(cells, 12)),
                    "amount_satang": _money(_cell(cells, 13)),
                    "location": "",
                    "code": str(_cell(cells, 10) or "").strip(),
                    "reason": str(_cell(cells, 14) or "").strip(),
                }
            )
    return [a for a in items if a["txn_date"] and a["description"]]


def parse_budget(rows: list[dict]) -> tuple[dict[int, int], list[dict]]:
    amounts: dict[int, int] = {}
    for cells in rows:
        for code_col, amt_col in ((1, 3), (5, 7)):
            code = _num(_cell(cells, code_col))
            if code and 4000 <= code < 6000:
                amounts[code] = _money(_cell(cells, amt_col))
    projects = []
    # งาน/โครงการ 1-10 start at col 9/10, budget col 15; 11-20 at col 18/19, budget 24
    pairs = [(9, 10, 15), (18, 19, 24)]
    by_seq: dict[int, dict] = {}
    for i, cells in enumerate(rows):
        for base, name_col, amt_col in pairs:
            label = str(_cell(cells, base) or "")
            if "งานโครงการ" not in label and "งานโครงการ" not in label.replace(" ", ""):
                if not label.startswith("ช่วงเดือน"):
                    continue
            name = str(_cell(cells, name_col) or "").strip()
            if "งานโครงการ" in label or label.startswith("งานโครงการ"):
                seq = _num(label.split(".")[0].strip()) if "." in label else None
                if seq is None:
                    try:
                        seq = int("".join(ch for ch in label if ch.isdigit()) or 0)
                    except ValueError:
                        seq = 0
                if seq:
                    by_seq[seq] = {
                        "name": name,
                        "period": "",
                        "amount_satang": _money(_cell(cells, amt_col)),
                    }
            elif label.startswith("ช่วงเดือน"):
                # previous project in this column group
                nearby = [
                    s
                    for s, p in by_seq.items()
                    if (s <= 10 and base == 9) or (s >= 11 and base == 18)
                ]
                if nearby:
                    last = max(nearby)
                    by_seq[last]["period"] = name
                    if _cell(cells, amt_col):
                        by_seq[last]["amount_satang"] = _money(_cell(cells, amt_col))
    for seq in sorted(by_seq):
        p = by_seq[seq]
        if p["name"] or p["amount_satang"]:
            projects.append(p)
    return amounts, projects


def import_xlsb(store, path: str | Path, replace: bool = True) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ {path}")
    data_rows = _sheet_rows(path, "DATA")
    rv = _collect_vouchers(data_rows, "rv")
    pv = _collect_vouchers(data_rows, "pv")
    years = {v["year"] for v in rv + pv}
    if replace:
        for year in years:
            store.clear_year_data(year)
    created = 0
    skipped = 0
    for voucher in rv + pv:
        try:
            store.create_voucher(
                kind=voucher["kind"],
                lines=voucher["lines"],
                transfers=voucher["transfers"],
                officer=voucher["officer"],
                reviewer=voucher["reviewer"],
                year=voucher["year"],
                number=voucher["number"],
                created_at=voucher["created_at"],
                cancelled=voucher["cancelled"],
                cancelled_at=voucher["cancelled_at"],
            )
            created += 1
        except Exception:
            skipped += 1
            continue

    try:
        asset_rows = _sheet_rows(path, "ครุภัณฑ์")
        for item in parse_assets(asset_rows):
            store.add_asset(item)
    except Exception:
        pass

    year = max(years) if years else store.fiscal_year()
    try:
        budget_rows = _sheet_rows(path, "ประมาณการ")
        amounts, projects = parse_budget(budget_rows)
        if amounts:
            store.save_budget(year + 1, amounts, projects)
    except Exception:
        pass

    if years:
        store.save_settings({"fiscal_year": str(max(years))})

    return {
        "rv": len(rv),
        "pv": len(pv),
        "created": created,
        "skipped": skipped,
        "years": sorted(years),
    }


def ensure_seed_imported(store, path: str | Path | None = None, force: bool = False) -> dict | None:
    """Load AC25-209.xlsb into an empty database. Skip if vouchers already exist unless force."""
    source = Path(path) if path else SEED_XLSB
    if not source.exists():
        return None
    lock_path = Path(store.path).parent / ".chatriacc-seed.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not force and store.voucher_count() > 0:
            return None
        result = import_xlsb(store, source, replace=True)
        store.save_settings({"seed_imported": "1", "seed_file": source.name})
        return result


def main(argv: list[str] | None = None) -> int:
    from .db import Store

    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="นำเข้าไฟล์ AC25 .xlsb เข้าฐาน chatriACC")
    parser.add_argument("path", nargs="?", default=str(SEED_XLSB), help="ไฟล์ .xlsb")
    parser.add_argument(
        "--db",
        default=os.environ.get("CHATRIACC_DB", str(root / "data" / "chatriacc.db")),
    )
    parser.add_argument("--force", action="store_true", help="แทนที่ใบสำคัญปีเดียวกันแม้ฐานไม่ว่าง")
    args = parser.parse_args(argv)
    store = Store(args.db)
    result = ensure_seed_imported(store, args.path, force=args.force)
    if result is None:
        print(f"ข้าม: ฐาน {args.db} มีใบสำคัญอยู่แล้ว หรือไม่พบไฟล์ {args.path}")
        print(f"จำนวนใบสำคัญปัจจุบัน: {store.voucher_count()}")
        return 0
    print(
        f"นำเข้าแล้ว รับ {result['rv']} ใบ จ่าย {result['pv']} ใบ "
        f"บันทึก {result['created']} ข้าม {result['skipped']} ปี {result['years']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
