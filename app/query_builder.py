"""Compile visual query JSON into a read-only SELECT. Users never send raw SQL."""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from typing import Any

from app.report_schema import (
    is_ident,
    is_secret_column,
    quote_ident,
    table_columns,
)

log = logging.getLogger("catholic.reports")

USER_ERROR = "ไม่สามารถสร้างรายงานได้ กรุณาตรวจสอบเงื่อนไขของรายงาน"
MAX_ROWS = 500
HARD_CAP = 2000
MAX_JOINS = 5
QUERY_TIMEOUT_SEC = 8

AGGS = {"SUM", "COUNT", "AVG", "MIN", "MAX"}
JOIN_TYPES = {"INNER": "INNER JOIN", "LEFT": "LEFT JOIN"}
OPS = {
    "eq": "=",
    "ne": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "startswith": "LIKE",
    "contains": "LIKE",
}
NULL_OPS = {"is_null": "IS NULL", "is_not_null": "IS NOT NULL"}
DATE_PARTS = {"year": "substr(%s, 1, 4)", "month": "substr(%s, 1, 7)"}
FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|ATTACH|DETACH|"
    r"PRAGMA|REPLACE|VACUUM|REINDEX|GRANT|REVOKE|INTO)\b",
    re.I,
)


class QueryError(Exception):
    """Safe, user-facing query failure."""

    def __init__(self, message: str = USER_ERROR, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or message


def load_schema_map(conn: sqlite3.Connection) -> dict[str, set[str]]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    out: dict[str, set[str]] = {}
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[0]
        if not is_ident(name):
            continue
        cols = set()
        for col in table_columns(conn, name):
            cols.add(col["name"])
        out[name] = cols
    return out


def _field_sql(table: str, column: str, schema: dict[str, set[str]], part: str | None = None) -> str:
    if table == "users" or not is_ident(table) or table not in schema:
        raise QueryError(detail=f"unknown table {table}")
    if column != "*" and (not is_ident(column) or column not in schema[table]):
        raise QueryError(detail=f"unknown column {table}.{column}")
    if column != "*" and is_secret_column(table, column):
        raise QueryError(detail="blocked column")
    if column == "*":
        expr = f"{quote_ident(table)}.*"
    else:
        expr = f"{quote_ident(table)}.{quote_ident(column)}"
    if part:
        if part not in DATE_PARTS:
            raise QueryError(detail=f"bad date part {part}")
        expr = DATE_PARTS[part] % expr
    return expr


def _parse_field_ref(raw: str, default_table: str) -> tuple[str, str]:
    raw = (raw or "").strip()
    if "." in raw:
        table, column = raw.split(".", 1)
        return table, column
    return default_table, raw


def compile_query(
    config: dict[str, Any],
    schema: dict[str, set[str]],
    parameters: dict[str, Any] | None = None,
    *,
    page: int = 1,
    page_size: int = 50,
    for_count: bool = False,
) -> tuple[str, list[Any]]:
    if not isinstance(config, dict):
        raise QueryError(detail="query config must be an object")
    main = str(config.get("mainTable") or "").strip()
    if main == "users" or not is_ident(main) or main not in schema:
        raise QueryError(detail="main table")
    params_in = parameters or {}
    binds: list[Any] = []

    joins = list(config.get("joins") or [])
    if len(joins) > MAX_JOINS:
        raise QueryError(detail="too many joins")
    join_sql = []
    used_tables = {main}
    for jn in joins:
        jtable = str(jn.get("table") or "")
        jtype = JOIN_TYPES.get(str(jn.get("type") or "LEFT").upper(), None)
        if jtype is None or not is_ident(jtable) or jtable not in schema:
            raise QueryError(detail="join table")
        left_t, left_c = _parse_field_ref(str(jn.get("left") or ""), main)
        right_t, right_c = _parse_field_ref(str(jn.get("right") or ""), jtable)
        left_sql = _field_sql(left_t, left_c, schema)
        right_sql = _field_sql(right_t, right_c, schema)
        join_sql.append(f"{jtype} {quote_ident(jtable)} ON {left_sql} = {right_sql}")
        used_tables.add(jtable)

    fields = list(config.get("fields") or [])
    if not fields:
        raise QueryError("กรุณาเลือกอย่างน้อยหนึ่งฟิลด์")
    select_parts = []
    aliases: list[str] = []
    has_agg = False
    for i, fld in enumerate(fields):
        table = str(fld.get("table") or main)
        column = str(fld.get("column") or "")
        agg = str(fld.get("agg") or "").upper() or None
        alias = str(fld.get("alias") or column or f"c{i}")
        if not is_ident(alias):
            alias = f"c{i}"
        part = fld.get("part")
        if agg and agg not in AGGS:
            raise QueryError(detail=f"agg {agg}")
        if agg == "COUNT" and column in ("", "*"):
            expr = "COUNT(*)"
        else:
            expr = _field_sql(table, column, schema, part=part)
            if agg:
                expr = f"{agg}({expr})"
                has_agg = True
        select_parts.append(f"{expr} AS {quote_ident(alias)}")
        aliases.append(alias)

    distinct = "DISTINCT " if config.get("distinct") else ""
    from_sql = f" FROM {quote_ident(main)} " + " ".join(join_sql)

    where_bits: list[str] = []
    for flt in config.get("filters") or []:
        field = str(flt.get("field") or "")
        op = str(flt.get("op") or "eq")
        table, column = _parse_field_ref(field, main)
        expr = _field_sql(table, column, schema, part=flt.get("part"))
        param_name = flt.get("param")
        value = flt.get("value")
        if param_name:
            if param_name not in params_in or params_in[param_name] in (None, ""):
                if flt.get("required"):
                    raise QueryError("กรุณากรอกเงื่อนไขของรายงาน")
                continue
            value = params_in[param_name]
        if op in NULL_OPS:
            where_bits.append(f"{expr} {NULL_OPS[op]}")
            continue
        if op not in OPS:
            raise QueryError(detail=f"op {op}")
        if value in (None, ""):
            continue
        if op == "contains":
            binds.append(f"%{value}%")
        elif op == "startswith":
            binds.append(f"{value}%")
        else:
            binds.append(value)
        where_bits.append(f"{expr} {OPS[op]} ?")

    where_sql = ""
    if where_bits:
        where_sql = " WHERE " + " AND ".join(where_bits)

    group_sql = ""
    group_exprs = []
    for g in config.get("groupBy") or []:
        if isinstance(g, str):
            table, column = _parse_field_ref(g, main)
            part = None
        else:
            table, column = _parse_field_ref(str(g.get("field") or ""), main)
            part = g.get("part")
        group_exprs.append(_field_sql(table, column, schema, part=part))
    if group_exprs:
        group_sql = " GROUP BY " + ", ".join(group_exprs)
    elif has_agg:
        pass

    order_sql = ""
    order_bits = []
    for o in config.get("orderBy") or []:
        if isinstance(o, str):
            table, column = _parse_field_ref(o, main)
            direction = "ASC"
            part = None
        else:
            table, column = _parse_field_ref(str(o.get("field") or ""), main)
            direction = "DESC" if str(o.get("dir") or "ASC").upper() == "DESC" else "ASC"
            part = o.get("part")
        order_bits.append(f"{_field_sql(table, column, schema, part=part)} {direction}")
    if order_bits and not for_count:
        order_sql = " ORDER BY " + ", ".join(order_bits)

    if for_count:
        sql = (
            "SELECT COUNT(*) AS n FROM (SELECT "
            + distinct
            + ", ".join(select_parts)
            + from_sql
            + where_sql
            + group_sql
            + ") AS counted"
        )
        return sql, binds

    wanted = int(config.get("limit") or page_size or MAX_ROWS)
    cap = min(max(wanted, 1), HARD_CAP)
    page = max(int(page or 1), 1)
    size = min(max(int(page_size or 50), 1), cap)
    offset = (page - 1) * size
    limit_sql = " LIMIT ? OFFSET ?"
    binds_limit = binds + [size, offset]
    sql = "SELECT " + distinct + ", ".join(select_parts) + from_sql + where_sql + group_sql + order_sql + limit_sql
    return sql, binds_limit


def validate_admin_sql(sql: str) -> str:
    text = (sql or "").strip()
    if not text:
        raise QueryError("กรุณาระบุคำสั่ง SELECT")
    if ";" in text.rstrip(";"):
        raise QueryError(detail="multiple statements")
    text = text.rstrip(";").strip()
    if FORBIDDEN_SQL.search(text):
        raise QueryError(detail="forbidden keyword")
    head = re.sub(r"\s+", " ", text.lstrip().upper())
    if not (head.startswith("SELECT ") or head.startswith("WITH ")):
        raise QueryError(detail="not a select")
    if re.search(r"\bLIMIT\s+\d+", text, re.I) is None:
        text = f"{text} LIMIT {MAX_ROWS}"
    return text


def run_select(
    conn: sqlite3.Connection,
    sql: str,
    binds: list[Any] | None = None,
    timeout: int = QUERY_TIMEOUT_SEC,
) -> list[sqlite3.Row]:
    start = time.time()

    def _watch():
        if time.time() - start > timeout:
            return 1
        return 0

    conn.set_progress_handler(_watch, 10000)
    try:
        cur = conn.execute(sql, binds or [])
        return cur.fetchall()
    except sqlite3.OperationalError as exc:
        log.exception("report query failed: %s", exc)
        if "interrupted" in str(exc).lower():
            raise QueryError("รายงานใช้เวลานานเกินไป กรุณาจำกัดเงื่อนไข") from exc
        raise QueryError() from exc
    except sqlite3.Error as exc:
        log.exception("report query failed: %s", exc)
        raise QueryError() from exc
    finally:
        conn.set_progress_handler(None, 0)


def execute_dataset(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    parameters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 50,
    admin_sql: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    if admin_sql:
        if not is_admin:
            raise QueryError("ไม่มีสิทธิ์ใช้คำสั่งขั้นสูง")
        sql = validate_admin_sql(admin_sql)
        rows = run_select(conn, sql, [])
        data = [dict(r) for r in rows]
        cols = list(data[0].keys()) if data else []
        return {
            "rows": data[:HARD_CAP],
            "columns": cols,
            "total": len(data),
            "page": 1,
            "pageSize": len(data),
            "sql": None,
        }
    schema = load_schema_map(conn)
    page_size = min(max(int(page_size or 50), 1), MAX_ROWS)
    sql, binds = compile_query(config, schema, parameters, page=page, page_size=page_size)
    count_sql, count_binds = compile_query(config, schema, parameters, for_count=True)
    total_rows = run_select(conn, count_sql, count_binds)
    total = int(total_rows[0][0]) if total_rows else 0
    rows = [dict(r) for r in run_select(conn, sql, binds)]
    columns = []
    for fld in config.get("fields") or []:
        alias = str(fld.get("alias") or fld.get("column") or "")
        if alias:
            columns.append(alias)
    if not columns and rows:
        columns = list(rows[0].keys())
    return {
        "rows": rows,
        "columns": columns,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "sql": None,
    }
