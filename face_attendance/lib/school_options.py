"""School dropdown options: year/term/grade/room."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .camera import CONFIG, ensure_data_dirs
from .gallery import EnrollmentError, list_people

OPTIONS_PATH = CONFIG / "school_options.json"

TERMS = ["1", "2"]

GRADES = [
    "เตรียมอนุบาล",
    "อนุบาล 1",
    "อนุบาล 2",
    "อนุบาล 3",
    "ประถมศึกษาปีที่ 1",
    "ประถมศึกษาปีที่ 2",
    "ประถมศึกษาปีที่ 3",
    "ประถมศึกษาปีที่ 4",
    "ประถมศึกษาปีที่ 5",
    "ประถมศึกษาปีที่ 6",
    "มัธยมศึกษาปีที่ 1",
    "มัธยมศึกษาปีที่ 2",
    "มัธยมศึกษาปีที่ 3",
    "มัธยมศึกษาปีที่ 4",
    "มัธยมศึกษาปีที่ 5",
    "มัธยมศึกษาปีที่ 6",
]

DEFAULT_ROOMS = [str(i) for i in range(1, 21)]


def _current_be_year() -> int:
    try:
        now = datetime.now(ZoneInfo("Asia/Bangkok"))
    except Exception:  # noqa: BLE001
        now = datetime.utcnow()
    return now.year + 543


def _default_years() -> list[str]:
    y = _current_be_year()
    return [str(v) for v in range(y - 2, y + 4)]


def _load_custom() -> dict:
    ensure_data_dirs()
    CONFIG.mkdir(parents=True, exist_ok=True)
    if not OPTIONS_PATH.exists():
        return {"academic_years": [], "rooms": []}
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"academic_years": [], "rooms": []}
    if not isinstance(data, dict):
        return {"academic_years": [], "rooms": []}
    years = data.get("academic_years") or []
    rooms = data.get("rooms") or []
    return {
        "academic_years": [str(x).strip() for x in years if str(x).strip()],
        "rooms": [str(x).strip() for x in rooms if str(x).strip()],
    }


def _save_custom(data: dict) -> None:
    ensure_data_dirs()
    CONFIG.mkdir(parents=True, exist_ok=True)
    payload = {
        "academic_years": sorted(set(data.get("academic_years") or []), reverse=True),
        "rooms": sorted(
            set(data.get("rooms") or []),
            key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)),
        ),
    }
    OPTIONS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _used_values(key: str) -> list[str]:
    values = set()
    for person in list_people():
        value = str(person.get(key) or "").strip()
        if value:
            values.add(value)
    return sorted(values)


def get_school_options() -> dict[str, list[str]]:
    custom = _load_custom()
    years = set(_default_years()) | set(custom["academic_years"]) | set(
        _used_values("academic_year")
    )
    rooms = set(DEFAULT_ROOMS) | set(custom["rooms"]) | set(_used_values("room"))
    return {
        "academic_year": sorted(years, reverse=True),
        "term": list(TERMS),
        "grade": list(GRADES),
        "room": sorted(
            rooms,
            key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)),
        ),
    }


def add_academic_year(year: str) -> dict[str, list[str]]:
    year = (year or "").strip()
    if not year:
        raise EnrollmentError("กรุณาระบุปีการศึกษา")
    if not year.isdigit() or len(year) != 4:
        raise EnrollmentError("ปีการศึกษาต้องเป็นตัวเลข 4 หลัก เช่น 2568")
    custom = _load_custom()
    if year not in custom["academic_years"]:
        custom["academic_years"].append(year)
        _save_custom(custom)
    return get_school_options()


def add_room(room: str) -> dict[str, list[str]]:
    room = (room or "").strip()
    if not room:
        raise EnrollmentError("กรุณาระบุห้อง")
    if len(room) > 16:
        raise EnrollmentError("ชื่อห้องยาวเกินไป")
    custom = _load_custom()
    if room not in custom["rooms"]:
        custom["rooms"].append(room)
        _save_custom(custom)
    return get_school_options()
