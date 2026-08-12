#!/usr/bin/env python3
"""FastAPI web app: ลงทะเบียนใบหน้านักเรียน."""

from __future__ import annotations

import re
import threading
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    list_people,
)

WEB_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Face Enrollment", version="0.1.0")
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
            "people_count": len(list_people()),
        },
    )


@app.get("/api/people")
def api_list_people() -> dict:
    people = list_people()
    return {"ok": True, "count": len(people), "people": people}


@app.get("/api/people/{person_id}/preview")
def api_preview(person_id: str) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", person_id):
        raise HTTPException(status_code=400, detail="รหัสไม่ถูกต้อง")
    path = (
        Path(__file__).resolve().parents[1] / "data" / "gallery" / person_id / "preview.jpg"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="ไม่พบรูปตัวอย่าง")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


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
) -> JSONResponse:
    try:
        with _pipeline_lock:
            frame = snapshot_from_camera()
            meta = enroll_from_ndarray(
                get_pipeline(),
                frame,
                person_id,
                display_name=display_name or None,
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


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "people": len(list_people())}
