from accounting.ocr import parse_bank_slip_text


def test_parse_kbank_expense_slip():
    text = """
    กสิกรไทย
    K PLUS
    โอนเงินสำเร็จ
    จำนวนเงิน
    1,500.00 บาท
    วันที่ทำรายการ 18/08/2569
    เลขที่อ้างอิง 20260818111
    """
    guess = parse_bank_slip_text(text)
    assert guess.bank_name == "กสิกรไทย"
    assert guess.amount_satang == 150000
    assert guess.txn_date == "2026-08-18"
    assert guess.kind == "expense"
    assert guess.reference == "20260818111"


def test_parse_incoming_transfer():
    text = """
    SCB EASY
    ไทยพาณิชย์
    เงินเข้า
    จำนวน 2,000.50
    01 ก.ย. 2568
    """
    guess = parse_bank_slip_text(text)
    assert guess.bank_name == "ไทยพาณิชย์"
    assert guess.amount_satang == 200050
    assert guess.txn_date == "2025-09-01"
    assert guess.kind == "income"


def test_parse_empty_text():
    guess = parse_bank_slip_text("  ")
    assert guess.amount_satang is None
    assert guess.notes
