"""Flask web UI for chatriACC."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from .dates import THAI_MONTHS, buddhist_year, iso_date, thai_date, today, year_label
from .db import Store
from .importer import SEED_XLSB, ensure_seed_imported, import_xlsb
from .money import baht_text, baht_to_satang, format_baht
from .years import ac_filename, parse_ac_filename

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path(os.environ.get("CHATRIACC_DB", ROOT / "data" / "chatriacc.db"))
DEFAULT_HOST = os.environ.get("CHATRIACC_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("CHATRIACC_PORT", "8100"))


def create_app(db_path: str | Path | None = None) -> Flask:
    app = Flask(
        "chatriacc",
        template_folder="templates",
        static_folder="static",
        root_path=str(Path(__file__).resolve().parent),
    )
    app.secret_key = os.environ.get("CHATRIACC_SECRET", "chatriacc-lan")
    using_default_db = db_path is None
    store = Store(db_path or DEFAULT_DB)
    app.config["STORE"] = store
    if using_default_db and os.environ.get("CHATRIACC_AUTO_SEED", "1") == "1":
        try:
            ensure_seed_imported(store)
        except Exception:
            pass

    @app.context_processor
    def inject_globals():
        s = store.settings_map()
        year = store.fiscal_year()
        return {
            "settings": s,
            "app_name": s.get("app_name", "chatriACC"),
            "church_name": s.get("church_name", ""),
            "fiscal_year": year,
            "year_label": year_label(year),
            "available_years": store.list_years(),
            "expected_file": store.expected_file(year),
            "thai_months": THAI_MONTHS,
            "format_baht": format_baht,
            "baht_text": baht_text,
            "thai_date": thai_date,
            "buddhist_year": buddhist_year,
            "voucher_label": lambda kind, number: f"{s.get('rv_prefix' if kind == 'rv' else 'pv_prefix', kind.upper())}-{int(number):03d}",
        }

    @app.get("/health")
    def health():
        return {"ok": True, "app": "chatriACC", "port": DEFAULT_PORT}

    @app.get("/")
    def dashboard():
        year = _year()
        data = store.dashboard(year)
        return render_template("dashboard.html", data=data, year=year)

    @app.route("/vouchers/new/<kind>", methods=["GET", "POST"])
    def voucher_new(kind: str):
        if kind not in ("rv", "pv"):
            abort(404)
        year = store.fiscal_year()
        accounts = store.accounts("income" if kind == "rv" else "expense")
        settings = store.settings_map()
        if request.method == "POST":
            try:
                vid = store.create_voucher(
                    kind=kind,
                    lines=_form_lines(),
                    transfers=_form_transfers(),
                    officer=request.form.get("officer") or settings.get("officer", ""),
                    reviewer=request.form.get("reviewer") or settings.get("parish_priest", ""),
                    year=year,
                )
                flash("เก็บข้อมูล เรียบร้อย - เริ่มใบฯ ใหม่", "ok")
                return redirect(url_for("voucher_detail", voucher_id=vid))
            except ValueError as exc:
                flash(str(exc), "err")
        return render_template(
            "voucher_form.html",
            kind=kind,
            accounts=accounts,
            next_number=store.next_number(kind, year),
            today=today().isoformat(),
            officer=settings.get("officer", ""),
            reviewer=settings.get("parish_priest", ""),
        )

    @app.get("/vouchers/<kind>")
    def voucher_list(kind: str):
        if kind not in ("rv", "pv"):
            abort(404)
        year = _year()
        month = request.args.get("month", type=int)
        rows = store.list_vouchers(kind=kind, year=year, month=month, limit=500)
        return render_template(
            "voucher_list.html",
            kind=kind,
            rows=rows,
            year=year,
            month=month,
        )

    @app.get("/vouchers/<int:voucher_id>")
    def voucher_detail(voucher_id: int):
        data = store.get_voucher(voucher_id)
        if not data:
            abort(404)
        return render_template("voucher_detail.html", data=data)

    @app.get("/vouchers/<int:voucher_id>/print")
    def voucher_print(voucher_id: int):
        data = store.get_voucher(voucher_id)
        if not data:
            abort(404)
        return render_template("voucher_print.html", data=data)

    @app.post("/vouchers/<int:voucher_id>/cancel")
    def voucher_cancel(voucher_id: int):
        try:
            store.cancel_voucher(voucher_id)
            flash("ยกเลิกใบสำคัญเรียบร้อย (เรียกคืนไม่ได้)", "ok")
        except ValueError as exc:
            flash(str(exc), "err")
        return redirect(url_for("voucher_detail", voucher_id=voucher_id))

    @app.get("/ledgers/<kind>")
    def ledger(kind: str):
        if kind not in ("rv", "pv"):
            abort(404)
        year = _year()
        month = request.args.get("month", type=int) or today().month
        rows = store.ledger(kind, year=year, month=month)
        total = sum(int(r["amount_satang"]) for r in rows)
        return render_template(
            "ledger.html",
            kind=kind,
            rows=rows,
            year=year,
            month=month,
            total=total,
        )

    @app.get("/reports/accounts")
    def report_accounts():
        year = _year()
        month = request.args.get("month", type=int)
        if month == 0:
            month = None
        kind = request.args.get("kind") or ""
        if kind not in ("rv", "pv"):
            kind = None
        selected = []
        for raw in request.args.getlist("code"):
            try:
                selected.append(int(raw))
            except (TypeError, ValueError):
                continue
        report = store.account_code_report(
            year=year,
            month=month,
            codes=selected or None,
            kind=kind,
        )
        return render_template(
            "report_accounts.html",
            year=year,
            month=month or 0,
            kind=kind or "",
            selected=set(selected),
            report=report,
            income_acc=store.accounts("income"),
            expense_acc=store.accounts("expense"),
            filtered=bool(selected),
        )

    @app.get("/reports/pl")
    def report_pl():
        year = _year()
        totals = store.year_totals(year)
        income_acc = store.accounts("income")
        expense_acc = store.accounts("expense")
        return render_template(
            "report_pl.html",
            year=year,
            totals=totals,
            income_acc=income_acc,
            expense_acc=expense_acc,
        )

    @app.get("/reports/balance")
    def report_balance():
        year = _year()
        sheet = store.balance_sheet(year)
        return render_template("report_balance.html", sheet=sheet, year=year)

    @app.get("/reports/position")
    def report_position():
        year = _year()
        sheet = store.balance_sheet(year)
        return render_template("report_position.html", sheet=sheet, year=year)

    @app.route("/assets", methods=["GET", "POST"])
    def assets():
        if request.method == "POST":
            desc = (request.form.get("description") or "").strip()
            txn = iso_date(request.form.get("txn_date"))
            if not desc or not txn:
                flash("กรุณาใส่วันที่และรายการ", "err")
            else:
                store.add_asset(
                    {
                        "direction": request.form.get("direction") or "in",
                        "txn_date": txn,
                        "description": desc,
                        "qty": request.form.get("qty") or None,
                        "amount_satang": baht_to_satang(request.form.get("amount")),
                        "location": request.form.get("location") or "",
                        "code": request.form.get("code") or "",
                        "reason": request.form.get("reason") or "",
                    }
                )
                flash("บันทึกครุภัณฑ์แล้ว", "ok")
            return redirect(url_for("assets"))
        incoming = store.assets("in")
        outgoing = store.assets("out")
        return render_template(
            "assets.html",
            incoming=incoming,
            outgoing=outgoing,
            in_total=sum(int(r["amount_satang"]) for r in incoming),
            out_total=sum(int(r["amount_satang"]) for r in outgoing),
            today=today().isoformat(),
        )

    @app.post("/assets/<int:asset_id>/delete")
    def asset_delete(asset_id: int):
        store.delete_asset(asset_id)
        flash("ลบรายการครุภัณฑ์แล้ว", "ok")
        return redirect(url_for("assets"))

    @app.route("/budget", methods=["GET", "POST"])
    def budget():
        year = request.args.get("year", type=int) or (store.fiscal_year() + 1)
        if request.method == "POST":
            year = int(request.form.get("year") or year)
            amounts = {}
            for acc in store.accounts():
                amounts[int(acc["code"])] = baht_to_satang(request.form.get(f"acc_{acc['code']}"))
            projects = []
            for i in range(1, 21):
                projects.append(
                    {
                        "name": request.form.get(f"proj_name_{i}") or "",
                        "period": request.form.get(f"proj_period_{i}") or "",
                        "amount_satang": baht_to_satang(request.form.get(f"proj_amount_{i}")),
                    }
                )
            store.save_budget(year, amounts, projects)
            flash("บันทึกประมาณการแล้ว", "ok")
            return redirect(url_for("budget", year=year))
        data = store.budget(year)
        existing_codes = {int(r["account_code"]) for r in data["income"] + data["expense"]}
        income_rows = list(data["income"])
        expense_rows = list(data["expense"])
        acc_map = {int(r["account_code"]): r for r in income_rows + expense_rows}

        def as_row(acc):
            found = acc_map.get(int(acc["code"]))
            return found or {"account_code": acc["code"], "name": acc["name"], "amount_satang": 0, "kind": acc["kind"]}

        income_full = [as_row(a) for a in store.accounts("income")]
        expense_full = [as_row(a) for a in store.accounts("expense")]
        projects = list(data["projects"]) + [{"name": "", "period": "", "amount_satang": 0}] * max(
            0, 20 - len(data["projects"])
        )
        return render_template(
            "budget.html",
            year=year,
            income=income_full,
            expense=expense_full,
            projects=projects[:20],
            income_total=sum(int(r["amount_satang"]) for r in income_full),
            expense_total=sum(int(r["amount_satang"]) for r in expense_full),
            unused=existing_codes,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            store.save_settings(
                {
                    "church_id": request.form.get("church_id") or "",
                    "church_name": request.form.get("church_name") or "",
                    "diocese": request.form.get("diocese") or "",
                    "parish_priest": request.form.get("parish_priest") or "",
                    "officer": request.form.get("officer") or "",
                    "assistant_priest": request.form.get("assistant_priest") or "",
                }
            )
            cash = []
            for i in range(1, 5):
                cash.append(
                    {
                        "name": request.form.get(f"cash_name_{i}") or "",
                        "amount_satang": baht_to_satang(request.form.get(f"cash_amt_{i}")),
                    }
                )
            store.save_cash_holders(cash)
            banks = []
            for i in range(1, 7):
                banks.append(
                    {
                        "bank_name": request.form.get(f"bank_name_{i}") or "",
                        "account_no": request.form.get(f"bank_no_{i}") or "",
                        "branch": request.form.get(f"bank_branch_{i}") or "",
                        "amount_satang": baht_to_satang(request.form.get(f"bank_amt_{i}")),
                    }
                )
            store.save_banks(banks)
            flash("บันทึกการตั้งค่าแล้ว", "ok")
            return redirect(url_for("settings"))
        cash = list(store.cash_holders()) + [{"name": "", "amount_satang": 0}] * 4
        banks = list(store.bank_accounts()) + [{"bank_name": "", "account_no": "", "branch": "", "amount_satang": 0}] * 6
        return render_template("settings.html", cash=cash[:4], banks=banks[:6])

    def _run_xlsb_import(path: Path):
        result = import_xlsb(store, path, replace=True)
        years = result.get("years") or []
        flash(
            f"นำเข้า {path.name} — ใบสำคัญรับ {result['rv']} ใบ จ่าย {result['pv']} ใบ"
            + (f" ปี {', '.join(str(y) for y in years)}" if years else ""),
            "ok",
        )
        return result

    def _store_year_file(uploaded, fallback_year: int | None = None) -> Path:
        meta = parse_ac_filename(uploaded.filename or "")
        year = meta["year"] or fallback_year or store.fiscal_year()
        dest_dir = ROOT / "data" / "years" / str(year)
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = Path(uploaded.filename or ac_filename(year, store.setting("church_id", "209"))).name
        path = dest_dir / name
        uploaded.save(path)
        return path

    @app.route("/years", methods=["GET", "POST"])
    def years_page():
        result = None
        if request.method == "POST":
            action = request.form.get("action")
            try:
                if action == "prepare":
                    year = request.form.get("year", type=int)
                    if not year:
                        raise ValueError("กรุณาใส่ปีบัญชี ค.ศ.")
                    info = store.prepare_year(year)
                    flash(
                        f"เตรียมปี {year_label(year)} แล้ว ใบสำคัญเริ่มที่ CRV-001 / CPV-001 — นำเข้าไฟล์ {info['expected_file']}",
                        "ok",
                    )
                    return redirect(url_for("years_page"))
                if action == "import":
                    uploaded = request.files.get("file")
                    use_seed = request.form.get("use_seed") == "1"
                    path = None
                    if uploaded and uploaded.filename:
                        path = _store_year_file(uploaded)
                    elif use_seed and SEED_XLSB.exists():
                        path = SEED_XLSB
                    if not path:
                        raise ValueError("กรุณาเลือกไฟล์ .xlsb ของปีนั้น")
                    result = _run_xlsb_import(path)
            except ValueError as exc:
                flash(str(exc), "err")
            except Exception as exc:
                flash(f"นำเข้าไม่สำเร็จ: {exc}", "err")
        nxt = store.fiscal_year() + 1
        return render_template(
            "years.html",
            years=store.list_years(),
            next_year=nxt,
            next_file=ac_filename(nxt, store.setting("church_id", "209")),
            result=result,
            has_seed=SEED_XLSB.exists(),
        )

    @app.post("/years/select")
    def select_year():
        year = request.form.get("year", type=int)
        if not year:
            abort(400)
        store.select_year(year)
        flash(f"กำลังใช้ปีบัญชี {year_label(year)}", "ok")
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/import", methods=["GET", "POST"])
    def import_page():
        result = None
        if request.method == "POST":
            uploaded = request.files.get("file")
            use_seed = request.form.get("use_seed") == "1"
            path = None
            try:
                if uploaded and uploaded.filename:
                    path = _store_year_file(uploaded)
                elif use_seed and SEED_XLSB.exists():
                    path = SEED_XLSB
                if not path:
                    flash("กรุณาเลือกไฟล์ .xlsb หรือใช้ไฟล์ AC25-209 ที่มากับระบบ", "err")
                else:
                    result = _run_xlsb_import(path)
            except Exception as exc:
                flash(f"นำเข้าไม่สำเร็จ: {exc}", "err")
        return render_template(
            "import.html",
            result=result,
            has_seed=SEED_XLSB.exists(),
            voucher_count=store.voucher_count(store.fiscal_year()),
            years=store.list_years(),
        )

    @app.post("/year/clear")
    def clear_year():
        year = store.fiscal_year()
        store.clear_year_data(year)
        flash(f"ลบข้อมูลปี {year} แล้ว (เรียกคืนไม่ได้)", "ok")
        return redirect(url_for("settings"))

    def _year() -> int:
        return request.args.get("year", type=int) or store.fiscal_year()

    def _form_lines() -> list[dict]:
        lines = []
        for i in range(1, 8):
            lines.append(
                {
                    "txn_date": request.form.get(f"date_{i}"),
                    "detail": request.form.get(f"detail_{i}"),
                    "amount_satang": baht_to_satang(request.form.get(f"amount_{i}")),
                    "account_code": request.form.get(f"code_{i}") or None,
                    "bank_flag": request.form.get(f"bank_{i}") == "1",
                }
            )
        return lines

    def _form_transfers() -> list[dict]:
        rows = []
        for i in range(1, 4):
            rows.append(
                {
                    "number": request.form.get(f"tr_no_{i}"),
                    "transfer_date": request.form.get(f"tr_date_{i}"),
                    "party": request.form.get(f"tr_party_{i}"),
                    "amount_satang": baht_to_satang(request.form.get(f"tr_amt_{i}")),
                }
            )
        return rows

    return app


def main():
    app = create_app()
    app.run(host=DEFAULT_HOST, port=DEFAULT_PORT, debug=os.environ.get("CHATRIACC_DEBUG") == "1")
