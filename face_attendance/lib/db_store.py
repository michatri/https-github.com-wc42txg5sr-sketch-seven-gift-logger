"""MySQL repositories for students, attendance, and school options."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import numpy as np

from .db import db_cursor


def _emb_to_blob(emb: np.ndarray) -> bytes:
    arr = np.asarray(emb, dtype=np.float32).reshape(-1)
    bio = io.BytesIO()
    np.save(bio, arr)
    return bio.getvalue()


def _blob_to_emb(blob: bytes | bytearray | memoryview | None) -> np.ndarray | None:
    if not blob:
        return None
    return np.load(io.BytesIO(bytes(blob)))


def upsert_student(meta: dict[str, Any], embedding: np.ndarray | None = None,
                   preview_jpeg: bytes | None = None) -> None:
    sql = """
    INSERT INTO students (
      person_id, display_name, academic_year, term, grade, room,
      face_score, embedding, preview_jpeg, source_path
    ) VALUES (
      %(person_id)s, %(display_name)s, %(academic_year)s, %(term)s, %(grade)s, %(room)s,
      %(face_score)s, %(embedding)s, %(preview_jpeg)s, %(source_path)s
    )
    ON DUPLICATE KEY UPDATE
      display_name = VALUES(display_name),
      academic_year = VALUES(academic_year),
      term = VALUES(term),
      grade = VALUES(grade),
      room = VALUES(room),
      face_score = VALUES(face_score),
      embedding = COALESCE(VALUES(embedding), embedding),
      preview_jpeg = COALESCE(VALUES(preview_jpeg), preview_jpeg),
      source_path = COALESCE(VALUES(source_path), source_path)
    """
    payload = {
        "person_id": meta["person_id"],
        "display_name": meta.get("display_name") or meta["person_id"],
        "academic_year": meta.get("academic_year") or "",
        "term": meta.get("term") or "",
        "grade": meta.get("grade") or "",
        "room": meta.get("room") or "",
        "face_score": meta.get("face_score"),
        "embedding": _emb_to_blob(embedding) if embedding is not None else None,
        "preview_jpeg": preview_jpeg,
        "source_path": meta.get("source_image") or meta.get("source_path"),
    }
    with db_cursor(commit=True) as cur:
        cur.execute(sql, payload)


def get_student(person_id: str) -> dict[str, Any] | None:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM students WHERE person_id = %s", (person_id,))
        row = cur.fetchone()
    if not row:
        return None
    return _student_row_to_meta(row)


def list_students(
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if academic_year:
        clauses.append("academic_year = %s")
        params.append(academic_year)
    if term:
        clauses.append("term = %s")
        params.append(term)
    if grade:
        clauses.append("grade = %s")
        params.append(grade)
    if room:
        clauses.append("room = %s")
        params.append(room)
    if q:
        clauses.append("(person_id LIKE %s OR display_name LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT person_id, display_name, academic_year, term, grade, room,
           face_score, source_path, preview_jpeg IS NOT NULL AS has_preview
    FROM students
    {where}
    ORDER BY person_id
    """
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [_student_row_to_meta(r) for r in rows]


def delete_student(person_id: str) -> bool:
    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM students WHERE person_id = %s", (person_id,))
        return cur.rowcount > 0


def load_embeddings() -> dict[str, np.ndarray]:
    with db_cursor() as cur:
        cur.execute("SELECT person_id, embedding FROM students WHERE embedding IS NOT NULL")
        rows = cur.fetchall()
    out: dict[str, np.ndarray] = {}
    for row in rows:
        emb = _blob_to_emb(row.get("embedding"))
        if emb is not None:
            out[row["person_id"]] = emb
    return out


def get_preview_jpeg(person_id: str) -> bytes | None:
    with db_cursor() as cur:
        cur.execute("SELECT preview_jpeg FROM students WHERE person_id = %s", (person_id,))
        row = cur.fetchone()
    if not row or not row.get("preview_jpeg"):
        return None
    return bytes(row["preview_jpeg"])


