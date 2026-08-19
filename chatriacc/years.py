"""ชื่อไฟล์บัญชีวัดรายปี รูปแบบ AC25-209.xlsb (ปี ค.ศ. 2 หลัก + รหัสวัด)."""

from __future__ import annotations

import re
from pathlib import Path


def ac_filename(year: int, church_id: str | int = "209") -> str:
    cid = str(church_id or "209").strip() or "209"
    return f"AC{int(year) % 100:02d}-{cid}.xlsb"


def parse_ac_filename(name: str | Path | None) -> dict:
    """Read year and church id from AC25-209.xlsb or AC25-209_Nopass.xlsb."""
    text = Path(name).name if name else ""
    match = re.search(r"AC(\d{2})[-_](\d+)", text, flags=re.IGNORECASE)
    if not match:
        return {"year": None, "church_id": None, "filename": text}
    yy = int(match.group(1))
    return {
        "year": 2000 + yy if yy < 100 else yy,
        "church_id": match.group(2),
        "filename": text,
    }
