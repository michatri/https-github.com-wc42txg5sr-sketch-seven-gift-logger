#!/usr/bin/env python3
"""FastAPI web app: ลงทะเบียนใบหน้า + ลงเวลาเข้า/ออก."""

from __future__ import annotations

import re
import threading
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from face_attendance.lib.attendance import (
    attendance_dir,
    list_records,
    list_student_history,
    process_frame,
)
from face_attendance.lib.camera import (
    FacePipeline,
    draw_hits,
    load_camera_env,
    snapshot_from_camera,
)
from face_attendance.lib.gallery import (
    EnrollmentError,
    delete_person,
    enroll_from_ndarray,
    get_person,
    list_people,
    update_person,
)
from face_attendance.lib.school_options import (
    add_academic_year,
    add_room,
    get_school_options,
)

WEB_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Face Attendance", version="0.3.0")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

_pipeline_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_pipeline() -> FacePipeline:
    load_camera_env()
    return FacePipeline()


def _decode_upload(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise EnrollmentError("ไฟล์รูปไม่ถูกต้อง")
    return img


def _json_error(exc: Exception, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=status)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "active": "enroll",
            "people_count": len(list_people()),
        },
    )


@app.get("/check-in", response_class=HTMLResponse)
def check_in_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "attendance.html",
        {
            "active": "in",
            "direction": "in",
            "direction_label": "เข้า",
            "page_title": "ลงเวลาเข้าโรงเรียน",
            "page_sub": "สแกนใบหน้าจากกล้องเพื่อบันทึกเวลาเข้าโรงเรียนหลายคนพร้อมกัน",
        },
    )


@app.get("/check-out", response_class=HTMLResponse)
def check_out_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "attendance.html",
        {
            "active": "out",
            "direction": "out",
            "direction_label": "ออก",
            "page_title": "ลงเวลาออกจากโรงเรียน",
            "page_sub": "สแกนใบหน้าจากกล้องเพื่อบันทึกเวลาออกจากโรงเรียนหลายคนพร้อมกัน",
        },
    )


@app.get("/students", response_class=HTMLResponse)
def students_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "students.html",
        {"active": "students"},
    )


@app.get("/api/students")
def api_students(
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    q: str | None = None,
) -> dict:
    students = list_people(
        academic_year=academic_year,
        term=term,
        grade=grade,
        room=room,
        q=q,
    )
    return {"ok": True, "count": len(students), "students": students}


@app.get("/api/students/options")
def api_student_options() -> dict:
    return {"ok": True, "options": get_school_options()}


@app.get("/api/school-options")
def api_school_options() -> dict:
    return {"ok": True, "options": get_school_options()}


@app.post("/api/school-options/academic-year")
def api_add_academic_year(payload: dict = Body(...)) -> JSONResponse:
    try:
        options = add_academic_year(str(payload.get("value") or ""))
        return JSONResponse({"ok": True, "options": options})
    except EnrollmentError as exc:
        return _json_error(exc)


@app.post("/api/school-options/room")
def api_add_room(payload: dict = Body(...)) -> JSONResponse:
    try:
        options = add_room(str(payload.get("value") or ""))
        return JSONResponse({"ok": True, "options": options})
    except EnrollmentError as exc:
        return _json_error(exc)


@app.get("/api/students/{person_id}/history")
def api_student_history(person_id: str, limit: int = Query(200, ge=1, le=1000)) -> JSONResponse:
    try:
        student = get_person(person_id)
        records = list_student_history(person_id, limit=limit)
        return JSONResponse(
            {"ok": True, "student": student, "count": len(records), "records": records}
        )
    except EnrollmentError as exc:
        return _json_error(exc, status=404)


@app.get("/api/people")
def api_list_people(
    academic_year: str | None = None,
    term: str | None = None,
    grade: str | None = None,
    room: str | None = None,
    q: str | None = None,
) -> dict:
    people = list_people(
        academic_year=academic_year,
        term=term,
        grade=grade,
        room=room,
        q=q,
    )
    return {"ok": True, "count": len(people), "people": people}


@app.get("/api/people/{person_id}")
def api_get_person(person_id: str) -> JSONResponse:
    try:
        return JSONResponse({"ok": True, "person": get_person(person_id)})
    except EnrollmentError as exc:
        return _json_error(exc, status=404)


