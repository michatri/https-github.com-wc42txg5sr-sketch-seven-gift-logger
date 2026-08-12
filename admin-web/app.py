#!/usr/bin/env python3
"""Simple admin web: register students, list, attendance times."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "school.db"

app = Flask(__name__)
app.config["DB_PATH"] = Path(os.environ.get("SCHOOL_DB", DEFAULT_DB))
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "school-checkin-dev")
app.config["FINGERPRINT_PORT"] = os.environ.get("FINGERPRINT_PORT", "/dev/serial0")
app.config["FINGERPRINT_BAUD"] = int(os.environ.get("FINGERPRINT_BAUD", "57600"))


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = app.config["DB_PATH"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
        ensure_schema(conn)
    return g.db


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_code TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL,
          first_name TEXT NOT NULL DEFAULT '',
          last_name TEXT NOT NULL DEFAULT '',
          finger_id INTEGER UNIQUE NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS attendance (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL,
          check_in_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          FOREIGN KEY(student_id) REFERENCES students(id)
        );
        """
    )
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
    if "first_name" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
    if "last_name" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
    # Backfill from old single name field
    conn.execute(
        """
        UPDATE students
        SET first_name = CASE
              WHEN first_name = '' AND instr(name, ' ') > 0
                THEN substr(name, 1, instr(name, ' ') - 1)
              WHEN first_name = '' THEN name
              ELSE first_name
            END,
            last_name = CASE
              WHEN last_name = '' AND instr(name, ' ') > 0
                THEN substr(name, instr(name, ' ') + 1)
              ELSE last_name
            END
        WHERE first_name = '' OR last_name = ''
        """
    )
    conn.commit()


