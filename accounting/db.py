"""SQLite persistence for payslips and ledger transactions."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    is_payslip INTEGER NOT NULL DEFAULT 0,
    UNIQUE (name, kind)
);

CREATE TABLE IF NOT EXISTS payslips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_date TEXT NOT NULL,
    period_month INTEGER NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    period_year INTEGER NOT NULL,
    employee_name TEXT NOT NULL,
    employee_id TEXT,
    company_name TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payslip_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payslip_id INTEGER NOT NULL REFERENCES payslips(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    category_id INTEGER REFERENCES categories(id),
    description TEXT NOT NULL,
    amount_satang INTEGER NOT NULL CHECK (amount_satang >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    category_id INTEGER REFERENCES categories(id),
    description TEXT NOT NULL,
    amount_satang INTEGER NOT NULL CHECK (amount_satang > 0),
    source TEXT NOT NULL CHECK (source IN ('payslip', 'manual')),
    payslip_id INTEGER REFERENCES payslips(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_transactions_kind ON transactions(kind);
CREATE INDEX IF NOT EXISTS idx_payslips_pay_date ON payslips(pay_date);
"""

DEFAULT_CATEGORIES = [
    ("เงินเดือน", "income", 1),
    ("ค่าล่วงเวลา", "income", 1),
    ("โบนัส", "income", 1),
    ("ค่าเบี้ยเลี้ยง", "income", 1),
    ("ค่าคอมมิชชั่น", "income", 1),
    ("เงินได้อื่นจากสลิป", "income", 1),
    ("รายได้อื่น", "income", 0),
    ("ภาษีหัก ณ ที่จ่าย", "expense", 1),
    ("ประกันสังคม", "expense", 1),
    ("กองทุนสำรองเลี้ยงชีพ", "expense", 1),
    ("ค่าสหกรณ์", "expense", 1),
    ("รายการหักอื่นจากสลิป", "expense", 1),
    ("ค่าอาหาร", "expense", 0),
    ("ค่าเดินทาง", "expense", 0),
    ("ค่าเช่า", "expense", 0),
    ("ค่าสาธารณูปโภค", "expense", 0),
    ("ค่าใช้จ่ายอื่น", "expense", 0),
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(conn: sqlite3.Connection | None = None) -> None:
    db = conn or get_db()
    db.executescript(SCHEMA)
    existing = {
        (row["name"], row["kind"])
        for row in db.execute("SELECT name, kind FROM categories")
    }
    for name, kind, is_payslip in DEFAULT_CATEGORIES:
        if (name, kind) not in existing:
            db.execute(
                "INSERT INTO categories (name, kind, is_payslip) VALUES (?, ?, ?)",
                (name, kind, is_payslip),
            )
    db.commit()


def categories(kind: str | None = None, payslip_only: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM categories WHERE 1=1"
    params: list[Any] = []
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if payslip_only:
        sql += " AND is_payslip = 1"
    sql += " ORDER BY is_payslip DESC, name"
    return list(get_db().execute(sql, params))


def get_or_create_category(name: str, kind: str, is_payslip: int = 0) -> int:
    name = name.strip()
    if not name:
        raise ValueError("กรุณาระบุหมวดหมู่")
    db = get_db()
    row = db.execute(
        "SELECT id FROM categories WHERE name = ? AND kind = ?",
        (name, kind),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = db.execute(
        "INSERT INTO categories (name, kind, is_payslip) VALUES (?, ?, ?)",
        (name, kind, is_payslip),
    )
    db.commit()
    return int(cur.lastrowid)


def fetch_payslip(payslip_id: int) -> dict[str, Any] | None:
    db = get_db()
    slip = db.execute("SELECT * FROM payslips WHERE id = ?", (payslip_id,)).fetchone()
    if slip is None:
        return None
    lines = db.execute(
        """
        SELECT l.*, c.name AS category_name
        FROM payslip_lines l
        LEFT JOIN categories c ON c.id = l.category_id
        WHERE l.payslip_id = ?
        ORDER BY l.kind, l.id
        """,
        (payslip_id,),
    ).fetchall()
    income = [dict(line) for line in lines if line["kind"] == "income"]
    expense = [dict(line) for line in lines if line["kind"] == "expense"]
    income_total = sum(line["amount_satang"] for line in income)
    expense_total = sum(line["amount_satang"] for line in expense)
    return {
        **dict(slip),
        "income_lines": income,
        "expense_lines": expense,
        "income_total": income_total,
        "expense_total": expense_total,
        "net": income_total - expense_total,
    }


def list_payslips() -> list[dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT
            p.*,
            COALESCE(SUM(CASE WHEN l.kind = 'income' THEN l.amount_satang ELSE 0 END), 0) AS income_total,
            COALESCE(SUM(CASE WHEN l.kind = 'expense' THEN l.amount_satang ELSE 0 END), 0) AS expense_total
        FROM payslips p
        LEFT JOIN payslip_lines l ON l.payslip_id = p.id
        GROUP BY p.id
        ORDER BY p.pay_date DESC, p.id DESC
        """
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["net"] = item["income_total"] - item["expense_total"]
        result.append(item)
    return result


def save_payslip(
    *,
    pay_date: str,
    period_month: int,
    period_year: int,
    employee_name: str,
    employee_id: str,
    company_name: str,
    notes: str,
    income_lines: list[dict[str, Any]],
    expense_lines: list[dict[str, Any]],
    payslip_id: int | None = None,
) -> int:
    if not employee_name.strip():
        raise ValueError("กรุณากรอกชื่อพนักงาน")
    if not pay_date:
        raise ValueError("กรุณาเลือกวันที่จ่าย")
    if not income_lines:
        raise ValueError("ต้องมีรายรับอย่างน้อย 1 รายการ")

    db = get_db()
    now = utcnow_iso()
    if payslip_id:
        existing = db.execute("SELECT id FROM payslips WHERE id = ?", (payslip_id,)).fetchone()
        if existing is None:
            raise ValueError("ไม่พบสลิปเงินเดือน")
        db.execute("DELETE FROM transactions WHERE payslip_id = ?", (payslip_id,))
        db.execute("DELETE FROM payslip_lines WHERE payslip_id = ?", (payslip_id,))
        db.execute(
            """
            UPDATE payslips
            SET pay_date = ?, period_month = ?, period_year = ?, employee_name = ?,
                employee_id = ?, company_name = ?, notes = ?
            WHERE id = ?
            """,
            (
                pay_date,
                period_month,
                period_year,
                employee_name.strip(),
                employee_id.strip() or None,
                company_name.strip() or None,
                notes.strip() or None,
                payslip_id,
            ),
        )
        slip_id = payslip_id
    else:
        cur = db.execute(
            """
            INSERT INTO payslips (
                pay_date, period_month, period_year, employee_name,
                employee_id, company_name, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pay_date,
                period_month,
                period_year,
                employee_name.strip(),
                employee_id.strip() or None,
                company_name.strip() or None,
                notes.strip() or None,
                now,
            ),
        )
        slip_id = int(cur.lastrowid)

    for kind, lines in (("income", income_lines), ("expense", expense_lines)):
        for line in lines:
            amount = int(line["amount_satang"])
            if amount <= 0:
                continue
            description = str(line["description"]).strip() or line.get("category_name") or "รายการ"
            category_id = line.get("category_id")
            db.execute(
                """
                INSERT INTO payslip_lines (
                    payslip_id, kind, category_id, description, amount_satang
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (slip_id, kind, category_id, description, amount),
            )
            db.execute(
                """
                INSERT INTO transactions (
                    txn_date, kind, category_id, description, amount_satang,
                    source, payslip_id, created_at
                ) VALUES (?, ?, ?, ?, ?, 'payslip', ?, ?)
                """,
                (pay_date, kind, category_id, description, amount, slip_id, now),
            )

    db.commit()
    return slip_id


def delete_payslip(payslip_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM payslips WHERE id = ?", (payslip_id,))
    db.commit()


def save_manual_transaction(
    *,
    txn_date: str,
    kind: str,
    category_id: int | None,
    description: str,
    amount_satang: int,
    txn_id: int | None = None,
) -> int:
    if kind not in ("income", "expense"):
        raise ValueError("ประเภทต้องเป็นรายรับหรือรายจ่าย")
    if amount_satang <= 0:
        raise ValueError("จำนวนเงินต้องมากกว่า 0")
    if not txn_date:
        raise ValueError("กรุณาเลือกวันที่")
    desc = description.strip()
    if not desc:
        raise ValueError("กรุณากรอกรายละเอียด")

    db = get_db()
    now = utcnow_iso()
    if txn_id:
        row = db.execute(
            "SELECT id, source FROM transactions WHERE id = ?", (txn_id,)
        ).fetchone()
        if row is None:
            raise ValueError("ไม่พบรายการ")
        if row["source"] != "manual":
            raise ValueError("รายการจากสลิปต้องแก้ไขที่หน้าสลิปเงินเดือน")
        db.execute(
            """
            UPDATE transactions
            SET txn_date = ?, kind = ?, category_id = ?, description = ?, amount_satang = ?
            WHERE id = ?
            """,
            (txn_date, kind, category_id, desc, amount_satang, txn_id),
        )
        db.commit()
        return txn_id

    cur = db.execute(
        """
        INSERT INTO transactions (
            txn_date, kind, category_id, description, amount_satang,
            source, payslip_id, created_at
        ) VALUES (?, ?, ?, ?, ?, 'manual', NULL, ?)
        """,
        (txn_date, kind, category_id, desc, amount_satang, now),
    )
    db.commit()
    return int(cur.lastrowid)


def delete_transaction(txn_id: int) -> None:
    db = get_db()
    row = db.execute("SELECT source FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    if row is None:
        raise ValueError("ไม่พบรายการ")
    if row["source"] != "manual":
        raise ValueError("รายการจากสลิปต้องลบที่หน้าสลิปเงินเดือน")
    db.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    db.commit()


def list_transactions(
    *,
    start: str | None = None,
    end: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT t.*, c.name AS category_name
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE 1=1
    """
    params: list[Any] = []
    if start:
        sql += " AND t.txn_date >= ?"
        params.append(start)
    if end:
        sql += " AND t.txn_date <= ?"
        params.append(end)
    if kind in ("income", "expense"):
        sql += " AND t.kind = ?"
        params.append(kind)
    sql += " ORDER BY t.txn_date DESC, t.id DESC"
    return [dict(row) for row in get_db().execute(sql, params)]


def get_transaction(txn_id: int) -> dict[str, Any] | None:
    row = get_db().execute(
        """
        SELECT t.*, c.name AS category_name
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.id = ?
        """,
        (txn_id,),
    ).fetchone()
    return dict(row) if row else None


def totals(
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, int]:
    sql = """
        SELECT
            COALESCE(SUM(CASE WHEN kind = 'income' THEN amount_satang ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount_satang ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE 1=1
    """
    params: list[Any] = []
    if start:
        sql += " AND txn_date >= ?"
        params.append(start)
    if end:
        sql += " AND txn_date <= ?"
        params.append(end)
    row = get_db().execute(sql, params).fetchone()
    income = int(row["income"])
    expense = int(row["expense"])
    return {"income": income, "expense": expense, "net": income - expense}


def daily_summary(year: int | None = None, month: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            txn_date AS period,
            COALESCE(SUM(CASE WHEN kind = 'income' THEN amount_satang ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount_satang ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE 1=1
    """
    params: list[Any] = []
    if year is not None:
        sql += " AND strftime('%Y', txn_date) = ?"
        params.append(f"{year:04d}")
    if month is not None:
        sql += " AND strftime('%m', txn_date) = ?"
        params.append(f"{month:02d}")
    sql += " GROUP BY txn_date ORDER BY txn_date DESC"
    rows = []
    for row in get_db().execute(sql, params):
        item = dict(row)
        item["net"] = item["income"] - item["expense"]
        rows.append(item)
    return rows


def monthly_summary(year: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            strftime('%Y-%m', txn_date) AS period,
            COALESCE(SUM(CASE WHEN kind = 'income' THEN amount_satang ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount_satang ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE 1=1
    """
    params: list[Any] = []
    if year is not None:
        sql += " AND strftime('%Y', txn_date) = ?"
        params.append(f"{year:04d}")
    sql += " GROUP BY strftime('%Y-%m', txn_date) ORDER BY period DESC"
    rows = []
    for row in get_db().execute(sql, params):
        item = dict(row)
        item["net"] = item["income"] - item["expense"]
        rows.append(item)
    return rows


def yearly_summary() -> list[dict[str, Any]]:
    rows = []
    for row in get_db().execute(
        """
        SELECT
            strftime('%Y', txn_date) AS period,
            COALESCE(SUM(CASE WHEN kind = 'income' THEN amount_satang ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN kind = 'expense' THEN amount_satang ELSE 0 END), 0) AS expense
        FROM transactions
        GROUP BY strftime('%Y', txn_date)
        ORDER BY period DESC
        """
    ):
        item = dict(row)
        item["net"] = item["income"] - item["expense"]
        rows.append(item)
    return rows


def category_breakdown(
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            t.kind,
            COALESCE(c.name, 'ไม่ระบุหมวด') AS category_name,
            COALESCE(SUM(t.amount_satang), 0) AS amount
        FROM transactions t
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE 1=1
    """
    params: list[Any] = []
    if start:
        sql += " AND t.txn_date >= ?"
        params.append(start)
    if end:
        sql += " AND t.txn_date <= ?"
        params.append(end)
    sql += " GROUP BY t.kind, COALESCE(c.name, 'ไม่ระบุหมวด') ORDER BY t.kind, amount DESC"
    return [dict(row) for row in get_db().execute(sql, params)]


def available_years() -> list[int]:
    rows = get_db().execute(
        """
        SELECT DISTINCT CAST(strftime('%Y', txn_date) AS INTEGER) AS year
        FROM transactions
        WHERE txn_date IS NOT NULL
        ORDER BY year DESC
        """
    ).fetchall()
    years = [int(row["year"]) for row in rows if row["year"] is not None]
    return years
