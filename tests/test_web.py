def test_dashboard_ok(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "รายรับ-รายจ่าย".encode("utf-8") in response.data


def test_create_payslip_via_form(client):
    response = client.post(
        "/payslips",
        data={
            "pay_date": "2026-08-31",
            "period_month": "8",
            "period_year": "2026",
            "employee_name": "สมชาย",
            "employee_id": "E1",
            "company_name": "ABC",
            "notes": "",
            "income_category_id": "",
            "income_description": "เงินเดือน",
            "income_amount": "30,000.00",
            "expense_category_id": "",
            "expense_description": "ประกันสังคม",
            "expense_amount": "750.00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "สมชาย".encode("utf-8") in response.data
    assert "฿30,000.00".encode("utf-8") in response.data
    assert "฿750.00".encode("utf-8") in response.data


def test_manual_transaction_and_daily_summary(client):
    client.post(
        "/transactions",
        data={
            "txn_date": "2026-08-18",
            "kind": "expense",
            "category_id": "",
            "new_category": "ค่ากาแฟ",
            "description": "กาแฟเช้า",
            "amount": "45",
        },
        follow_redirects=True,
    )
    response = client.get("/summary/daily?year=2026&month=8")
    assert response.status_code == 200
    assert "2026-08-18".encode("utf-8") in response.data
    assert "฿45.00".encode("utf-8") in response.data

    monthly = client.get("/summary/monthly?year=2026")
    assert monthly.status_code == 200
    assert "สิงหาคม 2026".encode("utf-8") in monthly.data

    yearly = client.get("/summary/yearly")
    assert yearly.status_code == 200
    assert "ปี 2026".encode("utf-8") in yearly.data
