from accounting.db import daily_summary, monthly_summary, save_manual_transaction, save_payslip, yearly_summary


def test_daily_monthly_yearly_summaries(app_ctx):
    save_payslip(
        pay_date="2026-08-15",
        period_month=8,
        period_year=2026,
        employee_name="A",
        employee_id="",
        company_name="",
        notes="",
        income_lines=[{"description": "เงินเดือน", "amount_satang": 100000, "category_id": None}],
        expense_lines=[{"description": "ภาษี", "amount_satang": 10000, "category_id": None}],
    )
    save_manual_transaction(
        txn_date="2026-08-15",
        kind="expense",
        category_id=None,
        description="ค่าอาหาร",
        amount_satang=5000,
    )
    save_manual_transaction(
        txn_date="2026-09-01",
        kind="income",
        category_id=None,
        description="รายได้อื่น",
        amount_satang=20000,
    )
    save_manual_transaction(
        txn_date="2025-12-31",
        kind="expense",
        category_id=None,
        description="ปีก่อน",
        amount_satang=3000,
    )

    daily = {row["period"]: row for row in daily_summary(2026, 8)}
    assert daily["2026-08-15"]["income"] == 100000
    assert daily["2026-08-15"]["expense"] == 15000
    assert daily["2026-08-15"]["net"] == 85000

    monthly = {row["period"]: row for row in monthly_summary(2026)}
    assert monthly["2026-08"]["net"] == 85000
    assert monthly["2026-09"]["income"] == 20000
    assert "2025-12" not in monthly

    yearly = {row["period"]: row for row in yearly_summary()}
    assert yearly["2026"]["income"] == 120000
    assert yearly["2026"]["expense"] == 15000
    assert yearly["2025"]["expense"] == 3000
