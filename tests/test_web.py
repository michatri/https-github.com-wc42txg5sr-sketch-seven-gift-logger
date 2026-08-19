from chatriacc.app import create_app
from chatriacc.db import Store


def test_health_and_dashboard(tmp_path):
    app = create_app(tmp_path / "web.db")
    client = app.test_client()
    assert client.get("/health").json["app"] == "chatriACC"
    home = client.get("/")
    assert home.status_code == 200
    assert "chatriACC".encode() in home.data
    assert "วัดนักบุญมาร์โก".encode("utf-8") in home.data


def test_create_rv_via_form(tmp_path):
    app = create_app(tmp_path / "web.db")
    client = app.test_client()
    resp = client.post(
        "/vouchers/new/rv",
        data={
            "officer": "นาย ทดสอบ",
            "reviewer": "คพ.ทดสอบ",
            "date_1": "2025-01-05",
            "detail_1": "ถุงทาน",
            "amount_1": "2865.00",
            "code_1": "4101",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "CRV-001".encode() in resp.data
    assert "สองพันแปดร้อยหกสิบห้าบาทถ้วน".encode("utf-8") in resp.data
    store = Store(tmp_path / "web.db")
    assert store.voucher_count() == 1


def test_ledger_and_pl_pages(tmp_path):
    app = create_app(tmp_path / "web.db")
    client = app.test_client()
    client.post(
        "/vouchers/new/pv",
        data={
            "date_1": "2025-03-01",
            "detail_1": "ค่าไฟฟ้า",
            "amount_1": "100.50",
            "code_1": "5201",
        },
    )
    led = client.get("/ledgers/pv?month=3")
    assert led.status_code == 200
    assert "ค่าไฟฟ้า".encode("utf-8") in led.data
    pl = client.get("/reports/pl")
    assert pl.status_code == 200
    assert "5201".encode() in pl.data
    by_code = client.get("/reports/accounts?code=5201")
    assert by_code.status_code == 200
    assert "รายงานรหัสบัญชี".encode("utf-8") in by_code.data
    assert "5201".encode() in by_code.data
    assert "ค่าไฟฟ้า".encode("utf-8") in by_code.data
    assert "รวมรหัส 5201".encode("utf-8") in by_code.data
    years = client.get("/years")
    assert years.status_code == 200
    assert "เตรียมปี".encode("utf-8") in years.data
    assert "AC25-209.xlsb".encode() in years.data
