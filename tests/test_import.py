from chatriacc.importer import SEED_XLSB, _collect_vouchers, import_xlsb
from chatriacc.db import Store


def test_group_rv_lines_and_cancelled_code():
    rows = [
        {},
        {8: "CRV-ID-6", 9: "Detail-7"},
        {
            7: 45658,
            8: 1,
            9: "ถุงทาน",
            10: 2865,
            11: 4101,
            13: "(นาย ทดสอบ)",
            14: "(คพ.ทดสอบ)",
            15: 2025,
        },
        {
            7: 45658,
            8: 1,
            9: "ขอมิสซา",
            10: 1400,
            11: 4121,
            13: "(นาย ทดสอบ)",
            14: "(คพ.ทดสอบ)",
            15: 2025,
        },
        {
            7: 45660,
            8: 2,
            9: "เงินบริจาค",
            10: 100,
            11: "X",
            13: "(นาย ทดสอบ)",
            14: "(คพ.ทดสอบ)",
            15: 2025,
            22: 4111,
            23: 45790,
        },
    ]
    vouchers = _collect_vouchers(rows, "rv")
    assert len(vouchers) == 2
    assert len(vouchers[0]["lines"]) == 2
    assert vouchers[0]["number"] == 1
    assert vouchers[1]["cancelled"] is True
    assert vouchers[1]["lines"][0]["account_code"] == 4111


def test_import_grouped_vouchers_into_store(tmp_path):
    store = Store(tmp_path / "imp.db")
    rows = [
        {},
        {},
        {
            7: 45658,
            8: 3,
            9: "ถุงทาน",
            10: 500,
            11: 4101,
            13: "ผู้ลง",
            14: "เจ้าอาวาส",
            15: 2025,
        },
    ]
    for voucher in _collect_vouchers(rows, "rv"):
        store.create_voucher(
            kind="rv",
            lines=voucher["lines"],
            officer=voucher["officer"],
            reviewer=voucher["reviewer"],
            year=voucher["year"],
            number=voucher["number"],
        )
    found = store.find_voucher("rv", 3, 2025)
    assert found is not None
    assert found["total"] == 50000


def test_seed_xlsb_matches_excel_year_totals(tmp_path):
    if not SEED_XLSB.exists():
        return
    store = Store(tmp_path / "seed.db")
    result = import_xlsb(store, SEED_XLSB, replace=True)
    assert result["rv"] == 60
    assert result["pv"] == 371
    assert result["skipped"] == 0
    totals = store.year_totals(2025)
    assert totals["income_total"] == 418088811
    assert totals["expense_total"] == 571097337
    assert store.next_number("rv", 2025) == 61
    assert store.next_number("pv", 2025) == 372
    years = {row["year"]: row for row in store.list_years()}
    assert 2025 in years
    assert years[2025]["file_name"].endswith(".xlsb")


def test_ensure_seed_imported_fills_empty_db(tmp_path):
    from chatriacc.importer import ensure_seed_imported

    if not SEED_XLSB.exists():
        return
    store = Store(tmp_path / "auto-seed.db")
    first = ensure_seed_imported(store)
    assert first is not None
    assert first["created"] == first["rv"] + first["pv"]
    assert store.voucher_count() == first["created"]
    second = ensure_seed_imported(store)
    assert second is None
    assert store.voucher_count() == first["created"]
