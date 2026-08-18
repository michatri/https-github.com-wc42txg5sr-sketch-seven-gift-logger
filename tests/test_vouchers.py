from chatriacc.db import Store


def _line(date="2025-01-15", detail="ถุงทาน", amount=286500, code=4101, bank=0):
    return {
        "txn_date": date,
        "detail": detail,
        "amount_satang": amount,
        "account_code": code,
        "bank_flag": bank,
    }


def test_create_and_number_rv(tmp_path):
    store = Store(tmp_path / "t.db")
    vid = store.create_voucher("rv", [_line()], officer="ผู้ลง", reviewer="เจ้าอาวาส")
    data = store.get_voucher(vid)
    assert data["voucher"]["number"] == 1
    assert data["total"] == 286500
    assert store.next_number("rv", 2025) == 2


def test_incomplete_line_rejected(tmp_path):
    store = Store(tmp_path / "t.db")
    try:
        store.create_voucher("rv", [{"txn_date": "2025-01-01", "detail": "ถุงทาน", "amount_satang": 100, "account_code": None}])
        assert False, "should fail"
    except ValueError as exc:
        assert "ไม่ครบ" in str(exc)


def test_cancel_cannot_restore(tmp_path):
    store = Store(tmp_path / "t.db")
    vid = store.create_voucher("rv", [_line(), _line("2025-01-15", "ขอมิสซา", 140000, 4121)])
    store.cancel_voucher(vid)
    data = store.get_voucher(vid)
    assert data["voucher"]["cancelled"] == 1
    try:
        store.cancel_voucher(vid)
        assert False, "second cancel should fail"
    except ValueError as exc:
        assert "ยกเลิกแล้ว" in str(exc)
    totals = store.year_totals(2025)
    assert totals["income_total"] == 0


def test_pl_groups_by_account_and_month(tmp_path):
    store = Store(tmp_path / "t.db")
    store.create_voucher("rv", [_line("2025-01-02", "ถุงทาน", 10000, 4101)])
    store.create_voucher("pv", [_line("2025-03-10", "ค่าน้ำ", 2500, 5211)])
    totals = store.year_totals(2025)
    assert totals["income"][4101][1] == 10000
    assert totals["expense"][5211][3] == 2500
    assert totals["net"] == 7500


def test_seven_line_limit(tmp_path):
    store = Store(tmp_path / "t.db")
    lines = [_line(detail=f"รายการ {i}") for i in range(8)]
    try:
        store.create_voucher("rv", lines)
        assert False
    except ValueError as exc:
        assert "7" in str(exc)
