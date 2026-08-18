from io import BytesIO

from PIL import Image


def _png_bytes() -> bytes:
    image = Image.new("RGB", (80, 80), color=(20, 90, 80))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_capture_page_ok(client):
    response = client.get("/bank-slips/new")
    assert response.status_code == 200
    assert "ถ่ายรูปจากกล้องมือถือ".encode("utf-8") in response.data
    assert b'capture="environment"' in response.data


def test_upload_bank_slip_creates_ledger(client, monkeypatch):
    monkeypatch.setattr(
        "accounting.app.read_slip_image",
        lambda path: (
            "กสิกรไทย\nโอนเงินสำเร็จ\nจำนวนเงิน 750.00 บาท\n18/08/2569",
            "mock-ocr",
        ),
    )
    response = client.post(
        "/bank-slips",
        data={"image": (BytesIO(_png_bytes()), "slip.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "750.00".encode("utf-8") in response.data
    assert "กสิกรไทย".encode("utf-8") in response.data

    posted = client.post(
        "/bank-slips/1",
        data={
            "txn_date": "2026-08-18",
            "kind": "expense",
            "amount": "750.00",
            "bank_name": "กสิกรไทย",
            "reference_no": "ABC",
            "description": "สลิปโอนเงิน กสิกรไทย",
            "category_id": "",
        },
        follow_redirects=True,
    )
    assert posted.status_code == 200
    assert "สลิปโอนเงิน".encode("utf-8") in posted.data
    assert "฿750.00".encode("utf-8") in posted.data


def test_rejects_non_image(client):
    response = client.post(
        "/bank-slips",
        data={"image": (BytesIO(b"not-an-image"), "note.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "ไม่ใช่รูปภาพ".encode("utf-8") in response.data
