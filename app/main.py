from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import pbkdf2_sha256
from starlette.middleware.sessions import SessionMiddleware

from app.db import (
    MEMBER_FIELDS,
    SEARCH_FIELDS,
    DIOCESES,
    diocese_name,
    display_name,
    get_db,
    next_member_id,
    now,
    row_to_dict,
    rows_to_dicts,
    search_members,
    stats,
    thai_date,
    today,
)
from app.pdfs import (
    CERT_TITLES,
    LIST_TITLES,
    certificate_pdf,
    churches_pdf,
    envelope_pdf,
    id_card_pdf,
    list_pdf,
    marriage_pdf,
    member_record_pdf,
    move_pdf,
    pdf_response,
)

from app.designer import router as designer_router
from app.reports import router as reports_router

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads" / "photos"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Catholic ID Web", version="4.5")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("CATHOLIC_SECRET", "catholic-id-web-change-me"),
    session_cookie="catholicid",
    max_age=60 * 60 * 12,
)
app.include_router(reports_router)
app.include_router(designer_router)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/photos", StaticFiles(directory=UPLOADS), name="photos")
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["thai_date"] = thai_date
templates.env.filters["dname"] = display_name
templates.env.globals["search_fields"] = SEARCH_FIELDS
templates.env.globals["dioceses"] = DIOCESES


def current_user(request: Request) -> str | None:
    return request.session.get("user")


def require_login(request: Request) -> RedirectResponse | None:
    if not current_user(request):
        nxt = str(request.url.path)
        if request.url.query:
            nxt += "?" + request.url.query
        return RedirectResponse(f"/login?next={nxt}", status_code=303)
    return None


def render(request: Request, name: str, **ctx: Any) -> HTMLResponse:
    ctx.update(request=request, user=current_user(request), parish=get_parish())
    return templates.TemplateResponse(request, name, ctx)


def get_parish() -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM parish_settings WHERE id = 1").fetchone()
        return row_to_dict(row) or {}


def form_member(form) -> dict[str, Any]:
    data = {}
    for field in MEMBER_FIELDS:
        value = form.get(field)
        if value is not None:
            value = value.strip()
        data[field] = value or None
    data["updated_at"] = today()
    return data


def save_photo(member_id: int, photo: UploadFile | None) -> None:
    if not photo or not photo.filename:
        return
    suffix = Path(photo.filename).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".jpg"
    dest = UPLOADS / f"{member_id}{suffix}"
    for old in UPLOADS.glob(f"{member_id}.*"):
        old.unlink(missing_ok=True)
    with dest.open("wb") as fh:
        shutil.copyfileobj(photo.file, fh)


def photo_url(member_id: int) -> str | None:
    for p in UPLOADS.glob(f"{member_id}.*"):
        return f"/photos/{p.name}"
    return None


def photo_file(member_id: int) -> Path | None:
    for p in UPLOADS.glob(f"{member_id}.*"):
        return p
    return None


