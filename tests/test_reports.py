from __future__ import annotations

from app.query_builder import QueryError, compile_query, load_schema_map, validate_admin_sql


def login(client):
    r = client.post("/login", data={"username": "admin", "password": "password", "next": "/"}, follow_redirects=False)
    assert r.status_code == 303


def test_reports_list_page(client):
    login(client)
    r = client.get("/reports")
    assert r.status_code == 200
    assert "รายงานทั้งหมด" in r.text
    assert "สร้างรายงาน" in r.text


def test_reports_library_page(client):
    login(client)
    r = client.get("/reports/library")
    assert r.status_code == 200
    assert "ออกรายงาน PDF" in r.text


def test_data_sources_dynamic_schema(client):
    login(client)
    src = client.get("/api/data-sources")
    assert src.status_code == 200
    items = src.json()["items"]
    assert items
    sid = items[0]["id"]
    tables = client.get(f"/api/data-sources/{sid}/tables")
    names = {t["name"] for t in tables.json()["tables"]}
    assert "members" in names
    assert "marriage_notifies" in names
    assert "churches" in names
    assert "users" not in names
    cols = client.get(f"/api/data-sources/{sid}/tables/members/columns")
    col_names = {c["name"] for c in cols.json()["columns"]}
    assert "first_name" in col_names
    assert "btsm_date" in col_names
    assert "family_no" in col_names
    assert "password_hash" not in col_names


def test_query_builder_rejects_writes(client):
    login(client)
    from app import db as dbmod

    with dbmod.get_db() as conn:
        schema = load_schema_map(conn)
    try:
        compile_query({"mainTable": "members;DROP", "fields": [{"column": "id"}]}, schema)
        assert False, "should reject"
    except QueryError:
        pass
    try:
        compile_query(
            {"mainTable": "members", "fields": [{"table": "users", "column": "password_hash"}]},
            schema,
        )
        assert False, "should reject secret column"
    except QueryError:
        pass
    try:
        validate_admin_sql("INSERT INTO members (id) VALUES (9)")
        assert False, "should reject insert"
    except QueryError:
        pass
    try:
        validate_admin_sql("SELECT * FROM members; DROP TABLE members")
        assert False, "should reject multi"
    except QueryError:
        pass


def test_create_preview_pdf_duplicate_version(client):
    login(client)
    payload = {
        "name": "รายงานทะเบียนสมรส",
        "description": "ตัวอย่าง",
        "query_config": {
            "mainTable": "members",
            "fields": [
                {"table": "members", "column": "first_name", "alias": "first_name", "label": "ชื่อ"},
                {"table": "members", "column": "last_name", "alias": "last_name", "label": "นามสกุล"},
                {"table": "members", "column": "birth_date", "alias": "birth_date", "label": "วันเกิด"},
            ],
            "filters": [
                {"field": "members.birth_date", "op": "gte", "param": "start_date"},
            ],
            "orderBy": [{"field": "members.last_name", "dir": "ASC"}],
            "limit": 50,
        },
        "parameters": [
            {"name": "start_date", "label": "วันที่เริ่มต้น", "data_type": "date", "default_value": "1900-01-01"}
        ],
        "status": "published",
    }
    created = client.post("/api/reports", json=payload)
    assert created.status_code == 200, created.text
    rid = created.json()["id"]

    listed = client.get("/api/reports", params={"q": "สมรส"})
    assert listed.status_code == 200
    assert any(it["id"] == rid for it in listed.json()["items"])

    prev = client.post(f"/api/reports/{rid}/preview", json={"page": 1, "pageSize": 10})
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert body["ok"] is True
    assert body["total"] >= 1
    assert "จอมพล" in body["html"]

    pdf = client.post(f"/api/reports/{rid}/pdf", json={})
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    dup = client.post(f"/api/reports/{rid}/duplicate")
    assert dup.status_code == 200
    assert dup.json()["id"] != rid

    vers = client.get(f"/api/reports/{rid}/versions")
    assert vers.status_code == 200
    assert vers.json()["items"]

    saved = client.put(
        f"/api/reports/{rid}",
        json={"name": "รายงานทะเบียนสมรส", "layout": {"version": 1, "page": {"size": "A4"}}, "snapshot": True},
    )
    assert saved.status_code == 200
    vid = vers.json()["items"][0]["id"]
    rest = client.post(f"/api/reports/{rid}/restore-version", json={"version_id": vid})
    assert rest.status_code == 200

    fav = client.put(f"/api/reports/{rid}", json={"is_favorite": True})
    assert fav.json()["item"]["is_favorite"] is True
    mine = client.get("/api/reports", params={"scope": "favorites"})
    assert any(it["id"] == rid for it in mine.json()["items"])

    wizard = client.get("/reports/new")
    assert wizard.status_code == 200
    assert "เลือกแหล่งข้อมูล" in wizard.text or "สร้างรายงาน" in wizard.text

    designer = client.get(f"/reports/{rid}/edit")
    assert designer.status_code == 200
    assert "คุณสมบัติ" in designer.text

    deleted = client.delete(f"/api/reports/{rid}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/reports/{rid}")
    assert missing.status_code == 404


def test_join_is_opt_in(client):
    login(client)
    from app import db as dbmod
    from app.query_builder import compile_query, load_schema_map

    with dbmod.get_db() as conn:
        schema = load_schema_map(conn)
        sql, _ = compile_query(
            {
                "mainTable": "moves",
                "fields": [{"table": "moves", "column": "num", "alias": "num"}],
                "joins": [
                    {
                        "table": "members",
                        "type": "LEFT",
                        "left": "moves.member_id",
                        "right": "members.id",
                    }
                ],
            },
            schema,
        )
    assert "LEFT JOIN" in sql
    assert "members" in sql


def test_print_endpoint(client):
    login(client)
    created = client.post(
        "/api/reports",
        json={
            "name": "พิมพ์ทดสอบ",
            "query_config": {
                "mainTable": "members",
                "fields": [{"table": "members", "column": "first_name", "alias": "first_name"}],
            },
        },
    )
    rid = created.json()["id"]
    r = client.post(f"/api/reports/{rid}/print")
    assert r.json()["printUrl"] == f"/reports/{rid}/print"
    page = client.get(f"/reports/{rid}/print")
    assert page.status_code == 200


def test_existing_designer_still_works(client):
    login(client)
    r = client.get("/designer")
    assert r.status_code == 200
    assert "ออกแบบหน้ารายงาน" in r.text
