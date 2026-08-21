from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from passlib.hash import pbkdf2_sha256

from app import db as dbmod
from scripts.import_mdb import connect, init_schema, seed_user


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "catholic.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db_path)
    import scripts.import_mdb as importer

    monkeypatch.setattr(importer, "DB_PATH", db_path)
    conn = connect()
    init_schema(conn)
    seed_user(conn)
    conn.execute(
        """INSERT INTO parish_settings (id, church_th, church_en, father, id_prefix, religion, sen, prefix)
           VALUES (1, 'วัดทดสอบ', 'Test Church', 'บาทหลวงทดสอบ', '070104-', 'คาทอลิก', 'เรียน', 'คุณ')"""
    )
    conn.execute(
        """INSERT INTO members (id, num, saint_name, first_name, last_name, gang, sex, religion, family_no, birth_date)
           VALUES (1, '070104-1987-B9', 'ยอห์นบอสโก', 'จอมพล', 'แสนสุข', '3A', 'ชาย', 'คาทอลิก', '525', '1982-02-02')"""
    )
    conn.execute(
        """INSERT INTO churches (id, name, gen_name, is_header) VALUES ('070104', 'นักบุญยอแซฟ', 'วัดบ้านโป่ง', 0)"""
    )
    conn.commit()
    conn.close()

    from importlib import reload
    import app.main as mainmod

    reload(mainmod)
    monkeypatch.setattr(mainmod, "get_db", dbmod.get_db)
    with TestClient(mainmod.app) as c:
        yield c


def login(client: TestClient):
    r = client.post("/login", data={"username": "admin", "password": "password", "next": "/"}, follow_redirects=False)
    assert r.status_code == 303


def test_login_required(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_dashboard_after_login(client):
    login(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "จอมพล" in r.text
    assert "วัดทดสอบ" in r.text


def test_member_search(client):
    login(client)
    r = client.get("/members", params={"q": "แสนสุข", "field": "last_name"})
    assert r.status_code == 200
    assert "070104-1987-B9" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.json()["ok"] is True
    assert r.json()["members"] == 1


def test_churches(client):
    login(client)
    r = client.get("/churches")
    assert r.status_code == 200
    assert "นักบุญยอแซฟ" in r.text


def test_pdf_certificate(client):
    login(client)
    r = client.get("/pdf/certificate/1", params={"kind": "all"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    assert "attachment" in r.headers.get("content-disposition", "")


def test_pdf_member_list(client):
    login(client)
    r = client.get("/pdf/list", params={"mode": "summary"})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_reports_page(client):
    login(client)
    r = client.get("/reports")
    assert r.status_code == 200
    assert "ออกรายงาน PDF" in r.text


def test_designer_save_and_pdf(client):
    login(client)
    r = client.get("/designer")
    assert r.status_code == 200
    assert "ออกแบบหน้ารายงาน" in r.text
    payload = {
        "name": "ใบรายชื่อทดสอบ",
        "source": "members",
        "layout": {
            "mode": "list",
            "orientation": "P",
            "header": True,
            "elements": [],
            "columns": [
                {"field": "num", "label": "รหัส", "w": 30},
                {"field": "first_name", "label": "ชื่อ", "w": 40},
                {"field": "last_name", "label": "นามสกุล", "w": 40},
            ],
        },
    }
    saved = client.post("/designer/save", json=payload)
    assert saved.status_code == 200
    assert saved.json()["ok"] is True
    design_id = saved.json()["id"]
    pdf = client.get(f"/designer/{design_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_designer_form_pdf(client):
    login(client)
    payload = {
        "name": "บัตรออกแบบเอง",
        "source": "members",
        "layout": {
            "mode": "form",
            "header": True,
            "orientation": "P",
            "elements": [
                {"id": "e1", "type": "text", "text": "รายงานทดสอบ", "x": 20, "y": 50, "w": 170, "h": 10, "size": 16, "bold": True, "align": "C"},
                {"id": "e2", "type": "field", "field": "_full_name", "label": "ชื่อ", "show_label": True, "x": 20, "y": 65, "w": 170, "h": 8, "size": 12, "align": "L"},
            ],
            "columns": [],
        },
    }
    saved = client.post("/designer/save", json=payload)
    pdf = client.get(f"/designer/{saved.json()['id']}/pdf")
    assert pdf.content.startswith(b"%PDF")
