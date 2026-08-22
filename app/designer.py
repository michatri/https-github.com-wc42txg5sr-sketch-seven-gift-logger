from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import (
    DIOCESES,
    REPORT_FIELDS,
    REPORT_SOURCES,
    SEARCH_FIELDS,
    display_name,
    fetch_report_rows,
    format_report_value,
    get_db,
    now,
    row_to_dict,
    rows_to_dicts,
    thai_date,
)
from app.pdfs import design_pdf, pdf_response
from pathlib import Path

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["thai_date"] = thai_date
templates.env.filters["dname"] = display_name
templates.env.globals["search_fields"] = SEARCH_FIELDS
templates.env.globals["dioceses"] = DIOCESES

router = APIRouter()

DEFAULT_LAYOUT = {
    "page": "A4",
    "orientation": "P",
    "mode": "form",
    "header": True,
    "elements": [],
    "columns": [],
}


def _user(request: Request) -> str | None:
    return request.session.get("user")


def _guard(request: Request):
    if not _user(request):
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    return None


def _parish() -> dict[str, Any]:
    with get_db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM parish_settings WHERE id = 1").fetchone()) or {}


def _render(request: Request, name: str, **ctx: Any):
    ctx.update(request=request, user=_user(request), parish=_parish())
    return templates.TemplateResponse(request, name, ctx)


def _parse_layout(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        layout = raw
    else:
        try:
            layout = json.loads(raw or "{}")
        except json.JSONDecodeError:
            layout = {}
    out = dict(DEFAULT_LAYOUT)
    out.update(layout or {})
    out["elements"] = list(out.get("elements") or [])
    out["columns"] = list(out.get("columns") or [])
    if out.get("mode") not in ("form", "list"):
        out["mode"] = "form"
    if str(out.get("orientation") or "P").upper().startswith("L"):
        out["orientation"] = "L"
    else:
        out["orientation"] = "P"
    out["header"] = bool(out.get("header", True))
    return out


def _boot(design: dict, layout: dict, source: str, sample: dict) -> dict:
    return {
        "id": design.get("id"),
        "name": design.get("name") or "",
        "source": source,
        "layout": layout,
        "fields": [{"key": k, "label": lab} for k, lab in REPORT_FIELDS.get(source, [])],
        "sample": {k: format_report_value(sample, k) for k, _lab in REPORT_FIELDS.get(source, [])} if sample else {},
        "sources": {k: v["label"] for k, v in REPORT_SOURCES.items()},
    }


@router.get("/designer", response_class=HTMLResponse)
def designer_list(request: Request):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        items = rows_to_dicts(conn.execute("SELECT * FROM report_designs ORDER BY updated_at DESC, id DESC").fetchall())
    for item in items:
        item["source_label"] = REPORT_SOURCES.get(item.get("source") or "", {}).get("label", item.get("source"))
        layout = _parse_layout(item.get("layout"))
        item["mode"] = "รายชื่อ" if layout.get("mode") == "list" else "วางฟิลด์ทีละหน้า"
        item["field_count"] = len(layout.get("columns") or []) if layout.get("mode") == "list" else len(layout.get("elements") or [])
    return _render(request, "designer_list.html", items=items, sources=REPORT_SOURCES)


@router.get("/designer/new", response_class=HTMLResponse)
def designer_new(request: Request, source: str = "members"):
    if (redir := _guard(request)):
        return redir
    if source not in REPORT_SOURCES:
        source = "members"
    design = {"id": None, "name": "", "source": source, "layout": json.dumps(DEFAULT_LAYOUT, ensure_ascii=False)}
    return _render(
        request,
        "designer_edit.html",
        design=design,
        layout=DEFAULT_LAYOUT,
        sources=REPORT_SOURCES,
        fields=REPORT_FIELDS.get(source, []),
        sample={},
        boot=_boot(design, DEFAULT_LAYOUT, source, {}),
    )


@router.get("/designer/{design_id}", response_class=HTMLResponse)
def designer_edit(request: Request, design_id: int):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        design = row_to_dict(conn.execute("SELECT * FROM report_designs WHERE id = ?", (design_id,)).fetchone())
        sample_rows = fetch_report_rows(conn, (design or {}).get("source") or "members", limit=1)
    if not design:
        return RedirectResponse("/designer", status_code=303)
    layout = _parse_layout(design.get("layout"))
    source = design.get("source") or "members"
    return _render(
        request,
        "designer_edit.html",
        design=design,
        layout=layout,
        sources=REPORT_SOURCES,
        fields=REPORT_FIELDS.get(source, []),
        sample=sample_rows[0] if sample_rows else {},
        boot=_boot(design, layout, source, sample_rows[0] if sample_rows else {}),
    )


@router.get("/api/designer/sample")
def designer_sample(request: Request, source: str = "members", q: str = ""):
    if not _user(request):
        return JSONResponse({"ok": False}, status_code=401)
    if source not in REPORT_SOURCES:
        return JSONResponse({"ok": False, "error": "unknown source"}, status_code=400)
    with get_db() as conn:
        rows = fetch_report_rows(conn, source, q=q, limit=1)
    record = rows[0] if rows else {}
    preview = {key: format_report_value(record, key) for key, _label in REPORT_FIELDS.get(source, [])}
    return {"ok": True, "record": preview, "fields": REPORT_FIELDS.get(source, [])}


@router.post("/designer/save")
async def designer_save(request: Request):
    if not _user(request):
        return JSONResponse({"ok": False, "error": "login"}, status_code=401)
    body = await request.json()
    name = str(body.get("name") or "").strip()
    source = str(body.get("source") or "members")
    if not name:
        return JSONResponse({"ok": False, "error": "กรุณาตั้งชื่อรายงาน"}, status_code=400)
    if source not in REPORT_SOURCES:
        return JSONResponse({"ok": False, "error": "แหล่งข้อมูลไม่ถูกต้อง"}, status_code=400)
    layout = _parse_layout(body.get("layout"))
    payload = json.dumps(layout, ensure_ascii=False)
    stamp = now()
    design_id = body.get("id")
    with get_db() as conn:
        if design_id:
            conn.execute(
                "UPDATE report_designs SET name=?, source=?, layout=?, updated_at=? WHERE id=?",
                (name, source, payload, stamp, int(design_id)),
            )
            nid = int(design_id)
        else:
            conn.execute(
                "INSERT INTO report_designs (name, source, layout, created_at, updated_at) VALUES (?,?,?,?,?)",
                (name, source, payload, stamp, stamp),
            )
            nid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    return {"ok": True, "id": nid}


@router.post("/designer/{design_id}/delete")
def designer_delete(request: Request, design_id: int):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        conn.execute("DELETE FROM report_designs WHERE id = ?", (design_id,))
    return RedirectResponse("/designer", status_code=303)


@router.get("/designer/{design_id}/pdf")
def designer_pdf(request: Request, design_id: int, q: str = "", limit: int = 50, record_id: str = ""):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        design = row_to_dict(conn.execute("SELECT * FROM report_designs WHERE id = ?", (design_id,)).fetchone())
        if not design:
            return RedirectResponse("/designer", status_code=303)
        layout = _parse_layout(design.get("layout"))
        cap = 200 if layout.get("mode") == "list" else 80
        rows = fetch_report_rows(
            conn,
            design.get("source") or "members",
            q=q,
            limit=min(max(int(limit or 50), 1), cap),
            record_id=record_id or None,
        )
    data = design_pdf(_parish(), design["name"], layout, rows)
    return pdf_response(data, f"{design['name']}.pdf")
