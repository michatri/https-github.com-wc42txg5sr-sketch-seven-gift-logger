"""Web Report Designer: pages + JSON API. Does not change Catholic data tables."""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import DIOCESES, SEARCH_FIELDS, display_name, get_db, now, row_to_dict, rows_to_dicts, stats, thai_date
from app.pdfs import CERT_TITLES, LIST_TITLES
from app.query_builder import QueryError, execute_dataset
from app.report_engine import default_layout, normalize_layout, pdf_bytes_response, preview_html, render_pdf
from app.report_schema import (
    ensure_report_schema,
    list_objects,
    schema_catalog,
    table_columns,
    table_relationships,
)
from pathlib import Path

log = logging.getLogger("catholic.reports")
USER_ERROR = "ไม่สามารถสร้างรายงานได้ กรุณาตรวจสอบเงื่อนไขของรายงาน"

ROOT = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["thai_date"] = thai_date
templates.env.filters["dname"] = display_name
templates.env.globals["search_fields"] = SEARCH_FIELDS
templates.env.globals["dioceses"] = DIOCESES

router = APIRouter()


def _user(request: Request) -> str | None:
    return request.session.get("user")


def _guard(request: Request):
    if not _user(request):
        nxt = str(request.url.path)
        if request.url.query:
            nxt += "?" + request.url.query
        return RedirectResponse(f"/login?next={nxt}", status_code=303)
    return None


def _is_admin(user: str | None) -> bool:
    return user == "admin"


def _parish() -> dict[str, Any]:
    with get_db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM parish_settings WHERE id = 1").fetchone()) or {}


def _render(request: Request, name: str, **ctx: Any):
    ctx.update(request=request, user=_user(request), parish=_parish(), is_admin=_is_admin(_user(request)))
    return templates.TemplateResponse(request, name, ctx)


def _json_error(status: int = 400, message: str = USER_ERROR, log_detail: str | None = None):
    if log_detail:
        log.warning("report api: %s", log_detail)
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _parse_json(raw: Any, fallback: Any):
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw or ("{}" if isinstance(fallback, dict) else "[]"))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _can(conn: sqlite3.Connection, report: dict, user: str, action: str) -> bool:
    if _is_admin(user):
        return True
    if report.get("created_by") == user:
        return True
    row = conn.execute(
        "SELECT can_view, can_edit, can_print, can_export_pdf FROM report_permissions WHERE report_id=? AND user_id=?",
        (report["id"], user),
    ).fetchone()
    if not row:
        return False
    col = {"view": "can_view", "edit": "can_edit", "print": "can_print", "export": "can_export_pdf"}[action]
    return bool(row[col])


def _report_row(conn: sqlite3.Connection, report_id: int) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone())


def _dataset_row(conn: sqlite3.Connection, dataset_id: int | None) -> dict | None:
    if not dataset_id:
        return None
    return row_to_dict(conn.execute("SELECT * FROM report_datasets WHERE id = ?", (dataset_id,)).fetchone())


def _params_rows(conn: sqlite3.Connection, report_id: int) -> list[dict]:
    rows = rows_to_dicts(conn.execute("SELECT * FROM report_parameters WHERE report_id = ? ORDER BY id", (report_id,)).fetchall())
    for p in rows:
        p["options"] = _parse_json(p.get("options_json"), [])
        p["required"] = bool(p.get("required"))
    return rows


def _snapshot_version(conn: sqlite3.Connection, report: dict, user: str) -> None:
    ds = _dataset_row(conn, report.get("dataset_id"))
    last = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) FROM report_versions WHERE report_id = ?",
        (report["id"],),
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO report_versions (report_id, version_number, layout_json, query_config_json, created_by, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            report["id"],
            int(last) + 1,
            report.get("layout_json") or "{}",
            (ds or {}).get("query_config_json"),
            user,
            now(),
        ),
    )
    conn.execute(
        """DELETE FROM report_versions WHERE report_id=? AND id NOT IN (
             SELECT id FROM report_versions WHERE report_id=? ORDER BY version_number DESC LIMIT 50)""",
        (report["id"], report["id"]),
    )


