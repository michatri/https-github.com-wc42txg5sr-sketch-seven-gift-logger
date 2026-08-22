from __future__ import annotations

from fastapi.testclient import TestClient


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
    assert "เพิ่มสัตบุรุษ" in r.text
    assert "แก้ไข" in r.text
    assert "ลบ" in r.text


def test_member_create_edit_delete(client):
    login(client)
    created = client.post(
        "/members/new",
        data={
            "first_name": "มารีอา",
            "last_name": "ทดสอบ",
            "saint_name": "มารีย์",
            "sex": "หญิง",
            "religion": "คาทอลิก",
            "num": "070104-2026-B1",
            "gang": "1A",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    loc = created.headers["location"]
    assert loc.startswith("/members/")
    member_id = loc.split("/")[2].split("?")[0]

    detail = client.get(f"/members/{member_id}")
    assert "มารีอา" in detail.text
    assert "แก้ไข" in detail.text
    assert "ลบ" in detail.text

    edited = client.post(
        f"/members/{member_id}/edit",
        data={
            "first_name": "มารีอา",
            "last_name": "แก้ไขแล้ว",
            "saint_name": "มารีย์",
            "sex": "หญิง",
            "religion": "คาทอลิก",
            "num": "070104-2026-B1",
            "gang": "1A",
        },
        follow_redirects=False,
    )
    assert edited.status_code == 303
    after = client.get(f"/members/{member_id}")
    assert "แก้ไขแล้ว" in after.text

    listed = client.get("/members")
    assert "มารีอา" in listed.text
    assert f"/members/{member_id}/edit" in listed.text
    assert f"/members/{member_id}/delete" in listed.text

    deleted = client.post(f"/members/{member_id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    gone = client.get(deleted.headers["location"])
    assert "มารีอา" not in gone.text
    assert "ลบรายการออกจากทะเบียนแล้ว" in gone.text


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
    assert "รายงานทั้งหมด" in r.text


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