def sorted_members(items: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "saint":
        items.sort(key=lambda m: ((m.get("saint_name") or "ไม่ระบุ"), m.get("last_name") or ""))
    elif mode == "gang":
        items.sort(key=lambda m: ((m.get("gang") or "ไม่ระบุ"), m.get("last_name") or ""))
    elif mode == "num":
        items.sort(key=lambda m: m.get("num") or "")
    elif mode == "family":
        items.sort(key=lambda m: ((m.get("family_no") or m.get("from_family") or ""), m.get("birth_date") or ""))
    return items


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if current_user(request):
        return RedirectResponse(next or "/", status_code=303)
    return render(request, "login.html", next=next, error=None)


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/")):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    user = row_to_dict(row)
    if not user or not pbkdf2_sha256.verify(password, user["password_hash"]):
        return render(request, "login.html", next=next, error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    request.session["user"] = user["username"]
    request.session["display"] = user["display_name"]
    return RedirectResponse(next or "/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        s = stats(conn)
        recent = rows_to_dicts(
            conn.execute("SELECT * FROM members ORDER BY updated_at DESC, id DESC LIMIT 8").fetchall()
        )
        gangs = rows_to_dicts(
            conn.execute(
                "SELECT gang, COUNT(*) AS n FROM members WHERE gang IS NOT NULL AND gang != '' GROUP BY gang ORDER BY gang"
            ).fetchall()
        )
    return render(request, "dashboard.html", stats=s, recent=recent, gangs=gangs)


@app.get("/members", response_class=HTMLResponse)
def members_page(
    request: Request,
    q: str = "",
    field: str = "name",
    extra: str = "",
    sort: str = "name",
):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        items = search_members(conn, q, field, extra)
        gangs = [r[0] for r in conn.execute("SELECT DISTINCT gang FROM members WHERE gang IS NOT NULL AND gang != '' ORDER BY gang")]
    if sort == "num":
        items.sort(key=lambda m: m.get("num") or "")
    elif sort == "saint":
        items.sort(key=lambda m: ((m.get("saint_name") or ""), m.get("last_name") or ""))
    elif sort == "gang":
        items.sort(key=lambda m: ((m.get("gang") or ""), m.get("last_name") or ""))
    elif sort == "family":
        items.sort(key=lambda m: ((m.get("family_no") or m.get("from_family") or ""), m.get("birth_date") or ""))
    return render(
        request,
        "members.html",
        items=items,
        q=q,
        field=field,
        extra=extra,
        sort=sort,
        gangs=gangs,
        count=len(items),
    )


@app.get("/members/new", response_class=HTMLResponse)
def member_new(request: Request, copy_from: int | None = None):
    if (redir := require_login(request)):
        return redir
    member: dict[str, Any] = {"religion": "คาทอลิก", "go_church": get_parish().get("church1") or get_parish().get("church_th")}
    if copy_from:
        with get_db() as conn:
            src = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (copy_from,)).fetchone())
        if src:
            member.update(
                {
                    "address1": src.get("address1"),
                    "address2": src.get("address2"),
                    "tel": src.get("tel"),
                    "gang": src.get("gang"),
                    "go_church": src.get("go_church"),
                    "from_family": src.get("from_family") or src.get("family_no"),
                    "family_no": src.get("family_no"),
                    "religion": src.get("religion") or "คาทอลิก",
                }
            )
    with get_db() as conn:
        churches = rows_to_dicts(conn.execute("SELECT id, name, gen_name FROM churches WHERE is_header = 0 ORDER BY id").fetchall())
    return render(request, "member_form.html", member=member, churches=churches, is_new=True, photo=None)


@app.post("/members/new")
async def member_create(request: Request, photo: UploadFile = File(None)):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    data = form_member(form)
    with get_db() as conn:
        mid = next_member_id(conn)
        cols = ["id", "updated_at"] + MEMBER_FIELDS
        values = [mid, today()] + [data.get(f) for f in MEMBER_FIELDS]
        conn.execute(
            f"INSERT INTO members ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})",
            values,
        )
    save_photo(mid, photo)
    return RedirectResponse(f"/members/{mid}", status_code=303)


@app.get("/members/{member_id}", response_class=HTMLResponse)
def member_detail(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
        if not member:
            return RedirectResponse("/members", status_code=303)
        family_key = member.get("family_no") or member.get("from_family")
        family = []
        if family_key:
            family = rows_to_dicts(
                conn.execute(
                    """SELECT * FROM members WHERE id != ? AND (family_no = ? OR from_family = ?)
                       ORDER BY birth_date""",
                    (member_id, family_key, family_key),
                ).fetchall()
            )
        moves = rows_to_dicts(
            conn.execute("SELECT * FROM moves WHERE member_id = ? ORDER BY id DESC", (member_id,)).fetchall()
        )
        marriages = rows_to_dicts(
            conn.execute(
                "SELECT * FROM marriage_notifies WHERE groom LIKE ? OR bride LIKE ? ORDER BY id DESC",
                (f"%{member.get('first_name') or ''}%", f"%{member.get('first_name') or ''}%"),
            ).fetchall()
        )
    return render(
        request,
        "member_detail.html",
        member=member,
        family=family,
        moves=moves,
        marriages=marriages,
        photo=photo_url(member_id),
        full_name=display_name(member),
    )


@app.get("/members/{member_id}/edit", response_class=HTMLResponse)
def member_edit(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
        churches = rows_to_dicts(conn.execute("SELECT id, name, gen_name FROM churches WHERE is_header = 0 ORDER BY id").fetchall())
    if not member:
        return RedirectResponse("/members", status_code=303)
    return render(request, "member_form.html", member=member, churches=churches, is_new=False, photo=photo_url(member_id))


@app.post("/members/{member_id}/edit")
async def member_update(request: Request, member_id: int, photo: UploadFile = File(None)):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    data = form_member(form)
    with get_db() as conn:
        sets = ", ".join(f"{f} = ?" for f in MEMBER_FIELDS + ["updated_at"])
        values = [data.get(f) for f in MEMBER_FIELDS] + [today(), member_id]
        conn.execute(f"UPDATE members SET {sets} WHERE id = ?", values)
    save_photo(member_id, photo)
    return RedirectResponse(f"/members/{member_id}", status_code=303)


@app.post("/members/{member_id}/delete")
def member_delete(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        conn.execute("DELETE FROM moves WHERE member_id = ?", (member_id,))
        conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    for old in UPLOADS.glob(f"{member_id}.*"):
        old.unlink(missing_ok=True)
    return RedirectResponse("/members", status_code=303)


@app.get("/churches", response_class=HTMLResponse)
def churches_page(request: Request, q: str = "", diocese: str = ""):
    if (redir := require_login(request)):
        return redir
    clauses = ["1=1"]
    params: list[Any] = []
    if q:
        clauses.append("(id LIKE ? OR name LIKE ? OR gen_name LIKE ? OR address1 LIKE ? OR address2 LIKE ?)")
        like = f"%{q}%"
        params.extend([like] * 5)
    if diocese:
        clauses.append("id LIKE ?")
        params.append(f"{diocese}%")
    with get_db() as conn:
        items = rows_to_dicts(
            conn.execute(
                f"SELECT * FROM churches WHERE {' AND '.join(clauses)} ORDER BY id",
                params,
            ).fetchall()
        )
    for item in items:
        item["diocese"] = diocese_name(item["id"])
    return render(request, "churches.html", items=items, q=q, diocese=diocese, count=len(items))


@app.get("/churches/{church_id}", response_class=HTMLResponse)
def church_detail(request: Request, church_id: str):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        church = row_to_dict(conn.execute("SELECT * FROM churches WHERE id = ?", (church_id,)).fetchone())
    if not church:
        return RedirectResponse("/churches", status_code=303)
    church["diocese"] = diocese_name(church["id"])
    return render(request, "church_form.html", church=church)


@app.post("/churches/{church_id}")
async def church_update(request: Request, church_id: str):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    with get_db() as conn:
        conn.execute(
            """UPDATE churches SET name=?, gen_name=?, address1=?, address2=?, tel=?, minister=?, asst1=?, asst2=?, asst3=?
               WHERE id=?""",
            (
                form.get("name") or None,
                form.get("gen_name") or None,
                form.get("address1") or None,
                form.get("address2") or None,
                form.get("tel") or None,
                form.get("minister") or None,
                form.get("asst1") or None,
                form.get("asst2") or None,
                form.get("asst3") or None,
                church_id,
            ),
        )
    return RedirectResponse("/churches", status_code=303)


@app.get("/marriages", response_class=HTMLResponse)
def marriages_page(request: Request, q: str = "", field: str = "groom"):
    if (redir := require_login(request)):
        return redir
    mapping = {
        "groom": "groom LIKE ?",
        "bride": "bride LIKE ?",
        "notify_no": "CAST(notify_no AS TEXT) LIKE ?",
        "marriage_id": "marriage_id LIKE ?",
        "witness": "(witness1 LIKE ? OR witness2 LIKE ?)",
        "priest": "priest LIKE ?",
    }
    sql = "SELECT * FROM marriage_notifies"
    params: list[Any] = []
    if q:
        part = mapping.get(field, "groom LIKE ?")
        sql += " WHERE " + part
        like = f"%{q}%"
        params.extend([like] * part.count("?"))
    sql += " ORDER BY notify_no, id"
    with get_db() as conn:
        items = rows_to_dicts(conn.execute(sql, params).fetchall())
    return render(request, "marriages.html", items=items, q=q, field=field, count=len(items))


@app.get("/marriages/new", response_class=HTMLResponse)
def marriage_new(request: Request, member_id: int | None = None):
    if (redir := require_login(request)):
        return redir
    item: dict[str, Any] = {}
    if member_id:
        with get_db() as conn:
            m = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
        if m:
            if (m.get("sex") or "").find("หญิง") >= 0:
                item.update(
                    {
                        "bride": display_name(m),
                        "br_religion": m.get("religion"),
                        "br_bap_place": m.get("btsm_wat"),
                        "br_bap_date": m.get("btsm_date"),
                        "br_bap_no": m.get("btsm_no"),
                        "bride_fr": " ".join(p for p in [m.get("papa_st"), m.get("papa_nm")] if p),
                        "br_fr_religion": m.get("papa_relig"),
                        "bride_mo": " ".join(p for p in [m.get("mama_st"), m.get("mama_nm")] if p),
                        "br_mo_religion": m.get("mama_relig"),
                    }
                )
            else:
                item.update(
                    {
                        "groom": display_name(m),
                        "gr_religion": m.get("religion"),
                        "gr_bap_place": m.get("btsm_wat"),
                        "gr_bap_date": m.get("btsm_date"),
                        "gr_bap_no": m.get("btsm_no"),
                        "groom_fr": " ".join(p for p in [m.get("papa_st"), m.get("papa_nm")] if p),
                        "gr_fr_religion": m.get("papa_relig"),
                        "groom_mo": " ".join(p for p in [m.get("mama_st"), m.get("mama_nm")] if p),
                        "gr_mo_religion": m.get("mama_relig"),
                    }
                )
            item["marriage_id"] = m.get("mtmn_no")
            item["marriage_date"] = m.get("mtmn_date")
            item["witness1"] = " ".join(p for p in [m.get("mtmn_father_st"), m.get("mtmn_father")] if p)
            item["witness2"] = " ".join(p for p in [m.get("mtmn_mother_st"), m.get("mtmn_mother")] if p)
            item["priest"] = m.get("mtmn_priest")
            item["member_id"] = member_id
    return render(request, "marriage_form.html", item=item, is_new=True)


@app.post("/marriages/new")
async def marriage_create(request: Request):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    fields = [
        "notify_no", "marriage_id", "marriage_date", "groom", "gr_religion", "gr_bap_place", "gr_bap_date",
        "gr_bap_no", "groom_fr", "gr_fr_religion", "groom_mo", "gr_mo_religion", "bride", "br_religion",
        "br_bap_place", "br_bap_date", "br_bap_no", "bride_fr", "br_fr_religion", "bride_mo", "br_mo_religion",
        "witness1", "witness2", "priest", "certify_by", "certify_date", "notify_to", "return_date", "return_by",
        "member_id",
    ]
    values = []
    for f in fields:
        v = (form.get(f) or "").strip() or None
        if f in ("notify_no", "member_id") and v:
            v = int(v)
        values.append(v)
    with get_db() as conn:
        if values[0] is None:
            nxt = conn.execute("SELECT COALESCE(MAX(notify_no), 0) + 1 FROM marriage_notifies").fetchone()[0]
            values[0] = nxt
        conn.execute(
            f"INSERT INTO marriage_notifies ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})",
            values,
        )
        nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return RedirectResponse(f"/marriages/{nid}/print", status_code=303)


@app.get("/marriages/{notify_id}", response_class=HTMLResponse)
def marriage_edit(request: Request, notify_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM marriage_notifies WHERE id = ?", (notify_id,)).fetchone())
    if not item:
        return RedirectResponse("/marriages", status_code=303)
    return render(request, "marriage_form.html", item=item, is_new=False)


@app.post("/marriages/{notify_id}")
async def marriage_update(request: Request, notify_id: int):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    fields = [
        "notify_no", "marriage_id", "marriage_date", "groom", "gr_religion", "gr_bap_place", "gr_bap_date",
        "gr_bap_no", "groom_fr", "gr_fr_religion", "groom_mo", "gr_mo_religion", "bride", "br_religion",
        "br_bap_place", "br_bap_date", "br_bap_no", "bride_fr", "br_fr_religion", "bride_mo", "br_mo_religion",
        "witness1", "witness2", "priest", "certify_by", "certify_date", "notify_to", "return_date", "return_by",
    ]
    values = [(form.get(f) or "").strip() or None for f in fields]
    if values[0]:
        values[0] = int(values[0])
    with get_db() as conn:
        conn.execute(
            f"UPDATE marriage_notifies SET {', '.join(f+'=?' for f in fields)} WHERE id=?",
            values + [notify_id],
        )
    return RedirectResponse("/marriages", status_code=303)


@app.post("/marriages/{notify_id}/delete")
def marriage_delete(request: Request, notify_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        conn.execute("DELETE FROM marriage_notifies WHERE id = ?", (notify_id,))
    return RedirectResponse("/marriages", status_code=303)


@app.get("/moves", response_class=HTMLResponse)
def moves_page(request: Request, q: str = ""):
    if (redir := require_login(request)):
        return redir
    sql = """SELECT moves.*, members.first_name, members.last_name, members.saint_name
             FROM moves LEFT JOIN members ON members.id = moves.member_id"""
    params: list[Any] = []
    if q:
        sql += " WHERE moves.num LIKE ? OR from_church LIKE ? OR to_church LIKE ? OR members.first_name LIKE ? OR members.last_name LIKE ?"
        like = f"%{q}%"
        params = [like] * 5
    sql += " ORDER BY moves.id DESC"
    with get_db() as conn:
        items = rows_to_dicts(conn.execute(sql, params).fetchall())
    return render(request, "moves.html", items=items, q=q, count=len(items))


@app.get("/moves/new", response_class=HTMLResponse)
def move_new(request: Request, member_id: int | None = None):
    if (redir := require_login(request)):
        return redir
    member = None
    if member_id:
        with get_db() as conn:
            member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    item = {"member_id": member_id, "num": (member or {}).get("num"), "date_in": today()}
    return render(request, "move_form.html", item=item, member=member, is_new=True)


@app.post("/moves/new")
async def move_create(request: Request):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    fields = [
        "num", "date_in", "move_in_by", "from_church", "move_from_no", "from_fr",
        "date_out", "move_out_by", "to_church", "move_to_no", "receive_in_by", "member_id",
    ]
    values = []
    for f in fields:
        v = (form.get(f) or "").strip() or None
        if f == "member_id" and v:
            v = int(v)
        values.append(v)
    with get_db() as conn:
        conn.execute(
            f"INSERT INTO moves ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})",
            values,
        )
        mid = values[-1]
        if mid and values[1]:
            conn.execute(
                "UPDATE members SET date_in = COALESCE(date_in, ?), from_church = COALESCE(from_church, ?) WHERE id = ?",
                (values[1], values[3], mid),
            )
        if mid and values[6]:
            conn.execute(
                "UPDATE members SET date_out = ?, to_church = ? WHERE id = ?",
                (values[6], values[8], mid),
            )
        nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return RedirectResponse(f"/moves/{nid}/print", status_code=303)


@app.get("/moves/{move_id}", response_class=HTMLResponse)
def move_edit(request: Request, move_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM moves WHERE id = ?", (move_id,)).fetchone())
        member = None
        if item and item.get("member_id"):
            member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (item["member_id"],)).fetchone())
    if not item:
        return RedirectResponse("/moves", status_code=303)
    return render(request, "move_form.html", item=item, member=member, is_new=False)


@app.post("/moves/{move_id}")
async def move_update(request: Request, move_id: int):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    fields = [
        "num", "date_in", "move_in_by", "from_church", "move_from_no", "from_fr",
        "date_out", "move_out_by", "to_church", "move_to_no", "receive_in_by", "member_id",
    ]
    values = []
    for f in fields:
        v = (form.get(f) or "").strip() or None
        if f == "member_id" and v:
            v = int(v)
        values.append(v)
    with get_db() as conn:
        conn.execute(
            f"UPDATE moves SET {', '.join(f+'=?' for f in fields)} WHERE id=?",
            values + [move_id],
        )
    return RedirectResponse("/moves", status_code=303)


@app.post("/moves/{move_id}/delete")
def move_delete(request: Request, move_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        conn.execute("DELETE FROM moves WHERE id = ?", (move_id,))
    return RedirectResponse("/moves", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    if (redir := require_login(request)):
        return redir
    return render(request, "settings.html")


@app.post("/settings")
async def settings_save(request: Request):
    if (redir := require_login(request)):
        return redir
    form = await request.form()
    fields = [
        "church_th", "church_en", "addr_th", "addr_en", "father", "id_prefix",
        "religion", "province", "church1", "church2", "church3", "sen", "prefix",
    ]
    values = [(form.get(f) or "").strip() or None for f in fields]
    with get_db() as conn:
        conn.execute(
            f"UPDATE parish_settings SET {', '.join(f+'=?' for f in fields)} WHERE id=1",
            values,
        )
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.get("/print/id/{member_id}", response_class=HTMLResponse)
def print_id(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    return render(request, "print_id.html", member=member, photo=photo_url(member_id), full_name=display_name(member))


@app.get("/print/certificate/{member_id}", response_class=HTMLResponse)
def print_certificate(request: Request, member_id: int, kind: str = "baptism"):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    titles = CERT_TITLES
    return render(
        request,
        "print_certificate.html",
        member=member,
        kind=kind,
        title=titles.get(kind, titles["all"]),
        full_name=display_name(member),
        issued=today(),
    )


@app.get("/print/list", response_class=HTMLResponse)
def print_list(
    request: Request,
    q: str = "",
    field: str = "name",
    extra: str = "",
    sort: str = "name",
    mode: str = "alpha",
):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        items = search_members(conn, q, field, extra)
    titles = LIST_TITLES
    items = sorted_members(items, mode)
    with get_db() as conn:
        s = stats(conn)
    return render(
        request,
        "print_list.html",
        items=items,
        mode=mode,
        title=titles.get(mode, titles["alpha"]),
        stats=s,
        q=q,
        field=field,
        extra=extra,
    )


@app.get("/print/envelope/{member_id}", response_class=HTMLResponse)
def print_envelope(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    return render(request, "print_envelope.html", member=member, full_name=display_name(member))


@app.get("/marriages/{notify_id}/print", response_class=HTMLResponse)
def print_marriage(request: Request, notify_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM marriage_notifies WHERE id = ?", (notify_id,)).fetchone())
    if not item:
        return RedirectResponse("/marriages", status_code=303)
    return render(request, "print_marriage.html", item=item)


@app.get("/moves/{move_id}/print", response_class=HTMLResponse)
def print_move(request: Request, move_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM moves WHERE id = ?", (move_id,)).fetchone())
        member = None
        if item and item.get("member_id"):
            member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (item["member_id"],)).fetchone())
    if not item:
        return RedirectResponse("/moves", status_code=303)
    return render(request, "print_move.html", item=item, member=member, full_name=display_name(member))


@app.get("/pdf/id/{member_id}")
def pdf_id(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    data = id_card_pdf(get_parish(), member, photo_file(member_id))
    return pdf_response(data, f"บัตรประจำตัว-{display_name(member)}.pdf")


@app.get("/pdf/certificate/{member_id}")
def pdf_certificate(request: Request, member_id: int, kind: str = "baptism"):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    data = certificate_pdf(get_parish(), member, kind, today())
    title = CERT_TITLES.get(kind, CERT_TITLES["all"])
    return pdf_response(data, f"{title}-{display_name(member)}.pdf")


@app.get("/pdf/member/{member_id}")
def pdf_member(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    data = member_record_pdf(get_parish(), member)
    return pdf_response(data, f"ประวัติ-{display_name(member)}.pdf")


@app.get("/pdf/list")
def pdf_list(request: Request, q: str = "", field: str = "name", extra: str = "", mode: str = "alpha"):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        items = sorted_members(search_members(conn, q, field, extra), mode)
        s = stats(conn)
    data = list_pdf(get_parish(), items, mode, s)
    return pdf_response(data, f"{LIST_TITLES.get(mode, 'รายชื่อ')}.pdf")


@app.get("/pdf/envelope/{member_id}")
def pdf_envelope(request: Request, member_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone())
    if not member:
        return RedirectResponse("/members", status_code=303)
    data = envelope_pdf(get_parish(), member)
    return pdf_response(data, f"จ่าหน้าซอง-{display_name(member)}.pdf")


@app.get("/pdf/marriage/{notify_id}")
def pdf_marriage(request: Request, notify_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM marriage_notifies WHERE id = ?", (notify_id,)).fetchone())
    if not item:
        return RedirectResponse("/marriages", status_code=303)
    data = marriage_pdf(get_parish(), item)
    return pdf_response(data, f"ใบแจ้งสมรส-{item.get('notify_no') or notify_id}.pdf")


@app.get("/pdf/move/{move_id}")
def pdf_move(request: Request, move_id: int):
    if (redir := require_login(request)):
        return redir
    with get_db() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM moves WHERE id = ?", (move_id,)).fetchone())
        member = None
        if item and item.get("member_id"):
            member = row_to_dict(conn.execute("SELECT * FROM members WHERE id = ?", (item["member_id"],)).fetchone())
    if not item:
        return RedirectResponse("/moves", status_code=303)
    data = move_pdf(get_parish(), item, member)
    return pdf_response(data, f"เอกสารย้าย-{item.get('num') or move_id}.pdf")


@app.get("/pdf/churches")
def pdf_churches(request: Request, q: str = "", diocese: str = ""):
    if (redir := require_login(request)):
        return redir
    clauses = ["1=1"]
    params: list[Any] = []
    if q:
        clauses.append("(id LIKE ? OR name LIKE ? OR gen_name LIKE ? OR address1 LIKE ? OR address2 LIKE ?)")
        like = f"%{q}%"
        params.extend([like] * 5)
    if diocese:
        clauses.append("id LIKE ?")
        params.append(f"{diocese}%")
    with get_db() as conn:
        items = rows_to_dicts(
            conn.execute(f"SELECT * FROM churches WHERE {' AND '.join(clauses)} ORDER BY id", params).fetchall()
        )
    data = churches_pdf(get_parish(), items)
    return pdf_response(data, "รายชื่อวัดคาทอลิก.pdf")


@app.get("/health")
def health():
    with get_db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    return {"ok": True, "members": n}


def list_query(**kwargs: Any) -> str:
    return urlencode({k: v for k, v in kwargs.items() if v})


templates.env.globals["list_query"] = list_query
