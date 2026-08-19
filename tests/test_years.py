from chatriacc.db import Store
from chatriacc.years import ac_filename, parse_ac_filename


def test_parse_ac_filename():
    assert parse_ac_filename("AC25-209.xlsb") == {
        "year": 2025,
        "church_id": "209",
        "filename": "AC25-209.xlsb",
    }
    assert parse_ac_filename("AC26-209_Nopass.xlsb")["year"] == 2026
    assert parse_ac_filename("random.xlsx")["year"] is None
    assert ac_filename(2026, "209") == "AC26-209.xlsb"
    assert ac_filename(2025, 209) == "AC25-209.xlsb"


def test_prepare_year_keeps_previous_year(tmp_path):
    store = Store(tmp_path / "years.db")
    store.create_voucher(
        "rv",
        [
            {
                "txn_date": "2025-01-05",
                "detail": "ถุงทาน",
                "amount_satang": 10000,
                "account_code": 4101,
            }
        ],
        year=2025,
    )
    info = store.prepare_year(2026)
    assert info["expected_file"] == "AC26-209.xlsb"
    assert store.fiscal_year() == 2026
    assert store.next_number("rv", 2026) == 1
    assert store.next_number("pv", 2026) == 1
    assert store.voucher_count(2025) == 1
    assert store.voucher_count(2026) == 0
    years = {row["year"]: row for row in store.list_years()}
    assert 2025 in years and 2026 in years
    assert years[2026]["active"] is True
    store.select_year(2025)
    assert store.fiscal_year() == 2025
    assert store.voucher_count(2025) == 1
