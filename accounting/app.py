"""Flask web app for payslip income/expense accounting."""

from __future__ import annotations

import os
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from accounting import db as store
from accounting.money import MoneyError, format_baht, parse_baht

THAI_MONTHS = [
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    root = Path(__file__).resolve().parent.parent
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("ACCOUNTING_SECRET", "dev-accounting-secret"),
        DATABASE=os.environ.get("ACCOUNTING_DB", str(root / "data" / "accounting.db")),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(store.close_db)

    with app.app_context():
        store.init_db()

    app.jinja_env.filters["baht"] = format_baht
    app.jinja_env.globals["thai_months"] = THAI_MONTHS
    app.jinja_env.globals["current_year"] = date.today().year

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        return {"ok": True, "service": "accounting"}, 200

    @app.get("/")
    def dashboard():
        today = date.today().isoformat()
        month_start = date.today().replace(day=1).isoformat()
        year_start = date.today().replace(month=1, day=1).isoformat()
        cards = {
            "today": store.totals(start=today, end=today),
            "month": store.totals(start=month_start, end=today),
            "year": store.totals(start=year_start, end=today),
            "all": store.totals(),
        }
        recent = store.list_transactions()[:12]
        monthly = list(reversed(store.monthly_summary(date.today().year)))
        breakdown = store.category_breakdown(start=year_start, end=today)
        return render_template(
            "dashboard.html",
            cards=cards,
            recent=recent,
            monthly=monthly,
            breakdown=breakdown,
            today=today,
        )

    @app.get("/payslips")
    def payslip_list():
        return render_template("payslip_list.html", payslips=store.list_payslips())

    @app.get("/payslips/new")
    def payslip_new():
        today = date.today()
        return render_template(
            "payslip_form.html",
            slip=None,
            income_categories=store.categories("income", payslip_only=True),
            expense_categories=store.categories("expense", payslip_only=True),
            default_date=today.isoformat(),
            default_month=today.month,
            default_year=today.year,
        )

    @app.get("/payslips/<int:payslip_id>")
    def payslip_detail(payslip_id: int):
        slip = store.fetch_payslip(payslip_id)
        if slip is None:
            flash("ไม่พบสลิปเงินเดือน", "error")
            return redirect(url_for("payslip_list"))
        return render_template("payslip_detail.html", slip=slip)

    @app.get("/payslips/<int:payslip_id>/edit")
    def payslip_edit(payslip_id: int):
        slip = store.fetch_payslip(payslip_id)
        if slip is None:
            flash("ไม่พบสลิปเงินเดือน", "error")
            return redirect(url_for("payslip_list"))
        return render_template(
            "payslip_form.html",
            slip=slip,
            income_categories=store.categories("income", payslip_only=True),
            expense_categories=store.categories("expense", payslip_only=True),
            default_date=slip["pay_date"],
            default_month=slip["period_month"],
            default_year=slip["period_year"],
        )

    @app.post("/payslips")
    def payslip_create():
        return _save_payslip_from_form()

    @app.post("/payslips/<int:payslip_id>")
    def payslip_update(payslip_id: int):
        return _save_payslip_from_form(payslip_id)

    @app.post("/payslips/<int:payslip_id>/delete")
    def payslip_delete(payslip_id: int):
        store.delete_payslip(payslip_id)
        flash("ลบสลิปเงินเดือนแล้ว รายรับ-รายจ่ายที่ผูกกับสลิปถูกลบด้วย", "success")
        return redirect(url_for("payslip_list"))

    @app.get("/transactions")
    def transaction_list():
        start = request.args.get("start") or ""
        end = request.args.get("end") or ""
        kind = request.args.get("kind") or ""
        rows = store.list_transactions(start=start or None, end=end or None, kind=kind or None)
        total = store.totals(start=start or None, end=end or None)
        if kind in ("income", "expense"):
            other = "expense" if kind == "income" else "income"
            total = {**total, other: 0, "net": total[kind] if kind == "income" else -total[kind]}
        return render_template(
            "transactions.html",
            rows=rows,
            total=total,
            start=start,
            end=end,
            kind=kind,
            income_categories=store.categories("income"),
            expense_categories=store.categories("expense"),
            form_date=date.today().isoformat(),
        )

    @app.post("/transactions")
    def transaction_create():
        try:
            amount = parse_baht(request.form.get("amount"))
            kind = request.form.get("kind") or "expense"
            category_id = _category_from_form(kind)
            store.save_manual_transaction(
                txn_date=request.form.get("txn_date") or "",
                kind=kind,
                category_id=category_id,
                description=request.form.get("description") or "",
                amount_satang=amount,
            )
            flash("บันทึกรายการแล้ว", "success")
        except (MoneyError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("transaction_list"))

    @app.post("/transactions/<int:txn_id>/delete")
    def transaction_delete(txn_id: int):
        try:
            store.delete_transaction(txn_id)
            flash("ลบรายการแล้ว", "success")
        except ValueError as exc:
            flash(str(exc), "error")
        return redirect(url_for("transaction_list"))

    @app.get("/summary/daily")
    def summary_daily():
        today = date.today()
        year = _int_arg("year", today.year)
        month = _int_arg("month", today.month)
        rows = store.daily_summary(year=year, month=month)
        start, end = _month_bounds(year, month)
        total = store.totals(start=start, end=end)
        return render_template(
            "summary.html",
            title="สรุปรายรับ-รายจ่ายรายวัน",
            period_label=f"{THAI_MONTHS[month]} {year}",
            mode="daily",
            rows=rows,
            total=total,
            year=year,
            month=month,
            years=_year_choices(year),
            chart_rows=list(reversed(rows)),
        )

    @app.get("/summary/monthly")
    def summary_monthly():
        today = date.today()
        year = _int_arg("year", today.year)
        rows = store.monthly_summary(year=year)
        start = f"{year:04d}-01-01"
        end = f"{year:04d}-12-31"
        total = store.totals(start=start, end=end)
        labeled = []
        for row in rows:
            month = int(row["period"].split("-")[1])
            labeled.append({**row, "label": f"{THAI_MONTHS[month]} {year}"})
        return render_template(
            "summary.html",
            title="สรุปรายรับ-รายจ่ายรายเดือน",
            period_label=f"ปี {year}",
            mode="monthly",
            rows=labeled,
            total=total,
            year=year,
            month=None,
            years=_year_choices(year),
            chart_rows=list(reversed(labeled)),
        )

    @app.get("/summary/yearly")
    def summary_yearly():
        rows = store.yearly_summary()
        labeled = [{**row, "label": f"ปี {row['period']}"} for row in rows]
        total = store.totals()
        return render_template(
            "summary.html",
            title="สรุปรายรับ-รายจ่ายรายปี",
            period_label="ทุกปี",
            mode="yearly",
            rows=labeled,
            total=total,
            year=None,
            month=None,
            years=_year_choices(date.today().year),
            chart_rows=list(reversed(labeled)),
        )


def _year_choices(selected: int) -> list[int]:
    years = set(store.available_years())
    years.add(selected)
    years.add(date.today().year)
    return sorted(years, reverse=True)


def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1).isoformat(), date(year, month, last_day).isoformat()