def _replace_parameters(conn: sqlite3.Connection, report_id: int, items: list[dict] | None) -> None:
    conn.execute("DELETE FROM report_parameters WHERE report_id = ?", (report_id,))
    for item in items or []:
        name = str(item.get("name") or "").strip().lstrip(":")
        if not name:
            continue
        conn.execute(
            """INSERT INTO report_parameters (report_id, name, label, data_type, default_value, required, options_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                report_id,
                name,
                item.get("label") or name,
                item.get("data_type") or "text",
                item.get("default_value"),
                1 if item.get("required") else 0,
                json.dumps(item.get("options") or item.get("options_json") or [], ensure_ascii=False)
                if not isinstance(item.get("options_json"), str)
                else item.get("options_json"),
            ),
        )


def _serialize_report(conn: sqlite3.Connection, report: dict) -> dict:
    ds = _dataset_row(conn, report.get("dataset_id"))
    return {
        "id": report["id"],
        "name": report.get("name"),
        "description": report.get("description") or "",
        "dataset_id": report.get("dataset_id"),
        "layout": _parse_json(report.get("layout_json"), {}),
        "status": report.get("status") or "draft",
        "is_favorite": bool(report.get("is_favorite")),
        "created_by": report.get("created_by"),
        "created_at": report.get("created_at"),
        "updated_by": report.get("updated_by"),
        "updated_at": report.get("updated_at"),
        "dataset": {
            "id": ds["id"],
            "name": ds.get("name"),
            "description": ds.get("description"),
            "data_source_id": ds.get("data_source_id"),
            "query_config": _parse_json(ds.get("query_config_json"), {}),
        }
        if ds
        else None,
        "parameters": _params_rows(conn, report["id"]),
    }


def _readonly_conn():
    from app.db import DB_PATH

    conn = sqlite3.connect(str(DB_PATH), timeout=8)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.Error:
        pass
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


@router.get("/reports", response_class=HTMLResponse)
def reports_list_page(request: Request, scope: str = "all"):
    if (redir := _guard(request)):
        return redir
    return _render(request, "report_list.html", scope=scope)


@router.get("/reports/mine", response_class=HTMLResponse)
def reports_mine(request: Request):
    if (redir := _guard(request)):
        return redir
    return _render(request, "report_list.html", scope="mine")


@router.get("/reports/favorites", response_class=HTMLResponse)
def reports_fav(request: Request):
    if (redir := _guard(request)):
        return redir
    return _render(request, "report_list.html", scope="favorites")


@router.get("/reports/new", response_class=HTMLResponse)
def reports_new(request: Request):
    if (redir := _guard(request)):
        return redir
    return _render(request, "report_wizard.html")


@router.get("/reports/sources", response_class=HTMLResponse)
def reports_sources(request: Request):
    if (redir := _guard(request)):
        return redir
    return _render(request, "report_sources.html")


@router.get("/reports/library", response_class=HTMLResponse)
def reports_library(request: Request):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        s = stats(conn)
        members = rows_to_dicts(
            conn.execute("SELECT id, num, saint_name, first_name, last_name FROM members ORDER BY last_name, first_name").fetchall()
        )
        marriages = rows_to_dicts(
            conn.execute("SELECT id, notify_no, groom, bride FROM marriage_notifies ORDER BY notify_no").fetchall()
        )
        moves = rows_to_dicts(conn.execute("SELECT id, num FROM moves ORDER BY id DESC").fetchall())
    return _render(
        request,
        "reports.html",
        stats=s,
        members=members,
        marriages=marriages,
        moves=moves,
        cert_titles=CERT_TITLES,
        list_titles=LIST_TITLES,
    )


@router.get("/reports/{report_id}/edit", response_class=HTMLResponse)
def reports_edit(request: Request, report_id: int):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, _user(request) or "", "view"):
            return RedirectResponse("/reports", status_code=303)
        payload = _serialize_report(conn, report)
        catalog = schema_catalog(conn)
    return _render(request, "report_designer.html", report_id=report_id, boot=payload, catalog=catalog)


@router.get("/reports/{report_id}/preview", response_class=HTMLResponse)
def reports_preview_page(request: Request, report_id: int):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, _user(request) or "", "view"):
            return RedirectResponse("/reports", status_code=303)
        payload = _serialize_report(conn, report)
    return _render(request, "report_preview.html", report_id=report_id, boot=payload)


@router.get("/reports/{report_id}/print", response_class=HTMLResponse)
def reports_print_page(request: Request, report_id: int):
    if (redir := _guard(request)):
        return redir
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, _user(request) or "", "print"):
            return RedirectResponse("/reports", status_code=303)
        payload = _serialize_report(conn, report)
    return _render(request, "report_print.html", report_id=report_id, boot=payload)


# ---------------------------------------------------------------------------
# Data sources API
# ---------------------------------------------------------------------------


@router.get("/api/data-sources")
def api_data_sources(request: Request):
    if not _user(request):
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        ensure_report_schema(conn)
        items = rows_to_dicts(conn.execute("SELECT * FROM report_data_sources ORDER BY id").fetchall())
    return {"ok": True, "items": items}


@router.get("/api/data-sources/{source_id}/tables")
def api_tables(request: Request, source_id: int):
    if not _user(request):
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        src = row_to_dict(conn.execute("SELECT * FROM report_data_sources WHERE id=?", (source_id,)).fetchone())
        if not src:
            return _json_error(404, "ไม่พบแหล่งข้อมูล")
        catalog = schema_catalog(conn)
    return {"ok": True, "source": src, **catalog}


@router.get("/api/data-sources/{source_id}/tables/{table}/columns")
def api_columns(request: Request, source_id: int, table: str):
    if not _user(request):
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    try:
        with get_db() as conn:
            src = row_to_dict(conn.execute("SELECT * FROM report_data_sources WHERE id=?", (source_id,)).fetchone())
            if not src:
                return _json_error(404, "ไม่พบแหล่งข้อมูล")
            names = {o["name"] for o in list_objects(conn, include_metadata=_is_admin(_user(request)))}
            if table not in names:
                return _json_error(404, "ไม่พบตาราง")
            cols = table_columns(conn, table)
            rels = table_relationships(conn, table)
        return {"ok": True, "table": table, "columns": cols, "relationships": rels}
    except Exception as exc:
        log.exception("columns failed: %s", exc)
        return _json_error(400, log_detail=str(exc))


# ---------------------------------------------------------------------------
# Datasets API
# ---------------------------------------------------------------------------


@router.get("/api/datasets")
def api_datasets(request: Request):
    if not _user(request):
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        items = rows_to_dicts(conn.execute("SELECT * FROM report_datasets ORDER BY updated_at DESC").fetchall())
        for it in items:
            it["query_config"] = _parse_json(it.get("query_config_json"), {})
    return {"ok": True, "items": items}


@router.post("/api/datasets")
async def api_datasets_create(request: Request):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        return _json_error(400, "กรุณาตั้งชื่อชุดข้อมูล")
    stamp = now()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO report_datasets (name, description, data_source_id, query_config_json, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                name,
                body.get("description") or "",
                body.get("data_source_id") or 1,
                json.dumps(body.get("query_config") or {}, ensure_ascii=False),
                user,
                stamp,
                stamp,
            ),
        )
        nid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    return {"ok": True, "id": nid}


@router.get("/api/datasets/{dataset_id}")
def api_dataset_get(request: Request, dataset_id: int):
    if not _user(request):
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        ds = _dataset_row(conn, dataset_id)
    if not ds:
        return _json_error(404, "ไม่พบชุดข้อมูล")
    ds["query_config"] = _parse_json(ds.get("query_config_json"), {})
    return {"ok": True, "item": ds}


@router.put("/api/datasets/{dataset_id}")
async def api_dataset_put(request: Request, dataset_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    with get_db() as conn:
        ds = _dataset_row(conn, dataset_id)
        if not ds:
            return _json_error(404, "ไม่พบชุดข้อมูล")
        if ds.get("created_by") != user and not _is_admin(user):
            return _json_error(403, "ไม่มีสิทธิ์แก้ไขชุดข้อมูล")
        conn.execute(
            """UPDATE report_datasets SET name=?, description=?, data_source_id=?, query_config_json=?, updated_at=? WHERE id=?""",
            (
                str(body.get("name") or ds["name"]),
                body.get("description", ds.get("description")),
                body.get("data_source_id") or ds.get("data_source_id"),
                json.dumps(body.get("query_config") or _parse_json(ds.get("query_config_json"), {}), ensure_ascii=False),
                now(),
                dataset_id,
            ),
        )
    return {"ok": True, "id": dataset_id}


@router.delete("/api/datasets/{dataset_id}")
def api_dataset_delete(request: Request, dataset_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        ds = _dataset_row(conn, dataset_id)
        if not ds:
            return _json_error(404, "ไม่พบชุดข้อมูล")
        if ds.get("created_by") != user and not _is_admin(user):
            return _json_error(403, "ไม่มีสิทธิ์ลบชุดข้อมูล")
        used = conn.execute("SELECT COUNT(*) FROM reports WHERE dataset_id=?", (dataset_id,)).fetchone()[0]
        if used:
            return _json_error(400, "ชุดข้อมูลนี้ถูกใช้ในรายงานอยู่ ไม่สามารถลบได้")
        conn.execute("DELETE FROM report_datasets WHERE id=?", (dataset_id,))
    return {"ok": True}


@router.post("/api/datasets/{dataset_id}/preview")
async def api_dataset_preview(request: Request, dataset_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    try:
        with get_db() as conn:
            ds = _dataset_row(conn, dataset_id)
            if not ds:
                return _json_error(404, "ไม่พบชุดข้อมูล")
            config = body.get("query_config") or _parse_json(ds.get("query_config_json"), {})
        ro = _readonly_conn()
        try:
            result = execute_dataset(
                ro,
                config,
                body.get("parameters") or {},
                page=int(body.get("page") or 1),
                page_size=int(body.get("pageSize") or 20),
                admin_sql=body.get("admin_sql") if _is_admin(user) else None,
                is_admin=_is_admin(user),
            )
        finally:
            ro.close()
        return {"ok": True, **result}
    except QueryError as exc:
        return _json_error(400, exc.message, log_detail=exc.detail)
    except Exception as exc:
        log.exception("dataset preview: %s", exc)
        return _json_error(400)


# ---------------------------------------------------------------------------
# Reports API
# ---------------------------------------------------------------------------


@router.get("/api/reports")
def api_reports_list(
    request: Request,
    q: str = "",
    status: str = "",
    sort: str = "updated_at",
    dir: str = "desc",
    scope: str = "all",
):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    sort_map = {
        "name": "name",
        "updated_at": "updated_at",
        "created_at": "created_at",
        "status": "status",
        "created_by": "created_by",
    }
    col = sort_map.get(sort, "updated_at")
    direction = "ASC" if str(dir).lower() == "asc" else "DESC"
    clauses = ["1=1"]
    params: list[Any] = []
    if q:
        clauses.append("(name LIKE ? OR IFNULL(description,'') LIKE ?)")
        like = f"%{q.strip()}%"
        params.extend([like, like])
    if status:
        clauses.append("status = ?")
        params.append(status)
    if scope == "mine":
        clauses.append("created_by = ?")
        params.append(user)
    if scope == "favorites":
        clauses.append("is_favorite = 1")
    sql = f"SELECT * FROM reports WHERE {' AND '.join(clauses)} ORDER BY {col} {direction}, id DESC"
    with get_db() as conn:
        items = rows_to_dicts(conn.execute(sql, params).fetchall())
        visible = []
        for it in items:
            if _can(conn, it, user, "view"):
                it["is_favorite"] = bool(it.get("is_favorite"))
                visible.append(it)
    return {"ok": True, "items": visible}


@router.post("/api/reports")
async def api_reports_create(request: Request):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        return _json_error(400, "กรุณาตั้งชื่อรายงาน")
    stamp = now()
    layout = normalize_layout(body.get("layout") or default_layout(name, (body.get("query_config") or {}).get("fields")))
    with get_db() as conn:
        dataset_id = body.get("dataset_id")
        if not dataset_id:
            conn.execute(
                """INSERT INTO report_datasets (name, description, data_source_id, query_config_json, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    name,
                    body.get("description") or "",
                    body.get("data_source_id") or 1,
                    json.dumps(body.get("query_config") or {}, ensure_ascii=False),
                    user,
                    stamp,
                    stamp,
                ),
            )
            dataset_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """INSERT INTO reports (name, description, dataset_id, layout_json, status, is_favorite, created_by, created_at, updated_by, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                name,
                body.get("description") or "",
                dataset_id,
                json.dumps(layout, ensure_ascii=False),
                body.get("status") or "draft",
                1 if body.get("is_favorite") else 0,
                user,
                stamp,
                user,
                stamp,
            ),
        )
        rid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        _replace_parameters(conn, rid, body.get("parameters"))
        conn.execute(
            """INSERT INTO report_permissions (report_id, user_id, can_view, can_edit, can_print, can_export_pdf)
               VALUES (?,?,1,1,1,1)""",
            (rid, user),
        )
        report = _report_row(conn, rid)
        _snapshot_version(conn, report, user)
    return {"ok": True, "id": rid}


@router.get("/api/reports/{report_id}")
def api_report_get(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report:
            return _json_error(404, "ไม่พบรายงาน")
        if not _can(conn, report, user, "view"):
            return _json_error(403, "ไม่มีสิทธิ์ดูรายงานนี้")
        return {"ok": True, "item": _serialize_report(conn, report)}


@router.put("/api/reports/{report_id}")
async def api_report_put(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report:
            return _json_error(404, "ไม่พบรายงาน")
        if not _can(conn, report, user, "edit"):
            return _json_error(403, "ไม่มีสิทธิ์แก้ไขรายงานนี้")
        layout = body.get("layout")
        layout_json = json.dumps(normalize_layout(layout), ensure_ascii=False) if layout is not None else report["layout_json"]
        conn.execute(
            """UPDATE reports SET name=?, description=?, layout_json=?, status=?, is_favorite=?, updated_by=?, updated_at=? WHERE id=?""",
            (
                str(body.get("name") or report["name"]).strip(),
                body.get("description", report.get("description")),
                layout_json,
                body.get("status") or report.get("status") or "draft",
                1 if body.get("is_favorite", report.get("is_favorite")) else 0,
                user,
                now(),
                report_id,
            ),
        )
        if body.get("query_config") is not None and report.get("dataset_id"):
            conn.execute(
                "UPDATE report_datasets SET query_config_json=?, updated_at=? WHERE id=?",
                (json.dumps(body["query_config"], ensure_ascii=False), now(), report["dataset_id"]),
            )
        if "parameters" in body:
            _replace_parameters(conn, report_id, body.get("parameters"))
        if body.get("permissions") and _is_admin(user):
            conn.execute("DELETE FROM report_permissions WHERE report_id=?", (report_id,))
            for perm in body["permissions"]:
                conn.execute(
                    """INSERT INTO report_permissions (report_id, user_id, can_view, can_edit, can_print, can_export_pdf)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        report_id,
                        perm.get("user_id"),
                        1 if perm.get("can_view", True) else 0,
                        1 if perm.get("can_edit") else 0,
                        1 if perm.get("can_print", True) else 0,
                        1 if perm.get("can_export_pdf", True) else 0,
                    ),
                )
        updated = _report_row(conn, report_id)
        if body.get("snapshot"):
            _snapshot_version(conn, updated, user)
        return {"ok": True, "item": _serialize_report(conn, updated)}


