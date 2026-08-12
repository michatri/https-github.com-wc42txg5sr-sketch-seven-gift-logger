#!/usr/bin/env python3
"""Simple admin web: student list + attendance times."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, g, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "school.db"

app = Flask(__name__)
app.config["DB_PATH"] = Path(os.environ.get("SCHOOL_DB", DEFAULT_DB))


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = app.config["DB_PATH"]
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: object | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.route("/")
def attendance():
    q = (request.args.get("q") or "").strip()
    date = (request.args.get("date") or "").strip()

    sql = """
        SELECT
            a.id,
            a.check_in_at,
            s.student_code,
            s.name,
            s.finger_id
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE 1=1
    """
    params: list[object] = []

    if q:
        sql += " AND (s.student_code LIKE ? OR s.name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if date:
        sql += " AND date(a.check_in_at) = ?"
        params.append(date)

    sql += " ORDER BY a.check_in_at DESC, a.id DESC LIMIT 500"

    rows = get_db().execute(sql, params).fetchall()
    total_students = get_db().execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]
    total_today = get_db().execute(
        "SELECT COUNT(*) AS c FROM attendance WHERE date(check_in_at) = date('now','localtime')"
    ).fetchone()["c"]

    return render_template(
        "attendance.html",
        rows=rows,
        q=q,
        date=date,
        total_students=total_students,
        total_today=total_today,
    )


@app.route("/students")
def students():
    q = (request.args.get("q") or "").strip()
    sql = """
        SELECT
            s.id,
            s.student_code,
            s.name,
            s.finger_id,
            s.created_at,
            COUNT(a.id) AS checkin_count,
            MAX(a.check_in_at) AS last_check_in
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.id
        WHERE 1=1
    """
    params: list[object] = []
    if q:
        sql += " AND (s.student_code LIKE ? OR s.name LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " GROUP BY s.id ORDER BY s.student_code ASC"

    rows = get_db().execute(sql, params).fetchall()
    return render_template("students.html", rows=rows, q=q)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    print(f"DB: {app.config['DB_PATH']}")
    print(f"Open: http://{host}:{port}/")
    app.run(host=host, port=port, debug=False)