@app.get("/api/people/{person_id}/preview")
def api_preview(person_id: str) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", person_id):
        raise HTTPException(status_code=400, detail="รหัสไม่ถูกต้อง")
    try:
        from face_attendance.lib.db import mysql_enabled
        from face_attendance.lib import db_store

        if mysql_enabled():
            blob = db_store.get_preview_jpeg(person_id)
            if blob:
                return Response(content=blob, media_type="image/jpeg")
    except Exception:
        pass
    path = (
        Path(__file__).resolve().parents[1] / "data" / "gallery" / person_id / "preview.jpg"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบรูปตัวอย่าง")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@app.patch("/api/people/{person_id}")
async def api_update_person(
    person_id: str,
    display_name: str = Form(""),
    academic_year: str = Form(""),
    term: str = Form(""),
    grade: str = Form(""),
    room: str = Form(""),
    from_camera: str = Form("0"),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    try:
        profile = {
            "display_name": display_name,
            "academic_year": academic_year,
            "term": term,
            "grade": grade,
            "room": room,
        }
        use_camera = from_camera in {"1", "true", "True", "yes"}
        if use_camera:
            with _pipeline_lock:
                image_bgr = snapshot_from_camera()
                meta = update_person(
                    person_id,
                    pipeline=get_pipeline(),
                    image_bgr=image_bgr,
                    **profile,
                )
        elif image is not None and image.filename:
            data = await image.read()
            if not data:
                raise EnrollmentError("ไม่พบไฟล์รูป")
            image_bgr = _decode_upload(data)
            with _pipeline_lock:
                meta = update_person(
                    person_id,
                    pipeline=get_pipeline(),
                    image_bgr=image_bgr,
                    **profile,
                )
        else:
            meta = update_person(person_id, **profile)
        return JSONResponse({"ok": True, "person": meta})
    except EnrollmentError as exc:
        return _json_error(exc)
    except RuntimeError as exc:
        return _json_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _json_error(exc, status=500)


@app.delete("/api/people/{person_id}")
def api_delete(person_id: str) -> dict:
    try:
        delete_person(person_id)
    except EnrollmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "deleted": person_id}


@app.post("/api/enroll")
async def api_enroll(
    person_id: str = Form(...),
    display_name: str = Form(""),
    academic_year: str = Form(""),
    term: str = Form(""),
    grade: str = Form(""),
    room: str = Form(""),
    image: UploadFile = File(...),
) -> JSONResponse:
    try:
        data = await image.read()
        if not data:
            raise EnrollmentError("ไม่พบไฟล์รูป")
        img = _decode_upload(data)
        with _pipeline_lock:
            meta = enroll_from_ndarray(
                get_pipeline(),
                img,
                person_id,
                display_name=display_name or None,
                academic_year=academic_year or None,
                term=term or None,
                grade=grade or None,
                room=room or None,
            )
        return JSONResponse({"ok": True, "person": meta})
    except EnrollmentError as exc:
        return _json_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _json_error(exc, status=500)


@app.post("/api/enroll/from-camera")
async def api_enroll_from_camera(
    person_id: str = Form(...),
    display_name: str = Form(""),
    academic_year: str = Form(""),
    term: str = Form(""),
    grade: str = Form(""),
    room: str = Form(""),
) -> JSONResponse:
    try:
        with _pipeline_lock:
            frame = snapshot_from_camera()
            meta = enroll_from_ndarray(
                get_pipeline(),
                frame,
                person_id,
                display_name=display_name or None,
                academic_year=academic_year or None,
                term=term or None,
                grade=grade or None,
                room=room or None,
            )
        return JSONResponse({"ok": True, "person": meta})
    except EnrollmentError as exc:
        return _json_error(exc)
    except RuntimeError as exc:
        return _json_error(exc)
    except Exception as exc:  # noqa: BLE001
        return _json_error(exc, status=500)


@app.get("/api/camera/snapshot")
def api_camera_snapshot(annotate: bool = True) -> Response:
    try:
        with _pipeline_lock:
            frame = snapshot_from_camera()
            if annotate:
                hits = get_pipeline().detect(frame)
                frame = draw_hits(frame, hits)
                face_count = len(hits)
            else:
                face_count = 0
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise RuntimeError("encode รูปไม่สำเร็จ")
        headers = {"X-Face-Count": str(face_count)}
        return Response(content=buf.tobytes(), media_type="image/jpeg", headers=headers)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/attendance/scan")
def api_attendance_scan(
    direction: str = Query("in", pattern="^(in|out)$"),
) -> Response:
    try:
        with _pipeline_lock:
            frame = snapshot_from_camera()
            result = process_frame(get_pipeline(), frame, direction)  # type: ignore[arg-type]
        headers = {
            "X-Face-Count": str(result["face_count"]),
            "X-Marked-Count": str(len(result["marked"])),
            "X-Unknown-Count": str(result["unknown"]),
            "X-Skipped-Count": str(len(result["skipped"])),
            "X-Direction": direction,
        }
        return Response(
            content=result["image_jpeg"],
            media_type="image/jpeg",
            headers=headers,
        )
    except Exception as exc:  # noqa: BLE001
        return _json_error(exc, status=500)


@app.get("/api/attendance")
def api_attendance_list(
    direction: str | None = Query(None, pattern="^(in|out)$"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    rows = list_records(direction=direction, limit=limit)  # type: ignore[arg-type]
    return {"ok": True, "count": len(rows), "records": rows}


@app.get("/api/attendance/snapshot-file/{filename}")
def api_attendance_snapshot_file(filename: str) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.jpg", filename):
        raise HTTPException(status_code=400, detail="ชื่อไฟล์ไม่ถูกต้อง")
    path = attendance_dir() / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@app.get("/api/health")
def health() -> dict:
    payload = {"ok": True, "people": len(list_people())}
    try:
        from face_attendance.lib.db import mysql_enabled, ping

        payload["mysql_enabled"] = mysql_enabled()
        if mysql_enabled():
            payload["mysql"] = ping()
    except Exception as exc:  # noqa: BLE001
        payload["mysql_enabled"] = False
        payload["mysql_error"] = str(exc)
    return payload