@app.teardown_appcontext
def close_db(_: object | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def full_name(first_name: str, last_name: str) -> str:
    return f"{first_name} {last_name}".strip()


def open_sensor():
    try:
        from pyfingerprint.pyfingerprint import PyFingerprint
    except ImportError as exc:
        raise RuntimeError("ยังไม่ได้ติดตั้ง pyfingerprint (pip install pyfingerprint)") from exc

    sensor = PyFingerprint(
        app.config["FINGERPRINT_PORT"],
        app.config["FINGERPRINT_BAUD"],
        0xFFFFFFFF,
        0x00000000,
    )
    if not sensor.verifyPassword():
        raise RuntimeError("เซนเซอร์ลายนิ้วมือไม่พร้อมใช้งาน")
    return sensor


def wait_for_finger(sensor, timeout_sec: int = 30) -> None:
    started = time.time()
    while not sensor.readImage():
        if time.time() - started > timeout_sec:
            raise TimeoutError("หมดเวลารอวางนิ้ว")
        time.sleep(0.15)


def wait_for_finger_removed(sensor, timeout_sec: int = 20) -> None:
    started = time.time()
    while sensor.readImage():
        if time.time() - started > timeout_sec:
            break
        time.sleep(0.15)


def enroll_fingerprint() -> int:
    sensor = open_sensor()

    wait_for_finger(sensor)
    sensor.convertImage(0x01)
    position, _score = sensor.searchTemplate()
    if position >= 0:
        raise RuntimeError(f"ลายนิ้วมือนี้อยู่ในระบบแล้ว (นิ้ว #{position})")

    wait_for_finger_removed(sensor)
    time.sleep(0.5)
    wait_for_finger(sensor)
    sensor.convertImage(0x02)

    if sensor.compareCharacteristics() == 0:
        raise RuntimeError("ลายนิ้วมือสองครั้งไม่ตรงกัน กรุณาลองใหม่")

    sensor.createTemplate()
    return int(sensor.storeTemplate())


@app.route("/")
def attendance():
    q = (request.args.get("q") or "").strip()
    date = (request.args.get("date") or "").strip()

    sql = """
        SELECT
            a.id,
            a.check_in_at,
            s.student_code,
            s.first_name,
            s.last_name,
            s.name,
            s.finger_id
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE 1=1
    """
    params: list[object] = []

    if q:
        sql += """
            AND (
              s.student_code LIKE ?
              OR s.name LIKE ?
              OR s.first_name LIKE ?
              OR s.last_name LIKE ?
            )
        """
        like = f"%{q}%"
        params.extend([like, like, like, like])
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
            s.first_name,
            s.last_name,
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
        sql += """
            AND (
              s.student_code LIKE ?
              OR s.name LIKE ?
              OR s.first_name LIKE ?
              OR s.last_name LIKE ?
            )
        """
        like = f"%{q}%"
        params.extend([like, like, like, like])
    sql += " GROUP BY s.id ORDER BY s.student_code ASC"

    rows = get_db().execute(sql, params).fetchall()
    return render_template("students.html", rows=rows, q=q)


def get_student_or_404(student_id: int):
    row = get_db().execute(
        """
        SELECT id, student_code, first_name, last_name, name, finger_id, created_at
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()
    if not row:
        return None
    return row


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id: int):
    student = get_student_or_404(student_id)
    if student is None:
        flash("ไม่พบนักเรียน", "error")
        return redirect(url_for("students"))

    form = {
        "student_code": student["student_code"],
        "first_name": student["first_name"] or student["name"],
        "last_name": student["last_name"] or "",
    }

    if request.method == "POST":
        form["student_code"] = (request.form.get("student_code") or "").strip()
        form["first_name"] = (request.form.get("first_name") or "").strip()
        form["last_name"] = (request.form.get("last_name") or "").strip()

        if not form["student_code"] or not form["first_name"] or not form["last_name"]:
            flash("กรุณากรอกรหัส ชื่อ และนามสกุลให้ครบ", "error")
            return render_template("edit_student.html", form=form, student=student), 400

        db = get_db()
        duplicate = db.execute(
            """
            SELECT id FROM students
            WHERE student_code = ? AND id != ?
            """,
            (form["student_code"], student_id),
        ).fetchone()
        if duplicate:
            flash("รหัสนักเรียนนี้มีอยู่แล้ว", "error")
            return render_template("edit_student.html", form=form, student=student), 400

        display_name = full_name(form["first_name"], form["last_name"])
        db.execute(
            """
            UPDATE students
            SET student_code = ?, name = ?, first_name = ?, last_name = ?
            WHERE id = ?
            """,
            (
                form["student_code"],
                display_name,
                form["first_name"],
                form["last_name"],
                student_id,
            ),
        )
        db.commit()
        flash(f"บันทึกแล้ว: {form['student_code']} {display_name}", "ok")
        return redirect(url_for("students"))

    return render_template("edit_student.html", form=form, student=student)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = {
        "student_code": "",
        "first_name": "",
        "last_name": "",
    }

    if request.method == "POST":
        form["student_code"] = (request.form.get("student_code") or "").strip()
        form["first_name"] = (request.form.get("first_name") or "").strip()
        form["last_name"] = (request.form.get("last_name") or "").strip()

        if not form["student_code"] or not form["first_name"] or not form["last_name"]:
            flash("กรุณากรอกรหัส ชื่อ และนามสกุลให้ครบ", "error")
            return render_template("register.html", form=form), 400

        db = get_db()
        exists = db.execute(
            "SELECT id FROM students WHERE student_code = ?",
            (form["student_code"],),
        ).fetchone()
        if exists:
            flash("รหัสนักเรียนนี้มีอยู่แล้ว", "error")
            return render_template("register.html", form=form), 400

        try:
            finger_id = enroll_fingerprint()
            display_name = full_name(form["first_name"], form["last_name"])
            db.execute(
                """
                INSERT INTO students(student_code, name, first_name, last_name, finger_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    form["student_code"],
                    display_name,
                    form["first_name"],
                    form["last_name"],
                    finger_id,
                ),
            )
            db.commit()
        except Exception as exc:
            flash(f"ลงทะเบียนไม่สำเร็จ: {exc}", "error")
            return render_template("register.html", form=form), 400

        flash(
            f"ลงทะเบียนสำเร็จ: {form['student_code']} {display_name} (นิ้ว #{finger_id})",
            "ok",
        )
        return redirect(url_for("students"))

    return render_template("register.html", form=form)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    print(f"DB: {app.config['DB_PATH']}")
    print(f"Sensor: {app.config['FINGERPRINT_PORT']} @ {app.config['FINGERPRINT_BAUD']}")
    print(f"Open: http://{host}:{port}/")
    app.run(host=host, port=port, debug=False)
