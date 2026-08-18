from accounting.db import (
    delete_payslip,
    fetch_payslip,
    list_transactions,
    save_payslip,
    totals,
)


def _sample_slip(**kwargs):
    payload = {
        "pay_date": "2026-08-31",
        "period_month": 8,
        "period_year": 2026,
        "employee_name": "สมชาย ใจดี",
        "employee_id": "E001",
        "company_name": "บริษัท ตัวอย่าง จำกัด",
        "notes": "สลิปเดือนสิงหาคม",
        "income_lines": [
            {"description": "เงินเดือน", "amount_satang": 3000000, "category_id": None},
            {"description": "ค่าล่วงเวลา", "amount_satang": 250000, "category_id": None},
        ],
        "expense_lines": [
            {"description": "ภาษี", "amount_satang": 150000, "category_id": None},
            {"description": "ประกันสังคม", "amount_satang": 75000, "category_id": None},
        ],
    }
    payload.update(kwargs)
    return payload


def test_save_payslip_posts_income_and_expense(app_ctx):
    slip_id = save_payslip(**_sample_slip())
    slip = fetch_payslip(slip_id)
    assert slip["income_total"] == 3250000
    assert slip["expense_total"] == 225000
    assert slip["net"] == 3025000

    txns = list_transactions()
    assert len(txns) == 4
    assert {row["kind"] for row in txns} == {"income", "expense"}
    assert all(row["source"] == "payslip" for row in txns)
    assert totals() == {"income": 3250000, "expense": 225000, "net": 3025000}


def test_update_payslip_replaces_ledger_rows(app_ctx):
    slip_id = save_payslip(**_sample_slip())
    save_payslip(
        **_sample_slip(
            payslip_id=slip_id,
            income_lines=[{"description": "เงินเดือน", "amount_satang": 2000000, "category_id": None}],
            expense_lines=[],
        )
    )
    slip = fetch_payslip(slip_id)
    assert slip["income_total"] == 2000000
    assert slip["expense_total"] == 0
    assert len(list_transactions()) == 1


def test_delete_payslip_removes_transactions(app_ctx):
    slip_id = save_payslip(**_sample_slip())
    delete_payslip(slip_id)
    assert fetch_payslip(slip_id) is None
    assert list_transactions() == []


def test_payslip_requires_income(app_ctx):
    try:
        save_payslip(**_sample_slip(income_lines=[]))
        assert False, "should have failed"
    except ValueError as exc:
        assert "รายรับ" in str(exc)