@router.delete("/api/reports/{report_id}")
def api_report_delete(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report:
            return _json_error(404, "ไม่พบรายงาน")
        if not _can(conn, report, user, "edit"):
            return _json_error(403, "ไม่มีสิทธิ์ลบรายงานนี้")
        conn.execute("DELETE FROM report_parameters WHERE report_id=?", (report_id,))
        conn.execute("DELETE FROM report_permissions WHERE report_id=?", (report_id,))
        conn.execute("DELETE FROM report_versions WHERE report_id=?", (report_id,))
        conn.execute("DELETE FROM reports WHERE id=?", (report_id,))
    return {"ok": True}


def _run_report(conn_meta: sqlite3.Connection, report: dict, body: dict, user: str) -> dict:
    ds = _dataset_row(conn_meta, report.get("dataset_id"))
    if not ds:
        raise QueryError("ยังไม่ได้กำหนดชุดข้อมูล")
    config = body.get("query_config") or _parse_json(ds.get("query_config_json"), {})
    layout = normalize_layout(body.get("layout") or _parse_json(report.get("layout_json"), {}))
    params = body.get("parameters") or {}
    ro = _readonly_conn()
    try:
        result = execute_dataset(
            ro,
            config,
            params,
            page=int(body.get("page") or 1),
            page_size=int(body.get("pageSize") or 50),
            admin_sql=body.get("admin_sql") if _is_admin(user) else None,
            is_admin=_is_admin(user),
        )
    finally:
        ro.close()
    html = preview_html(
        layout,
        result["rows"],
        title=report.get("name") or "",
        page=result["page"],
        total=result["total"],
        page_size=result["pageSize"],
        status="ok" if result["rows"] else "empty",
        message="" if result["rows"] else "ไม่มีข้อมูลตามเงื่อนไขที่เลือก",
    )
    return {**result, "html": html, "layout": layout}


@router.post("/api/reports/{report_id}/preview")
async def api_report_preview(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json() if (request.headers.get("content-length") not in (None, "0")) else {}
    try:
        with get_db() as conn:
            report = _report_row(conn, report_id)
            if not report:
                return _json_error(404, "ไม่พบรายงาน")
            if not _can(conn, report, user, "view"):
                return _json_error(403, "ไม่มีสิทธิ์ดูรายงานนี้")
            result = _run_report(conn, report, body or {}, user)
        status = "success" if result["rows"] else "empty"
        return {"ok": True, "status": status, **result}
    except QueryError as exc:
        return JSONResponse(
            {"ok": False, "status": "error", "error": exc.message, "html": preview_html({}, [], status="error", message=exc.message)},
            status_code=400,
        )
    except Exception as exc:
        log.exception("preview failed: %s", exc)
        return JSONResponse(
            {"ok": False, "status": "error", "error": USER_ERROR, "html": preview_html({}, [], status="error", message=USER_ERROR)},
            status_code=400,
        )


@router.post("/api/reports/{report_id}/pdf")
async def api_report_pdf(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json() if (request.headers.get("content-length") not in (None, "0")) else {}
    try:
        with get_db() as conn:
            report = _report_row(conn, report_id)
            if not report:
                return _json_error(404, "ไม่พบรายงาน")
            if not _can(conn, report, user, "export"):
                return _json_error(403, "ไม่มีสิทธิ์ส่งออก PDF")
            ds = _dataset_row(conn, report.get("dataset_id"))
            config = (body or {}).get("query_config") or _parse_json((ds or {}).get("query_config_json"), {})
            layout = normalize_layout((body or {}).get("layout") or _parse_json(report.get("layout_json"), {}))
            parish = row_to_dict(conn.execute("SELECT * FROM parish_settings WHERE id=1").fetchone()) or {}
        ro = _readonly_conn()
        try:
            result = execute_dataset(
                ro,
                config,
                (body or {}).get("parameters") or {},
                page=1,
                page_size=int((body or {}).get("pageSize") or 500),
            )
        finally:
            ro.close()
        data = render_pdf(parish, report.get("name") or "รายงาน", layout, result["rows"])
        return pdf_bytes_response(data, f"{report.get('name') or 'report'}.pdf")
    except QueryError as exc:
        return _json_error(400, exc.message, log_detail=exc.detail)
    except Exception as exc:
        log.exception("pdf failed: %s", exc)
        return _json_error(400)


@router.post("/api/reports/{report_id}/print")
async def api_report_print(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report:
            return _json_error(404, "ไม่พบรายงาน")
        if not _can(conn, report, user, "print"):
            return _json_error(403, "ไม่มีสิทธิ์พิมพ์รายงานนี้")
    return {"ok": True, "printUrl": f"/reports/{report_id}/print"}


@router.post("/api/reports/{report_id}/duplicate")
def api_report_dup(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    stamp = now()
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, user, "view"):
            return _json_error(404, "ไม่พบรายงาน")
        ds = _dataset_row(conn, report.get("dataset_id"))
        dataset_id = None
        if ds:
            conn.execute(
                """INSERT INTO report_datasets (name, description, data_source_id, query_config_json, created_by, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (f"{ds.get('name')} (สำเนา)", ds.get("description"), ds.get("data_source_id"), ds.get("query_config_json"), user, stamp, stamp),
            )
            dataset_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """INSERT INTO reports (name, description, dataset_id, layout_json, status, is_favorite, created_by, created_at, updated_by, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                f"{report.get('name')} (สำเนา)",
                report.get("description"),
                dataset_id,
                report.get("layout_json"),
                "draft",
                0,
                user,
                stamp,
                user,
                stamp,
            ),
        )
        nid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        for p in _params_rows(conn, report_id):
            conn.execute(
                """INSERT INTO report_parameters (report_id, name, label, data_type, default_value, required, options_json)
                   VALUES (?,?,?,?,?,?,?)""",
                (nid, p["name"], p.get("label"), p.get("data_type"), p.get("default_value"), p.get("required") or 0, p.get("options_json")),
            )
        conn.execute(
            """INSERT INTO report_permissions (report_id, user_id, can_view, can_edit, can_print, can_export_pdf)
               VALUES (?,?,1,1,1,1)""",
            (nid, user),
        )
        _snapshot_version(conn, _report_row(conn, nid), user)
    return {"ok": True, "id": nid}


@router.get("/api/reports/{report_id}/versions")
def api_versions(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, user, "view"):
            return _json_error(404, "ไม่พบรายงาน")
        items = rows_to_dicts(
            conn.execute(
                "SELECT id, report_id, version_number, created_by, created_at FROM report_versions WHERE report_id=? ORDER BY version_number DESC",
                (report_id,),
            ).fetchall()
        )
    return {"ok": True, "items": items}


@router.post("/api/reports/{report_id}/restore-version")
async def api_restore(request: Request, report_id: int):
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    vid = int(body.get("version_id") or body.get("id") or 0)
    with get_db() as conn:
        report = _report_row(conn, report_id)
        if not report or not _can(conn, report, user, "edit"):
            return _json_error(403, "ไม่มีสิทธิ์กู้คืนเวอร์ชัน")
        ver = row_to_dict(
            conn.execute("SELECT * FROM report_versions WHERE id=? AND report_id=?", (vid, report_id)).fetchone()
        )
        if not ver:
            return _json_error(404, "ไม่พบเวอร์ชัน")
        conn.execute(
            "UPDATE reports SET layout_json=?, updated_by=?, updated_at=? WHERE id=?",
            (ver["layout_json"], user, now(), report_id),
        )
        if ver.get("query_config_json") and report.get("dataset_id"):
            conn.execute(
                "UPDATE report_datasets SET query_config_json=?, updated_at=? WHERE id=?",
                (ver["query_config_json"], now(), report["dataset_id"]),
            )
        _snapshot_version(conn, _report_row(conn, report_id), user)
    return {"ok": True}


@router.post("/api/query/preview")
async def api_query_preview(request: Request):
    """Wizard live preview without a saved dataset."""
    user = _user(request)
    if not user:
        return _json_error(401, "กรุณาเข้าสู่ระบบ")
    body = await request.json()
    try:
        ro = _readonly_conn()
        try:
            result = execute_dataset(
                ro,
                body.get("query_config") or {},
                body.get("parameters") or {},
                page=int(body.get("page") or 1),
                page_size=int(body.get("pageSize") or 20),
                admin_sql=body.get("admin_sql") if _is_admin(user) else None,
                is_admin=_is_admin(user),
            )
        finally:
            ro.close()
        layout = normalize_layout(body.get("layout") or default_layout("ตัวอย่าง", (body.get("query_config") or {}).get("fields")))
        html = preview_html(layout, result["rows"], title="ตัวอย่าง", page=result["page"], total=result["total"], page_size=result["pageSize"])
        return {"ok": True, "status": "success" if result["rows"] else "empty", "html": html, **result}
    except QueryError as exc:
        return _json_error(400, exc.message, log_detail=exc.detail)
    except Exception as exc:
        log.exception("query preview: %s", exc)
        return _json_error(400)
