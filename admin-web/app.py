#!/usr/bin/env python3
"""Simple admin web: register students, list, attendance times."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "school.db"
_SENSOR_LOCK = threading.Lock()

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
          finger_id INTEGER UNIQUE,
          finger_left_id INTEGER UNIQUE,
          finger_right_id INTEGER UNIQUE,
          balance INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS attendance (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL,
          check_in_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          check_out_at TEXT,
          matched_hand TEXT,
          matched_finger_id INTEGER,
          check_out_hand TEXT,
          check_out_finger_id INTEGER,
          FOREIGN KEY(student_id) REFERENCES students(id)
        );
        CREATE TABLE IF NOT EXISTS topups (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL,
          amount INTEGER NOT NULL,
          balance_after INTEGER NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          FOREIGN KEY(student_id) REFERENCES students(id)
        );
        CREATE TABLE IF NOT EXISTS shops (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS purchases (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL,
          shop_id INTEGER NOT NULL,
          amount INTEGER NOT NULL,
          balance_after INTEGER NOT NULL,
          matched_hand TEXT,
          matched_finger_id INTEGER,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          FOREIGN KEY(student_id) REFERENCES students(id),
          FOREIGN KEY(shop_id) REFERENCES shops(id)
        );
        """
    )
    student_cols = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
    attendance_cols = {row["name"] for row in conn.execute("PRAGMA table_info(attendance)")}

    if "first_name" not in student_cols:
        conn.execute("ALTER TABLE students ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
    if "last_name" not in student_cols:
        conn.execute("ALTER TABLE students ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
    if "finger_left_id" not in student_cols:
        conn.execute("ALTER TABLE students ADD COLUMN finger_left_id INTEGER")
    if "finger_right_id" not in student_cols:
        conn.execute("ALTER TABLE students ADD COLUMN finger_right_id INTEGER")
    if "balance" not in student_cols:
        conn.execute("ALTER TABLE students ADD COLUMN balance INTEGER NOT NULL DEFAULT 0")
    if "matched_hand" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN matched_hand TEXT")
    if "matched_finger_id" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN matched_finger_id INTEGER")
    if "check_out_at" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN check_out_at TEXT")
    if "check_out_hand" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN check_out_hand TEXT")
    if "check_out_finger_id" not in attendance_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN check_out_finger_id INTEGER")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_finger_left ON students(finger_left_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_finger_right ON students(finger_right_id)"
    )

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
    # Old single finger_id becomes right-hand finger by default
    conn.execute(
        """
        UPDATE students
        SET finger_right_id = finger_id
        WHERE finger_right_id IS NULL AND finger_id IS NOT NULL
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


def close_sensor(sensor) -> None:
    if sensor is None:
        return
    for attr in ("_ser", "ser", "_serial"):
        ser = getattr(sensor, attr, None)
        if ser is None:
            continue
        try:
            ser.close()
        except Exception:
            pass
        break
    # Give the kernel a moment before the next open
    time.sleep(0.35)


def open_sensor():
    try:
        from pyfingerprint.pyfingerprint import PyFingerprint
    except ImportError as exc:
        raise RuntimeError("ยังไม่ได้ติดตั้ง pyfingerprint (pip install pyfingerprint)") from exc

    port = app.config["FINGERPRINT_PORT"]
    baud = app.config["FINGERPRINT_BAUD"]
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            sensor = PyFingerprint(port, baud, 0xFFFFFFFF, 0x00000000)
            if not sensor.verifyPassword():
                close_sensor(sensor)
                raise RuntimeError("เซนเซอร์ลายนิ้วมือไม่พร้อมใช้งาน")
            return sensor
        except Exception as exc:
            last_error = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"เปิดเซนเซอร์ไม่สำเร็จ: {last_error}")


@contextmanager
def sensor_session():
    """Ensure only one request talks to the R307 at a time."""
    acquired = _SENSOR_LOCK.acquire(timeout=50)
    if not acquired:
        raise RuntimeError(
            "เซนเซอร์กำลังถูกใช้อยู่ กรุณารอสักครู่ "
            "(เปิดหน้าเช็คเข้าและเช็คออกพร้อมกันได้เพียงหน้าเดียว)"
        )
    sensor = None
    try:
        sensor = open_sensor()
        yield sensor
    finally:
        close_sensor(sensor)
        _SENSOR_LOCK.release()


def wait_for_finger(sensor, timeout_sec: int = 40) -> None:
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


def enroll_fingerprint(
    sensor=None,
    hand_label: str = "นิ้ว",
    exclude_positions: set[int] | None = None,
) -> tuple[object, int]:
    if sensor is None:
        with sensor_session() as owned:
            return enroll_fingerprint(owned, hand_label, exclude_positions)

    exclude = {int(p) for p in (exclude_positions or set())}

    for _attempt in range(3):
        wait_for_finger(sensor)
        sensor.convertImage(0x01)
        position, _score = sensor.searchTemplate()

        if position >= 0:
            if int(position) in exclude:
                raise RuntimeError(
                    f"{hand_label}: นิ้วนี้เพิ่งสแกนไปแล้ว "
                    "กรุณาใช้คนละนิ้ว (มือซ้าย 1 นิ้ว / มือขวา 1 นิ้ว)"
                )

            owner = find_student_by_finger(get_db(), int(position))
            if owner is None:
                # Orphan template left on sensor from old tests/deletes
                delete_template(sensor, int(position), strict=False)
                wait_for_finger_removed(sensor)
                time.sleep(0.4)
                continue

            owner_name = full_name(
                owner["first_name"] or owner["name"],
                owner["last_name"] or "",
            )
            raise RuntimeError(
                f"{hand_label}: นิ้วนี้เป็นของ {owner['student_code']} {owner_name} "
                f"อยู่แล้ว (นิ้ว #{position})"
            )

        wait_for_finger_removed(sensor)
        time.sleep(0.5)
        wait_for_finger(sensor)
        sensor.convertImage(0x02)

        if sensor.compareCharacteristics() == 0:
            raise RuntimeError(f"{hand_label}: ลายนิ้วมือสองครั้งไม่ตรงกัน กรุณาลองใหม่")

        sensor.createTemplate()
        return sensor, int(sensor.storeTemplate())

    raise RuntimeError(
        f"{hand_label}: พบนิ้วค้างในเซนเซอร์และลบให้แล้ว แต่ยังลงทะเบียนไม่สำเร็จ ลองใหม่"
    )


def delete_template(sensor, position: int | None, *, strict: bool = False) -> None:
    if sensor is None or position is None:
        return
    last_error: Exception | None = None
    for _ in range(3):
        try:
            sensor.deleteTemplate(int(position))
            return
        except Exception as exc:
            msg = str(exc).lower()
            # Slot already empty counts as successfully removed
            if any(
                token in msg
                for token in (
                    "not found",
                    "no template",
                    "does not exist",
                    "invalid",
                    "empty",
                    "bad location",
                    "pageid",
                )
            ):
                return
            last_error = exc
            time.sleep(0.2)
    if strict:
        raise RuntimeError(f"ลบลายนิ้วมือ #{position} จากเซนเซอร์ไม่สำเร็จ: {last_error}")


def purge_student_fingerprints(student) -> list[int]:
    """Delete every fingerprint template for this student from the sensor."""
    positions = sorted(
        {
            int(p)
            for p in (
                student["finger_left_id"],
                student["finger_right_id"],
                student["finger_id"],
            )
            if p is not None
        }
    )
    if not positions:
        return []

    deleted: list[int] = []
    with sensor_session() as sensor:
        for pos in positions:
            delete_template(sensor, pos, strict=True)
            deleted.append(pos)
    return deleted


def find_student_by_finger(db: sqlite3.Connection, finger_pos: int):
    return db.execute(
        """
        SELECT id, student_code, first_name, last_name, name,
               finger_id, finger_left_id, finger_right_id
        FROM students
        WHERE finger_left_id = ?
           OR finger_right_id = ?
           OR finger_id = ?
        """,
        (finger_pos, finger_pos, finger_pos),
    ).fetchone()


def matched_hand_for(student, finger_pos: int) -> str:
    if student["finger_left_id"] == finger_pos:
        return "left"
    if student["finger_right_id"] == finger_pos:
        return "right"
    if student["finger_id"] == finger_pos:
        return "right"
    return "unknown"


@app.route("/")
def attendance():
    q = (request.args.get("q") or "").strip()
    date = (request.args.get("date") or "").strip()

    sql = """
        SELECT
            a.id,
            a.check_in_at,
            a.check_out_at,
            a.matched_hand,
            a.matched_finger_id,
            a.check_out_hand,
            a.check_out_finger_id,
            s.student_code,
            s.first_name,
            s.last_name,
            s.name,
            s.finger_left_id,
            s.finger_right_id,
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
    total_out_today = get_db().execute(
        """
        SELECT COUNT(*) AS c FROM attendance
        WHERE date(check_in_at) = date('now','localtime')
          AND check_out_at IS NOT NULL AND check_out_at != ''
        """
    ).fetchone()["c"]
    still_in_today = get_db().execute(
        """
        SELECT COUNT(*) AS c FROM attendance
        WHERE date(check_in_at) = date('now','localtime')
          AND (check_out_at IS NULL OR check_out_at = '')
        """
    ).fetchone()["c"]

    return render_template(
        "attendance.html",
        rows=rows,
        q=q,
        date=date,
        total_students=total_students,
        total_today=total_today,
        total_out_today=total_out_today,
        still_in_today=still_in_today,
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
            s.finger_left_id,
            s.finger_right_id,
            s.balance,
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
    return get_db().execute(
        """
        SELECT id, student_code, first_name, last_name, name,
               finger_id, finger_left_id, finger_right_id, created_at
        FROM students
        WHERE id = ?
        """,
        (student_id,),
    ).fetchone()


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
        "rescan_left": False,
        "rescan_right": False,
    }

    if request.method == "POST":
        form["student_code"] = (request.form.get("student_code") or "").strip()
        form["first_name"] = (request.form.get("first_name") or "").strip()
        form["last_name"] = (request.form.get("last_name") or "").strip()
        form["rescan_left"] = request.form.get("rescan_left") == "1"
        form["rescan_right"] = request.form.get("rescan_right") == "1"

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

        left_id = student["finger_left_id"]
        right_id = student["finger_right_id"] or student["finger_id"]
        new_left = None
        new_right = None

        try:
            if form["rescan_left"] or form["rescan_right"]:
                with sensor_session() as sensor:
                    if form["rescan_left"]:
                        exclude = set()
                        if student["finger_right_id"] is not None:
                            exclude.add(int(student["finger_right_id"]))
                        elif student["finger_id"] is not None:
                            exclude.add(int(student["finger_id"]))
                        _sensor, new_left = enroll_fingerprint(
                            sensor, "นิ้วมือซ้าย", exclude_positions=exclude
                        )
                    if form["rescan_right"]:
                        exclude = set()
                        current_left = (
                            new_left if new_left is not None else student["finger_left_id"]
                        )
                        if current_left is not None:
                            exclude.add(int(current_left))
                        _sensor, new_right = enroll_fingerprint(
                            sensor, "นิ้วมือขวา", exclude_positions=exclude
                        )
                    if new_left is not None:
                        delete_template(sensor, left_id)
                        left_id = new_left
                    if new_right is not None:
                        delete_template(sensor, right_id)
                        right_id = new_right
        except Exception as exc:
            flash(f"สแกนนิ้วไม่สำเร็จ: {exc}", "error")
            return render_template("edit_student.html", form=form, student=student), 400

        display_name = full_name(form["first_name"], form["last_name"])
        compat_finger = right_id if right_id is not None else left_id
        db.execute(
            """
            UPDATE students
            SET student_code = ?, name = ?, first_name = ?, last_name = ?,
                finger_id = ?, finger_left_id = ?, finger_right_id = ?
            WHERE id = ?
            """,
            (
                form["student_code"],
                display_name,
                form["first_name"],
                form["last_name"],
                compat_finger,
                left_id,
                right_id,
                student_id,
            ),
        )
        db.commit()
        flash(f"บันทึกแล้ว: {form['student_code']} {display_name}", "ok")
        return redirect(url_for("students"))

    return render_template("edit_student.html", form=form, student=student)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id: int):
    student = get_student_or_404(student_id)
    if student is None:
        flash("ไม่พบนักเรียน", "error")
        return redirect(url_for("students"))

    display = full_name(student["first_name"] or student["name"], student["last_name"] or "")

    try:
        deleted_fingers = purge_student_fingerprints(student)
    except Exception as exc:
        flash(
            f"ยังไม่ลบ {student['student_code']} {display} "
            f"เพราะลบลายนิ้วมือจากเซนเซอร์ไม่สำเร็จ: {exc}",
            "error",
        )
        return redirect(url_for("students"))

    db = get_db()
    db.execute("DELETE FROM purchases WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM topups WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()

    if deleted_fingers:
        fingers = ", ".join(f"#{p}" for p in deleted_fingers)
        flash(
            f"ลบครบแล้ว: {student['student_code']} {display} "
            f"(ข้อมูล + ประวัติเข้า + ลายนิ้วมือ {fingers})",
            "ok",
        )
    else:
        flash(f"ลบครบแล้ว: {student['student_code']} {display}", "ok")
    return redirect(url_for("students"))


@app.route("/api/enroll-finger", methods=["POST"])
def api_enroll_finger():
    data = request.get_json(silent=True) or {}
    hand = (data.get("hand") or "").strip().lower()
    if hand not in {"left", "right"}:
        return jsonify(ok=False, message="hand ต้องเป็น left หรือ right"), 400

    exclude_raw = data.get("exclude") or []
    try:
        exclude = {int(v) for v in exclude_raw if v is not None and str(v) != ""}
    except (TypeError, ValueError):
        return jsonify(ok=False, message="exclude ไม่ถูกต้อง"), 400

    replace_id = data.get("replace_id")
    try:
        replace_id = int(replace_id) if replace_id is not None and str(replace_id) != "" else None
    except (TypeError, ValueError):
        return jsonify(ok=False, message="replace_id ไม่ถูกต้อง"), 400

    label = "นิ้วมือซ้าย" if hand == "left" else "นิ้วมือขวา"
    sensor = None
    new_id = None
    try:
        sensor, new_id = enroll_fingerprint(
            None,
            label,
            exclude_positions=exclude,
        )
        if replace_id is not None and replace_id != new_id:
            delete_template(sensor, replace_id, strict=False)
        return jsonify(
            ok=True,
            hand=hand,
            finger_id=new_id,
            message=f"{label}พร้อมแล้ว (นิ้ว #{new_id})",
        )
    except Exception as exc:
        delete_template(sensor, new_id, strict=False)
        return jsonify(ok=False, message=str(exc)), 400


@app.route("/register", methods=["GET", "POST"])
def register():
    form = {
        "student_code": "",
        "first_name": "",
        "last_name": "",
        "finger_left_id": "",
        "finger_right_id": "",
    }

    if request.method == "POST":
        form["student_code"] = (request.form.get("student_code") or "").strip()
        form["first_name"] = (request.form.get("first_name") or "").strip()
        form["last_name"] = (request.form.get("last_name") or "").strip()
        form["finger_left_id"] = (request.form.get("finger_left_id") or "").strip()
        form["finger_right_id"] = (request.form.get("finger_right_id") or "").strip()

        if not form["student_code"] or not form["first_name"] or not form["last_name"]:
            flash("กรุณากรอกรหัส ชื่อ และนามสกุลให้ครบ", "error")
            return render_template("register.html", form=form), 400

        try:
            left_id = int(form["finger_left_id"])
            right_id = int(form["finger_right_id"])
        except ValueError:
            flash("กรุณากดอ่านลายนิ้วมือซ้ายและขวาให้ครบก่อนบันทึก", "error")
            return render_template("register.html", form=form), 400

        if left_id == right_id:
            flash("นิ้วซ้ายและขวาต้องเป็นคนละนิ้ว", "error")
            return render_template("register.html", form=form), 400

        db = get_db()
        exists = db.execute(
            "SELECT id FROM students WHERE student_code = ?",
            (form["student_code"],),
        ).fetchone()
        if exists:
            flash("รหัสนักเรียนนี้มีอยู่แล้ว", "error")
            return render_template("register.html", form=form), 400

        # Ensure these templates are not already bound to another student
        for pos, label in ((left_id, "ซ้าย"), (right_id, "ขวา")):
            owner = find_student_by_finger(db, pos)
            if owner:
                owner_name = full_name(
                    owner["first_name"] or owner["name"],
                    owner["last_name"] or "",
                )
                flash(
                    f"นิ้ว{label} #{pos} ถูกใช้โดย {owner['student_code']} {owner_name} แล้ว",
                    "error",
                )
                return render_template("register.html", form=form), 400

        display_name = full_name(form["first_name"], form["last_name"])
        try:
            db.execute(
                """
                INSERT INTO students(
                  student_code, name, first_name, last_name,
                  finger_id, finger_left_id, finger_right_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form["student_code"],
                    display_name,
                    form["first_name"],
                    form["last_name"],
                    right_id,
                    left_id,
                    right_id,
                ),
            )
            db.commit()
        except Exception as exc:
            flash(f"ลงทะเบียนไม่สำเร็จ: {exc}", "error")
            return render_template("register.html", form=form), 400

        flash(
            f"ลงทะเบียนสำเร็จ: {form['student_code']} {display_name} "
            f"(ซ้าย #{left_id}, ขวา #{right_id})",
            "ok",
        )
        return redirect(url_for("students"))

    return render_template("register.html", form=form)


@app.route("/checkin", methods=["GET"])
def checkin():
    return render_template("checkin.html")


@app.route("/checkout", methods=["GET"])
def checkout():
    return render_template("checkout.html")


def scan_student_from_sensor(timeout_sec: int = 40):
    with sensor_session() as sensor:
        wait_for_finger(sensor, timeout_sec=timeout_sec)
        sensor.convertImage(0x01)
        position, score = sensor.searchTemplate()
        if position < 0:
            raise RuntimeError("ไม่พบลายนิ้วมือในระบบ")

        student = find_student_by_finger(get_db(), int(position))
        if not student:
            raise RuntimeError(f"พบนิ้ว #{position} แต่ยังไม่ได้ผูกกับนักเรียน")

        hand = matched_hand_for(student, int(position))
        return student, hand, int(position), int(score)


@app.route("/api/sensor-ready", methods=["POST"])
def api_sensor_ready():
    try:
        with sensor_session() as sensor:
            count = sensor.getTemplateCount()
            capacity = sensor.getStorageCapacity()
        return jsonify(
            ok=True,
            message="R307 พร้อมรับลายนิ้วมือแล้ว",
            templates=count,
            capacity=capacity,
        )
    except Exception as exc:
        return jsonify(ok=False, message=f"เซนเซอร์ยังไม่พร้อม: {exc}"), 400


@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    db = get_db()
    try:
        student, hand, position, score = scan_student_from_sensor()
        db.execute(
            """
            INSERT INTO attendance(student_id, matched_hand, matched_finger_id)
            VALUES (?, ?, ?)
            """,
            (student["id"], hand, position),
        )
        db.commit()
        when = db.execute("SELECT datetime('now','localtime')").fetchone()[0]
        return jsonify(
            ok=True,
            message="เช็คเข้าสำเร็จ",
            result={
                "student_code": student["student_code"],
                "name": full_name(
                    student["first_name"] or student["name"],
                    student["last_name"] or "",
                ),
                "hand": "ซ้าย" if hand == "left" else "ขวา" if hand == "right" else "-",
                "finger_id": position,
                "score": score,
                "when": when,
            },
        )
    except TimeoutError:
        return jsonify(
            ok=False,
            message="หมดเวลารอวางนิ้ว — กดปุ่มแล้ววางนิ้วบนเซนเซอร์ทันที",
        ), 408
    except Exception as exc:
        return jsonify(ok=False, message=str(exc)), 400


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    db = get_db()
    try:
        student, hand, position, score = scan_student_from_sensor()
        open_row = db.execute(
            """
            SELECT id, check_in_at
            FROM attendance
            WHERE student_id = ?
              AND date(check_in_at) = date('now','localtime')
              AND (check_out_at IS NULL OR check_out_at = '')
            ORDER BY id DESC
            LIMIT 1
            """,
            (student["id"],),
        ).fetchone()
        if not open_row:
            raise RuntimeError("ยังไม่มีรายการเช็คเข้าวันนี้ หรือเช็คออกไปแล้ว")

        db.execute(
            """
            UPDATE attendance
            SET check_out_at = datetime('now','localtime'),
                check_out_hand = ?,
                check_out_finger_id = ?
            WHERE id = ?
            """,
            (hand, position, open_row["id"]),
        )
        db.commit()
        when = db.execute("SELECT datetime('now','localtime')").fetchone()[0]
        return jsonify(
            ok=True,
            message="เช็คออกสำเร็จ",
            result={
                "student_code": student["student_code"],
                "name": full_name(
                    student["first_name"] or student["name"],
                    student["last_name"] or "",
                ),
                "hand": "ซ้าย" if hand == "left" else "ขวา" if hand == "right" else "-",
                "finger_id": position,
                "score": score,
                "when": when,
                "check_in_at": open_row["check_in_at"],
            },
        )
    except TimeoutError:
        return jsonify(
            ok=False,
            message="หมดเวลารอวางนิ้ว — กดปุ่มแล้ววางนิ้วบนเซนเซอร์ทันที",
        ), 408
    except Exception as exc:
        return jsonify(ok=False, message=str(exc)), 400


def student_payload(row) -> dict:
    return {
        "id": row["id"],
        "student_code": row["student_code"],
        "first_name": row["first_name"] or row["name"],
        "last_name": row["last_name"] or "",
        "name": full_name(row["first_name"] or row["name"], row["last_name"] or ""),
        "balance": int(row["balance"] or 0),
    }


@app.route("/api/identify-finger", methods=["POST"])
def api_identify_finger():
    try:
        student, hand, position, score = scan_student_from_sensor(timeout_sec=40)
        balance_row = get_db().execute(
            "SELECT balance FROM students WHERE id = ?",
            (student["id"],),
        ).fetchone()
        student_dict = dict(student)
        student_dict["balance"] = int((balance_row["balance"] if balance_row else 0) or 0)
        payload = student_payload(student_dict)
        payload["finger_id"] = position
        payload["hand"] = hand
        payload["score"] = score
        return jsonify(ok=True, student=payload)
    except TimeoutError:
        return jsonify(
            ok=False,
            message="หมดเวลารอวางนิ้ว — วางนิ้วบนเซนเซอร์ภายใน 40 วินาที",
        ), 408
    except Exception as exc:
        return jsonify(ok=False, message=f"สแกนไม่สำเร็จ: {exc}"), 400


@app.route("/api/student-by-code", methods=["POST"])
def api_student_by_code():
    data = request.get_json(silent=True) or {}
    code = str(data.get("student_code") or "").strip()
    if not code:
        return jsonify(ok=False, message="กรุณาใส่รหัสนักเรียน"), 400

    row = get_db().execute(
        """
        SELECT id, student_code, first_name, last_name, name, balance
        FROM students
        WHERE student_code = ?
        """,
        (code,),
    ).fetchone()
    if not row:
        return jsonify(ok=False, message=f"ไม่พบรหัสนักเรียน {code}"), 404
    return jsonify(ok=True, student=student_payload(row))


@app.route("/api/topup", methods=["POST"])
def api_topup():
    data = request.get_json(silent=True) or {}
    code = str(data.get("student_code") or "").strip()
    try:
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="จำนวนเงินไม่ถูกต้อง"), 400

    if not code:
        return jsonify(ok=False, message="กรุณาสแกนลายนิ้วมือก่อน"), 400
    if amount <= 0:
        return jsonify(ok=False, message="จำนวนเงินต้องมากกว่า 0"), 400
    if amount > 100000:
        return jsonify(ok=False, message="จำนวนเงินสูงเกินไป"), 400

    db = get_db()
    row = db.execute(
        """
        SELECT id, student_code, first_name, last_name, name, balance
        FROM students
        WHERE student_code = ?
        """,
        (code,),
    ).fetchone()
    if not row:
        return jsonify(ok=False, message=f"ไม่พบรหัสนักเรียน {code}"), 404

    new_balance = int(row["balance"] or 0) + amount
    db.execute("UPDATE students SET balance = ? WHERE id = ?", (new_balance, row["id"]))
    db.execute(
        """
        INSERT INTO topups(student_id, amount, balance_after, note)
        VALUES (?, ?, ?, ?)
        """,
        (row["id"], amount, new_balance, data.get("note") or "fingerprint-topup"),
    )
    db.commit()

    student = student_payload(row)
    student["balance"] = new_balance
    when = db.execute("SELECT datetime('now','localtime')").fetchone()[0]
    return jsonify(
        ok=True,
        message=f"เติมเงินสำเร็จ +{amount} บาท",
        student=student,
        amount=amount,
        balance_after=new_balance,
        when=when,
    )


@app.route("/topup")
def topup():
    recent = get_db().execute(
        """
        SELECT
          t.amount,
          t.balance_after,
          t.created_at,
          s.student_code,
          s.first_name,
          s.last_name,
          s.name
        FROM topups t
        JOIN students s ON s.id = t.student_id
        ORDER BY t.id DESC
        LIMIT 10
        """
    ).fetchall()
    return render_template("topup.html", recent=recent)


@app.route("/summary")
def wallet_summary():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    date = (request.args.get("date") or "").strip()

    totals = db.execute(
        """
        SELECT
          COUNT(*) AS student_count,
          COALESCE(SUM(balance), 0) AS total_balance
        FROM students
        """
    ).fetchone()

    topup_totals_sql = """
        SELECT
          COALESCE(SUM(amount), 0) AS total_topup,
          COUNT(*) AS topup_count
        FROM topups
        WHERE 1=1
    """
    topup_params: list[object] = []
    if date:
        topup_totals_sql += " AND date(created_at) = ?"
        topup_params.append(date)

    topup_totals = db.execute(topup_totals_sql, topup_params).fetchone()

    today_topup = db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total_topup, COUNT(*) AS topup_count
        FROM topups
        WHERE date(created_at) = date('now','localtime')
        """
    ).fetchone()

    students_sql = """
        SELECT
          s.id,
          s.student_code,
          s.first_name,
          s.last_name,
          s.name,
          s.balance,
          COALESCE(SUM(t.amount), 0) AS total_topup,
          COUNT(t.id) AS topup_count,
          MAX(t.created_at) AS last_topup_at
        FROM students s
        LEFT JOIN topups t ON t.student_id = s.id
        WHERE 1=1
    """
    student_params: list[object] = []
    if q:
        students_sql += """
          AND (
            s.student_code LIKE ?
            OR s.name LIKE ?
            OR s.first_name LIKE ?
            OR s.last_name LIKE ?
          )
        """
        like = f"%{q}%"
        student_params.extend([like, like, like, like])
    students_sql += """
        GROUP BY s.id
        ORDER BY s.balance DESC, s.student_code ASC
    """
    rows = db.execute(students_sql, student_params).fetchall()

    recent_sql = """
        SELECT
          t.amount,
          t.balance_after,
          t.created_at,
          s.student_code,
          s.first_name,
          s.last_name,
          s.name
        FROM topups t
        JOIN students s ON s.id = t.student_id
        WHERE 1=1
    """
    recent_params: list[object] = []
    if date:
        recent_sql += " AND date(t.created_at) = ?"
        recent_params.append(date)
    if q:
        recent_sql += """
          AND (
            s.student_code LIKE ?
            OR s.name LIKE ?
            OR s.first_name LIKE ?
            OR s.last_name LIKE ?
          )
        """
        like = f"%{q}%"
        recent_params.extend([like, like, like, like])
    recent_sql += " ORDER BY t.id DESC LIMIT 50"
    recent = db.execute(recent_sql, recent_params).fetchall()

    return render_template(
        "summary.html",
        rows=rows,
        recent=recent,
        q=q,
        date=date,
        student_count=totals["student_count"],
        total_balance=totals["total_balance"],
        total_topup=topup_totals["total_topup"],
        topup_count=topup_totals["topup_count"],
        today_topup=today_topup["total_topup"],
        today_topup_count=today_topup["topup_count"],
    )


def get_shop_or_none(shop_id: int):
    return get_db().execute(
        "SELECT id, name, note, is_active, created_at FROM shops WHERE id = ?",
        (shop_id,),
    ).fetchone()


@app.route("/shops")
def shops():
    q = (request.args.get("q") or "").strip()
    sql = """
        SELECT
          sh.id,
          sh.name,
          sh.note,
          sh.is_active,
          sh.created_at,
          COUNT(p.id) AS purchase_count,
          COALESCE(SUM(p.amount), 0) AS total_sales
        FROM shops sh
        LEFT JOIN purchases p ON p.shop_id = sh.id
        WHERE 1=1
    """
    params: list[object] = []
    if q:
        sql += " AND (sh.name LIKE ? OR sh.note LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])
    sql += " GROUP BY sh.id ORDER BY sh.is_active DESC, sh.name ASC"
    rows = get_db().execute(sql, params).fetchall()
    return render_template("shops.html", rows=rows, q=q)


@app.route("/shops/new", methods=["GET", "POST"])
def new_shop():
    form = {"name": "", "note": "", "is_active": True}
    if request.method == "POST":
        form["name"] = (request.form.get("name") or "").strip()
        form["note"] = (request.form.get("note") or "").strip()
        form["is_active"] = request.form.get("is_active") == "1"
        if not form["name"]:
            flash("กรุณาใส่ชื่อร้าน", "error")
            return render_template("shop_form.html", form=form, mode="new"), 400

        db = get_db()
        exists = db.execute(
            "SELECT id FROM shops WHERE name = ?",
            (form["name"],),
        ).fetchone()
        if exists:
            flash("ชื่อร้านนี้มีอยู่แล้ว", "error")
            return render_template("shop_form.html", form=form, mode="new"), 400

        db.execute(
            "INSERT INTO shops(name, note, is_active) VALUES (?, ?, ?)",
            (form["name"], form["note"], 1 if form["is_active"] else 0),
        )
        db.commit()
        flash(f"เพิ่มร้านแล้ว: {form['name']}", "ok")
        return redirect(url_for("shops"))

    return render_template("shop_form.html", form=form, mode="new")


@app.route("/shops/<int:shop_id>/edit", methods=["GET", "POST"])
def edit_shop(shop_id: int):
    shop = get_shop_or_none(shop_id)
    if shop is None:
        flash("ไม่พบร้าน", "error")
        return redirect(url_for("shops"))

    form = {
        "name": shop["name"],
        "note": shop["note"] or "",
        "is_active": bool(shop["is_active"]),
    }
    if request.method == "POST":
        form["name"] = (request.form.get("name") or "").strip()
        form["note"] = (request.form.get("note") or "").strip()
        form["is_active"] = request.form.get("is_active") == "1"
        if not form["name"]:
            flash("กรุณาใส่ชื่อร้าน", "error")
            return render_template(
                "shop_form.html", form=form, mode="edit", shop=shop
            ), 400

        db = get_db()
        duplicate = db.execute(
            "SELECT id FROM shops WHERE name = ? AND id != ?",
            (form["name"], shop_id),
        ).fetchone()
        if duplicate:
            flash("ชื่อร้านนี้มีอยู่แล้ว", "error")
            return render_template(
                "shop_form.html", form=form, mode="edit", shop=shop
            ), 400

        db.execute(
            """
            UPDATE shops
            SET name = ?, note = ?, is_active = ?
            WHERE id = ?
            """,
            (form["name"], form["note"], 1 if form["is_active"] else 0, shop_id),
        )
        db.commit()
        flash(f"บันทึกร้านแล้ว: {form['name']}", "ok")
        return redirect(url_for("shops"))

    return render_template("shop_form.html", form=form, mode="edit", shop=shop)


@app.route("/shops/<int:shop_id>/delete", methods=["POST"])
def delete_shop(shop_id: int):
    shop = get_shop_or_none(shop_id)
    if shop is None:
        flash("ไม่พบร้าน", "error")
        return redirect(url_for("shops"))

    db = get_db()
    purchase_count = db.execute(
        "SELECT COUNT(*) AS c FROM purchases WHERE shop_id = ?",
        (shop_id,),
    ).fetchone()["c"]
    if purchase_count:
        # Soft-disable instead of hard delete to keep sales history
        db.execute("UPDATE shops SET is_active = 0 WHERE id = ?", (shop_id,))
        db.commit()
        flash(
            f"ร้าน {shop['name']} มีประวัติขายอยู่ จึงปิดใช้งานแทนการลบ",
            "ok",
        )
    else:
        db.execute("DELETE FROM shops WHERE id = ?", (shop_id,))
        db.commit()
        flash(f"ลบร้านแล้ว: {shop['name']}", "ok")
    return redirect(url_for("shops"))


@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    data = request.get_json(silent=True) or {}
    code = str(data.get("student_code") or "").strip()
    try:
        shop_id = int(data.get("shop_id"))
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify(ok=False, message="ข้อมูลร้านหรือจำนวนเงินไม่ถูกต้อง"), 400

    if not code:
        return jsonify(ok=False, message="กรุณาสแกนลายนิ้วมือก่อน"), 400
    if amount <= 0:
        return jsonify(ok=False, message="จำนวนเงินต้องมากกว่า 0"), 400
    if amount > 100000:
        return jsonify(ok=False, message="จำนวนเงินสูงเกินไป"), 400

    db = get_db()
    shop = db.execute(
        "SELECT id, name, is_active FROM shops WHERE id = ?",
        (shop_id,),
    ).fetchone()
    if not shop or not shop["is_active"]:
        return jsonify(ok=False, message="ไม่พบร้านที่ใช้งานได้"), 404

    row = db.execute(
        """
        SELECT id, student_code, first_name, last_name, name, balance
        FROM students
        WHERE student_code = ?
        """,
        (code,),
    ).fetchone()
    if not row:
        return jsonify(ok=False, message=f"ไม่พบรหัสนักเรียน {code}"), 404

    balance = int(row["balance"] or 0)
    if balance < amount:
        return jsonify(
            ok=False,
            message=f"ยอดเงินไม่พอ (คงเหลือ {balance} บาท)",
            balance=balance,
        ), 400

    new_balance = balance - amount
    hand = data.get("hand")
    finger_id = data.get("finger_id")
    try:
        finger_id = int(finger_id) if finger_id is not None else None
    except (TypeError, ValueError):
        finger_id = None

    db.execute("UPDATE students SET balance = ? WHERE id = ?", (new_balance, row["id"]))
    db.execute(
        """
        INSERT INTO purchases(
          student_id, shop_id, amount, balance_after, matched_hand, matched_finger_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row["id"], shop_id, amount, new_balance, hand, finger_id),
    )
    db.commit()

    student = student_payload(row)
    student["balance"] = new_balance
    when = db.execute("SELECT datetime('now','localtime')").fetchone()[0]
    return jsonify(
        ok=True,
        message=f"ตัดเงินสำเร็จ -{amount} บาท ที่ร้าน {shop['name']}",
        student=student,
        shop={"id": shop["id"], "name": shop["name"]},
        amount=amount,
        balance_after=new_balance,
        when=when,
    )


@app.route("/purchase")
def purchase():
    db = get_db()
    active_shops = db.execute(
        """
        SELECT id, name, note
        FROM shops
        WHERE is_active = 1
        ORDER BY name ASC
        """
    ).fetchall()
    recent = db.execute(
        """
        SELECT
          p.amount,
          p.balance_after,
          p.created_at,
          s.student_code,
          s.first_name,
          s.last_name,
          s.name,
          sh.name AS shop_name
        FROM purchases p
        JOIN students s ON s.id = p.student_id
        JOIN shops sh ON sh.id = p.shop_id
        ORDER BY p.id DESC
        LIMIT 10
        """
    ).fetchall()
    return render_template("purchase.html", shops=active_shops, recent=recent)


@app.route("/purchases")
def purchase_history():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    date = (request.args.get("date") or "").strip()
    shop_id = (request.args.get("shop_id") or "").strip()

    shops = db.execute(
        "SELECT id, name FROM shops ORDER BY name ASC"
    ).fetchall()

    where = ["1=1"]
    params: list[object] = []
    if q:
        where.append(
            "(s.student_code LIKE ? OR s.name LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if date:
        where.append("date(p.created_at) = ?")
        params.append(date)
    if shop_id:
        where.append("p.shop_id = ?")
        params.append(int(shop_id))

    where_sql = " AND ".join(where)

    totals = db.execute(
        f"""
        SELECT
          COALESCE(SUM(p.amount), 0) AS total_amount,
          COUNT(p.id) AS purchase_count
        FROM purchases p
        JOIN students s ON s.id = p.student_id
        JOIN shops sh ON sh.id = p.shop_id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    today = db.execute(
        """
        SELECT
          COALESCE(SUM(amount), 0) AS total_amount,
          COUNT(*) AS purchase_count
        FROM purchases
        WHERE date(created_at) = date('now','localtime')
        """
    ).fetchone()

    rows = db.execute(
        f"""
        SELECT
          p.id,
          p.amount,
          p.balance_after,
          p.matched_hand,
          p.matched_finger_id,
          p.created_at,
          s.student_code,
          s.first_name,
          s.last_name,
          s.name,
          sh.name AS shop_name
        FROM purchases p
        JOIN students s ON s.id = p.student_id
        JOIN shops sh ON sh.id = p.shop_id
        WHERE {where_sql}
        ORDER BY p.id DESC
        LIMIT 500
        """,
        params,
    ).fetchall()

    return render_template(
        "purchase_history.html",
        rows=rows,
        shops=shops,
        q=q,
        date=date,
        shop_id=shop_id,
        total_amount=totals["total_amount"],
        purchase_count=totals["purchase_count"],
        today_amount=today["total_amount"],
        today_count=today["purchase_count"],
    )


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    print(f"DB: {app.config['DB_PATH']}")
    print(f"Sensor: {app.config['FINGERPRINT_PORT']} @ {app.config['FINGERPRINT_BAUD']}")
    print(f"Open: http://{host}:{port}/")
    app.run(host=host, port=port, debug=False, threaded=True)