def _category_from_form(kind: str, prefix: str = "") -> int | None:
    new_name = (request.form.get(f"{prefix}new_category") or "").strip()
    if new_name:
        return store.get_or_create_category(new_name, kind)
    raw = request.form.get(f"{prefix}category_id") or ""
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _collect_lines(kind: str) -> list[dict]:
    descriptions = request.form.getlist(f"{kind}_description")
    amounts = request.form.getlist(f"{kind}_amount")
    category_ids = request.form.getlist(f"{kind}_category_id")
    lines = []
    for idx, description in enumerate(descriptions):
        amount_text = amounts[idx] if idx < len(amounts) else ""
        if not str(amount_text).strip() and not str(description).strip():
            continue
        amount = parse_baht(amount_text)
        if amount <= 0:
            continue
        category_id = None
        if idx < len(category_ids) and category_ids[idx]:
            try:
                category_id = int(category_ids[idx])
            except ValueError:
                category_id = None
        cat_name = ""
        if category_id:
            for cat in store.categories(kind):
                if cat["id"] == category_id:
                    cat_name = cat["name"]
                    break
        lines.append(
            {
                "description": description.strip() or cat_name or ("รายรับ" if kind == "income" else "รายจ่าย"),
                "amount_satang": amount,
                "category_id": category_id,
                "category_name": cat_name,
            }
        )
    return lines


def _save_payslip_from_form(payslip_id: int | None = None):
    try:
        period_month = int(request.form.get("period_month") or 0)
        period_year = int(request.form.get("period_year") or 0)
        pay_date = request.form.get("pay_date") or ""
        datetime.strptime(pay_date, "%Y-%m-%d")
        if not (1 <= period_month <= 12) or period_year < 2000:
            raise ValueError("รอบเดือน/ปี ของสลิปไม่ถูกต้อง")
        income_lines = _collect_lines("income")
        expense_lines = _collect_lines("expense")
        slip_id = store.save_payslip(
            pay_date=pay_date,
            period_month=period_month,
            period_year=period_year,
            employee_name=request.form.get("employee_name") or "",
            employee_id=request.form.get("employee_id") or "",
            company_name=request.form.get("company_name") or "",
            notes=request.form.get("notes") or "",
            income_lines=income_lines,
            expense_lines=expense_lines,
            payslip_id=payslip_id,
        )
        flash("บันทึกสลิปเงินเดือน และลงรายรับ-รายจ่ายแล้ว", "success")
        return redirect(url_for("payslip_detail", payslip_id=slip_id))
    except (MoneyError, ValueError) as exc:
        flash(str(exc), "error")
        if payslip_id:
            return redirect(url_for("payslip_edit", payslip_id=payslip_id))
        return redirect(url_for("payslip_new"))
