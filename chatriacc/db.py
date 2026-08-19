"""SQLite persistence for chatriACC."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from . import chart
from .dates import iso_date, now_iso, parse_date, today

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vouchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('rv', 'pv')),
    number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    doc_date TEXT NOT NULL,
    officer TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    cancelled INTEGER NOT NULL DEFAULT 0,
    cancelled_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(kind, year, number)
);

CREATE TABLE IF NOT EXISTS voucher_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    txn_date TEXT NOT NULL,
    detail TEXT NOT NULL,
    amount_satang INTEGER NOT NULL,
    account_code INTEGER,
    bank_flag INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS voucher_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id INTEGER NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    number TEXT NOT NULL DEFAULT '',
    transfer_date TEXT,
    party TEXT NOT NULL DEFAULT '',
    amount_satang INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cash_holders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_satang INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    account_no TEXT NOT NULL DEFAULT '',
    branch TEXT NOT NULL DEFAULT '',
    amount_satang INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS balance_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section TEXT NOT NULL CHECK (section IN ('receivable', 'liability', 'equity')),
    name TEXT NOT NULL,
    amount_satang INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    txn_date TEXT NOT NULL,
    description TEXT NOT NULL,
    qty INTEGER,
    amount_satang INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS budget_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    account_code INTEGER NOT NULL,
    amount_satang INTEGER NOT NULL DEFAULT 0,
    UNIQUE(year, account_code)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL DEFAULT '',
    amount_satang INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_vouchers_kind_year ON vouchers(kind, year, number);
CREATE INDEX IF NOT EXISTS idx_lines_voucher ON voucher_lines(voucher_id);
CREATE INDEX IF NOT EXISTS idx_lines_date ON voucher_lines(txn_date);
CREATE INDEX IF NOT EXISTS idx_lines_code ON voucher_lines(account_code);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def tx(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init(self):
        with self.tx() as conn:
            conn.executescript(SCHEMA)
            self._seed(conn)

    def _seed(self, conn: sqlite3.Connection):
        existing = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        if existing == 0:
            conn.executemany(
                "INSERT INTO accounts(code, name, kind, sort_order) VALUES (?, ?, ?, ?)",
                chart.all_accounts(),
            )
        for key, value in chart.DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        if conn.execute("SELECT COUNT(*) FROM cash_holders").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO cash_holders(name, amount_satang, sort_order) VALUES (?, ?, ?)",
                [(n, a, i) for i, (n, a) in enumerate(chart.DEFAULT_CASH_HOLDERS)],
            )
        if conn.execute("SELECT COUNT(*) FROM bank_accounts").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO bank_accounts(bank_name, account_no, branch, amount_satang, sort_order) VALUES (?, ?, ?, ?, ?)",
                [
                    (b, no, br, amt, i)
                    for i, (b, no, br, amt) in enumerate(chart.DEFAULT_BANKS)
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM balance_lines").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO balance_lines(section, name, amount_satang, sort_order) VALUES (?, ?, ?, ?)",
                ("receivable", "ลูกหนี้ (เงินยืมวัด)", 0, 0),
            )
            conn.execute(
                "INSERT INTO balance_lines(section, name, amount_satang, sort_order) VALUES (?, ?, ?, ?)",
                ("equity", "รายรับ หัก รายจ่าย สะสม", 246504596, 0),
            )

    def setting(self, key: str, default: str = "") -> str:
        with self.tx() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def settings_map(self) -> dict[str, str]:
        with self.tx() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def save_settings(self, data: dict[str, str]):
        with self.tx() as conn:
            for key, value in data.items():
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )

    def fiscal_year(self) -> int:
        try:
            return int(self.setting("fiscal_year", str(today().year)))
        except ValueError:
            return today().year

    def accounts(self, kind: str | None = None) -> list[sqlite3.Row]:
        with self.tx() as conn:
            if kind:
                return conn.execute(
                    "SELECT * FROM accounts WHERE kind = ? ORDER BY sort_order, code",
                    (kind,),
                ).fetchall()
            return conn.execute("SELECT * FROM accounts ORDER BY kind, sort_order, code").fetchall()

    def account_map(self) -> dict[int, sqlite3.Row]:
        return {int(r["code"]): r for r in self.accounts()}

    def next_number(self, kind: str, year: int | None = None) -> int:
        year = year or self.fiscal_year()
        with self.tx() as conn:
            row = conn.execute(
                "SELECT MAX(number) AS n FROM vouchers WHERE kind = ? AND year = ?",
                (kind, year),
            ).fetchone()
        return int(row["n"] or 0) + 1

    def create_voucher(
        self,
        kind: str,
        lines: list[dict],
        transfers: list[dict] | None = None,
        officer: str = "",
        reviewer: str = "",
        year: int | None = None,
        number: int | None = None,
        created_at: str | None = None,
        cancelled: bool = False,
        cancelled_at: str | None = None,
    ) -> int:
        if kind not in ("rv", "pv"):
            raise ValueError("kind ต้องเป็น rv หรือ pv")
        clean = []
        for i, line in enumerate(lines, start=1):
            detail = (line.get("detail") or "").strip()
            amount = int(line.get("amount_satang") or 0)
            txn = iso_date(line.get("txn_date"))
            code = line.get("account_code")
            if not detail and not amount and not txn:
                continue
            if not detail or not txn or amount <= 0 or not code:
                raise ValueError(f"ลำดับ {i} ข้อมูลไม่ครบ (วันที่-รายการ-จำนวนเงิน-รหัส)")
            clean.append(
                {
                    "line_no": i,
                    "txn_date": txn,
                    "detail": detail,
                    "amount_satang": amount,
                    "account_code": int(code),
                    "bank_flag": 1 if line.get("bank_flag") else 0,
                }
            )
        if not clean:
            raise ValueError("กรุณาใส่ข้อมูล ( วันที่-รายการ-เช็ค/โอน-จำนวนเงิน-รหัส )")
        if len(clean) > 7:
            raise ValueError("ใบสำคัญได้ไม่เกิน 7 รายการ")
        year = year or parse_date(clean[0]["txn_date"]).year
        settings = self.settings_map()
        officer = officer or settings.get("officer", "")
        reviewer = reviewer or settings.get("parish_priest", "")
        with self.tx() as conn:
            if number is None:
                row = conn.execute(
                    "SELECT MAX(number) AS n FROM vouchers WHERE kind = ? AND year = ?",
                    (kind, year),
                ).fetchone()
                number = int(row["n"] or 0) + 1
            cur = conn.execute(
                """
                INSERT INTO vouchers(kind, number, year, doc_date, officer, reviewer, cancelled, cancelled_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kind,
                    number,
                    year,
                    clean[0]["txn_date"],
                    officer,
                    reviewer,
                    1 if cancelled else 0,
                    cancelled_at,
                    created_at or now_iso(),
                ),
            )
            voucher_id = int(cur.lastrowid)
            conn.executemany(
                """
                INSERT INTO voucher_lines(voucher_id, line_no, txn_date, detail, amount_satang, account_code, bank_flag)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        voucher_id,
                        ln["line_no"],
                        ln["txn_date"],
                        ln["detail"],
                        ln["amount_satang"],
                        ln["account_code"],
                        ln["bank_flag"],
                    )
                    for ln in clean
                ],
            )
            for seq, tr in enumerate(transfers or [], start=1):
                if seq > 3:
                    break
                amt = int(tr.get("amount_satang") or 0)
                num = str(tr.get("number") or "").strip()
                party = str(tr.get("party") or "").strip()
                tdate = iso_date(tr.get("transfer_date")) or None
                if not (num or party or amt or tdate):
                    continue
                conn.execute(
                    """
                    INSERT INTO voucher_transfers(voucher_id, seq, number, transfer_date, party, amount_satang)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (voucher_id, seq, num, tdate, party, amt),
                )
        return voucher_id

    def get_voucher(self, voucher_id: int) -> dict | None:
        with self.tx() as conn:
            row = conn.execute("SELECT * FROM vouchers WHERE id = ?", (voucher_id,)).fetchone()
            if not row:
                return None
            lines = conn.execute(
                """
                SELECT l.*, a.name AS account_name
                FROM voucher_lines l
                LEFT JOIN accounts a ON a.code = l.account_code
                WHERE l.voucher_id = ?
                ORDER BY l.line_no
                """,
                (voucher_id,),
            ).fetchall()
            transfers = conn.execute(
                "SELECT * FROM voucher_transfers WHERE voucher_id = ? ORDER BY seq",
                (voucher_id,),
            ).fetchall()
        return {
            "voucher": row,
            "lines": lines,
            "transfers": transfers,
            "total": sum(int(l["amount_satang"]) for l in lines),
        }

    def find_voucher(self, kind: str, number: int, year: int | None = None) -> dict | None:
        year = year or self.fiscal_year()
        with self.tx() as conn:
            row = conn.execute(
                "SELECT id FROM vouchers WHERE kind = ? AND number = ? AND year = ?",
                (kind, number, year),
            ).fetchone()
        return self.get_voucher(row["id"]) if row else None

    def list_vouchers(
        self,
        kind: str | None = None,
        year: int | None = None,
        month: int | None = None,
        include_cancelled: bool = True,
        limit: int = 200,
    ) -> list[dict]:
        year = year or self.fiscal_year()
        sql = [
            "SELECT v.*, COALESCE(SUM(l.amount_satang), 0) AS total, COUNT(l.id) AS line_count",
            "FROM vouchers v LEFT JOIN voucher_lines l ON l.voucher_id = v.id",
            "WHERE v.year = ?",
        ]
        params: list = [year]
        if kind:
            sql.append("AND v.kind = ?")
            params.append(kind)
        if not include_cancelled:
            sql.append("AND v.cancelled = 0")
        if month:
            sql.append("AND strftime('%m', v.doc_date) = ?")
            params.append(f"{int(month):02d}")
        sql.append("GROUP BY v.id ORDER BY v.number DESC LIMIT ?")
        params.append(limit)
        with self.tx() as conn:
            return conn.execute(" ".join(sql), params).fetchall()

    def cancel_voucher(self, voucher_id: int) -> None:
        data = self.get_voucher(voucher_id)
        if not data:
            raise ValueError("ไม่พบใบสำคัญ")
        if data["voucher"]["cancelled"]:
            raise ValueError("ใบสำคัญนี้ ถูกยกเลิกแล้ว")
        with self.tx() as conn:
            conn.execute(
                "UPDATE vouchers SET cancelled = 1, cancelled_at = ? WHERE id = ?",
                (now_iso(), voucher_id),
            )

    def ledger(
        self,
        kind: str,
        year: int | None = None,
        month: int | None = None,
        include_cancelled: bool = False,
    ) -> list[sqlite3.Row]:
        year = year or self.fiscal_year()
        sql = """
            SELECT l.*, v.number, v.kind, v.cancelled, a.name AS account_name
            FROM voucher_lines l
            JOIN vouchers v ON v.id = l.voucher_id
            LEFT JOIN accounts a ON a.code = l.account_code
            WHERE v.kind = ? AND v.year = ?
        """
        params: list = [kind, year]
        if not include_cancelled:
            sql += " AND v.cancelled = 0"
        if month:
            sql += " AND strftime('%m', l.txn_date) = ?"
            params.append(f"{int(month):02d}")
        sql += " ORDER BY l.txn_date, v.number, l.line_no"
        with self.tx() as conn:
            return conn.execute(sql, params).fetchall()

    def account_code_report(
        self,
        year: int | None = None,
        month: int | None = None,
        codes: list[int] | None = None,
        kind: str | None = None,
        include_cancelled: bool = False,
    ) -> dict:
        year = year or self.fiscal_year()
        wanted = sorted({int(c) for c in (codes or []) if c not in (None, "")})
        sql = """
            SELECT l.*, v.number, v.kind, v.cancelled, a.name AS account_name, a.kind AS account_kind
            FROM voucher_lines l
            JOIN vouchers v ON v.id = l.voucher_id
            LEFT JOIN accounts a ON a.code = l.account_code
            WHERE v.year = ?
        """
        params: list = [year]
        if not include_cancelled:
            sql += " AND v.cancelled = 0"
        if kind in ("rv", "pv"):
            sql += " AND v.kind = ?"
            params.append(kind)
        if month:
            sql += " AND strftime('%m', l.txn_date) = ?"
            params.append(f"{int(month):02d}")
        if wanted:
            placeholders = ",".join("?" * len(wanted))
            sql += f" AND l.account_code IN ({placeholders})"
            params.extend(wanted)
        sql += " ORDER BY l.account_code, l.txn_date, v.kind, v.number, l.line_no"
        with self.tx() as conn:
            rows = conn.execute(sql, params).fetchall()
        names = {int(a["code"]): a for a in self.accounts()}
        grouped: dict[int, list] = defaultdict(list)
        for row in rows:
            grouped[int(row["account_code"] or 0)].append(row)
        if wanted:
            ordered_codes = wanted
        else:
            ordered_codes = sorted(grouped)
        groups = []
        income_total = 0
        expense_total = 0
        for code in ordered_codes:
            acc = names.get(code)
            items = grouped.get(code, [])
            total = sum(int(r["amount_satang"]) for r in items)
            acc_kind = (acc["kind"] if acc else None) or (items[0]["kind"] if items else "")
            if acc_kind in ("income", "rv") or (items and items[0]["kind"] == "rv"):
                income_total += total
                display_kind = "income"
            else:
                expense_total += total
                display_kind = "expense"
            groups.append(
                {
                    "code": code,
                    "name": acc["name"] if acc else "",
                    "kind": display_kind,
                    "rows": items,
                    "total": total,
                    "count": len(items),
                }
            )
        return {
            "year": year,
            "month": month,
            "kind": kind,
            "codes": wanted,
            "groups": groups,
            "income_total": income_total,
            "expense_total": expense_total,
            "grand_total": income_total + expense_total,
            "net": income_total - expense_total,
            "grand_count": sum(g["count"] for g in groups),
        }

    def year_totals(self, year: int | None = None) -> dict:
        year = year or self.fiscal_year()
        with self.tx() as conn:
            rows = conn.execute(
                """
                SELECT v.kind, strftime('%m', l.txn_date) AS month, l.account_code,
                       SUM(l.amount_satang) AS total
                FROM voucher_lines l
                JOIN vouchers v ON v.id = l.voucher_id
                WHERE v.year = ? AND v.cancelled = 0
                GROUP BY v.kind, month, l.account_code
                """,
                (year,),
            ).fetchall()
        income = defaultdict(lambda: defaultdict(int))
        expense = defaultdict(lambda: defaultdict(int))
        month_income = [0] * 13
        month_expense = [0] * 13
        for row in rows:
            m = int(row["month"] or 0)
            code = int(row["account_code"] or 0)
            amt = int(row["total"] or 0)
            if row["kind"] == "rv":
                income[code][m] += amt
                month_income[m] += amt
            else:
                expense[code][m] += amt
                month_expense[m] += amt
        return {
            "year": year,
            "income": income,
            "expense": expense,
            "month_income": month_income,
            "month_expense": month_expense,
            "income_total": sum(month_income),
            "expense_total": sum(month_expense),
            "net": sum(month_income) - sum(month_expense),
        }

    def dashboard(self, year: int | None = None) -> dict:
        year = year or self.fiscal_year()
        totals = self.year_totals(year)
        m = today().month if today().year == year else 12
        with self.tx() as conn:
            recent = conn.execute(
                """
                SELECT v.*, COALESCE(SUM(l.amount_satang), 0) AS total
                FROM vouchers v LEFT JOIN voucher_lines l ON l.voucher_id = v.id
                WHERE v.year = ?
                GROUP BY v.id
                ORDER BY v.created_at DESC, v.id DESC
                LIMIT 8
                """,
                (year,),
            ).fetchall()
            counts = conn.execute(
                """
                SELECT kind, COUNT(*) AS n
                FROM vouchers WHERE year = ? AND cancelled = 0
                GROUP BY kind
                """,
                (year,),
            ).fetchall()
        count_map = {r["kind"]: r["n"] for r in counts}
        return {
            **totals,
            "month": m,
            "month_income_now": totals["month_income"][m],
            "month_expense_now": totals["month_expense"][m],
            "recent": recent,
            "rv_count": count_map.get("rv", 0),
            "pv_count": count_map.get("pv", 0),
            "next_rv": self.next_number("rv", year),
            "next_pv": self.next_number("pv", year),
        }

    def cash_holders(self):
        with self.tx() as conn:
            return conn.execute("SELECT * FROM cash_holders ORDER BY sort_order, id").fetchall()

    def bank_accounts(self):
        with self.tx() as conn:
            return conn.execute("SELECT * FROM bank_accounts ORDER BY sort_order, id").fetchall()

    def save_cash_holders(self, rows: list[dict]):
        with self.tx() as conn:
            conn.execute("DELETE FROM cash_holders")
            conn.executemany(
                "INSERT INTO cash_holders(name, amount_satang, sort_order) VALUES (?, ?, ?)",
                [
                    (r["name"].strip(), int(r.get("amount_satang") or 0), i)
                    for i, r in enumerate(rows)
                    if (r.get("name") or "").strip()
                ],
            )

    def save_banks(self, rows: list[dict]):
        with self.tx() as conn:
            conn.execute("DELETE FROM bank_accounts")
            conn.executemany(
                "INSERT INTO bank_accounts(bank_name, account_no, branch, amount_satang, sort_order) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        r["bank_name"].strip(),
                        (r.get("account_no") or "").strip(),
                        (r.get("branch") or "").strip(),
                        int(r.get("amount_satang") or 0),
                        i,
                    )
                    for i, r in enumerate(rows)
                    if (r.get("bank_name") or "").strip()
                ],
            )

    def balance_sheet(self, year: int | None = None) -> dict:
        year = year or self.fiscal_year()
        cash = self.cash_holders()
        banks = self.bank_accounts()
        with self.tx() as conn:
            extras = conn.execute(
                "SELECT * FROM balance_lines ORDER BY section, sort_order, id"
            ).fetchall()
        cash_total = sum(int(r["amount_satang"]) for r in cash)
        bank_total = sum(int(r["amount_satang"]) for r in banks)
        recv = [r for r in extras if r["section"] == "receivable"]
        liab = [r for r in extras if r["section"] == "liability"]
        equity = [r for r in extras if r["section"] == "equity"]
        recv_total = sum(int(r["amount_satang"]) for r in recv)
        liab_total = sum(int(r["amount_satang"]) for r in liab)
        equity_total = sum(int(r["amount_satang"]) for r in equity)
        assets_total = cash_total + bank_total + recv_total
        return {
            "year": year,
            "cash": cash,
            "banks": banks,
            "receivables": recv,
            "liabilities": liab,
            "equity": equity,
            "cash_total": cash_total,
            "bank_total": bank_total,
            "recv_total": recv_total,
            "liab_total": liab_total,
            "equity_total": equity_total,
            "assets_total": assets_total,
            "liab_equity_total": liab_total + equity_total,
        }

    def assets(self, direction: str | None = None):
        with self.tx() as conn:
            if direction:
                return conn.execute(
                    "SELECT * FROM assets WHERE direction = ? ORDER BY txn_date, id",
                    (direction,),
                ).fetchall()
            return conn.execute("SELECT * FROM assets ORDER BY txn_date, id").fetchall()

    def add_asset(self, data: dict) -> int:
        with self.tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO assets(direction, txn_date, description, qty, amount_satang, location, code, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["direction"],
                    iso_date(data["txn_date"]),
                    data["description"].strip(),
                    data.get("qty") or None,
                    int(data.get("amount_satang") or 0),
                    (data.get("location") or "").strip(),
                    (data.get("code") or "").strip(),
                    (data.get("reason") or "").strip(),
                ),
            )
            return int(cur.lastrowid)

    def delete_asset(self, asset_id: int):
        with self.tx() as conn:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))

    def budget(self, year: int | None = None):
        year = year or (self.fiscal_year() + 1)
        with self.tx() as conn:
            lines = conn.execute(
                """
                SELECT b.*, a.name, a.kind
                FROM budget_lines b JOIN accounts a ON a.code = b.account_code
                WHERE b.year = ?
                ORDER BY a.kind, a.sort_order
                """,
                (year,),
            ).fetchall()
            projects = conn.execute(
                "SELECT * FROM projects WHERE year = ? ORDER BY seq",
                (year,),
            ).fetchall()
        income = [r for r in lines if r["kind"] == "income"]
        expense = [r for r in lines if r["kind"] == "expense"]
        return {
            "year": year,
            "income": income,
            "expense": expense,
            "projects": projects,
            "income_total": sum(int(r["amount_satang"]) for r in income),
            "expense_total": sum(int(r["amount_satang"]) for r in expense),
        }

    def save_budget(self, year: int, amounts: dict[int, int], projects: list[dict]):
        with self.tx() as conn:
            for code, amt in amounts.items():
                conn.execute(
                    """
                    INSERT INTO budget_lines(year, account_code, amount_satang)
                    VALUES (?, ?, ?)
                    ON CONFLICT(year, account_code) DO UPDATE SET amount_satang = excluded.amount_satang
                    """,
                    (year, int(code), int(amt)),
                )
            conn.execute("DELETE FROM projects WHERE year = ?", (year,))
            conn.executemany(
                "INSERT INTO projects(year, seq, name, period, amount_satang) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        year,
                        i + 1,
                        (p.get("name") or "").strip(),
                        (p.get("period") or "").strip(),
                        int(p.get("amount_satang") or 0),
                    )
                    for i, p in enumerate(projects)
                    if (p.get("name") or "").strip() or int(p.get("amount_satang") or 0)
                ],
            )

    def clear_year_data(self, year: int):
        with self.tx() as conn:
            ids = [
                r["id"]
                for r in conn.execute("SELECT id FROM vouchers WHERE year = ?", (year,)).fetchall()
            ]
            if ids:
                q = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM voucher_lines WHERE voucher_id IN ({q})", ids)
                conn.execute(f"DELETE FROM voucher_transfers WHERE voucher_id IN ({q})", ids)
                conn.execute("DELETE FROM vouchers WHERE year = ?", (year,))
            conn.execute("DELETE FROM assets")
            conn.execute("DELETE FROM budget_lines WHERE year = ?", (year,))
            conn.execute("DELETE FROM projects WHERE year = ?", (year,))

    def voucher_count(self) -> int:
        with self.tx() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM vouchers").fetchone()[0])