def insert_attendance(record: dict[str, Any]) -> int:
    sql = """
    INSERT INTO attendance (
      timestamp_local, timestamp_utc, direction, person_id, display_name,
      academic_year, term, grade, room, similarity, snapshot_path
    ) VALUES (
      %(timestamp_local)s, %(timestamp_utc)s, %(direction)s, %(person_id)s, %(display_name)s,
      %(academic_year)s, %(term)s, %(grade)s, %(room)s, %(similarity)s, %(snapshot_path)s
    )
    """
    payload = {
        "timestamp_local": _parse_dt(record.get("timestamp_local")),
        "timestamp_utc": _parse_dt(record.get("timestamp_utc")),
        "direction": record.get("direction"),
        "person_id": record.get("person_id"),
        "display_name": record.get("display_name") or "",
        "academic_year": record.get("academic_year") or "",
        "term": record.get("term") or "",
        "grade": record.get("grade") or "",
        "room": record.get("room") or "",
        "similarity": record.get("similarity"),
        "snapshot_path": record.get("snapshot") or record.get("snapshot_path"),
    }
    with db_cursor(commit=True) as cur:
        cur.execute(sql, payload)
        return int(cur.lastrowid)


def list_attendance(
    *,
    direction: str | None = None,
    person_id: str | None = None,
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    today_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if today_only:
        clauses.append("DATE(timestamp_local) = CURDATE()")
    if direction:
        clauses.append("direction = %s")
        params.append(direction)
    if person_id:
        clauses.append("person_id = %s")
        params.append(person_id)
    if academic_year:
        clauses.append("academic_year = %s")
        params.append(academic_year)
    if term:
        clauses.append("term = %s")
        params.append(term)
    if grade:
        clauses.append("grade = %s")
        params.append(grade)
    if room:
        clauses.append("room = %s")
        params.append(room)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
    SELECT id, timestamp_local, timestamp_utc, direction, person_id, display_name,
           academic_year, term, grade, room, similarity, snapshot_path
    FROM attendance
    {where}
    ORDER BY timestamp_local DESC, id DESC
    LIMIT %s
    """
    params.append(int(limit))
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    out = []
    for row in rows:
        item = dict(row)
        snap = item.get("snapshot_path") or ""
        item["snapshot"] = snap
        if snap:
            name = snap.replace("\\", "/").split("/")[-1]
            item["snapshot_url"] = f"/api/attendance/snapshot-file/{name}"
        for key in ("timestamp_local", "timestamp_utc"):
            val = item.get(key)
            if isinstance(val, datetime):
                item[key] = val.isoformat(timespec="seconds")
        out.append(item)
    return out


def list_option_years() -> list[str]:
    with db_cursor() as cur:
        cur.execute("SELECT value FROM school_option_years ORDER BY value DESC")
        return [r["value"] for r in cur.fetchall()]


def list_option_rooms() -> list[str]:
    with db_cursor() as cur:
        cur.execute("SELECT value FROM school_option_rooms ORDER BY value")
        return [r["value"] for r in cur.fetchall()]


def add_option_year(value: str) -> None:
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT IGNORE INTO school_option_years (value) VALUES (%s)",
            (value,),
        )


def add_option_room(value: str) -> None:
    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT IGNORE INTO school_option_rooms (value) VALUES (%s)",
            (value,),
        )


def _student_row_to_meta(row: dict[str, Any]) -> dict[str, Any]:
    person_id = row["person_id"]
    return {
        "person_id": person_id,
        "display_name": row.get("display_name") or person_id,
        "academic_year": row.get("academic_year") or "",
        "term": row.get("term") or "",
        "grade": row.get("grade") or "",
        "room": row.get("room") or "",
        "face_score": row.get("face_score"),
        "source_image": row.get("source_path"),
        "has_preview": bool(row.get("has_preview") or row.get("preview_jpeg")),
        "preview_url": f"/api/people/{person_id}/preview",
    }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value or "").strip()
    if not text:
        return datetime.utcnow()
    # handle trailing Z / timezone
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.utcnow()
