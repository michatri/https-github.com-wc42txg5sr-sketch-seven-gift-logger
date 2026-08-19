from __future__ import annotations

import json
import os
from typing import Any

import requests


def line_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_messages(payload: dict[str, Any], message_type: str, photo_urls: list[str]) -> list[dict[str, Any]]:
    date = payload.get("date") or ""
    code = payload.get("branchCode") or ""
    name = payload.get("storeName") or ""
    pieces = payload.get("pieces")
    baskets = payload.get("baskets")
    contact = payload.get("contactName") or ""
    position = payload.get("position") or ""
    phone = payload.get("phone") or ""

    if message_type in ("short", "summary"):
        text = f"รับของ\nรหัสสาขา: {code} {name} - {pieces} ชิ้น"
    else:
        lines = [
            "📦 รับของบริจาค 7-Eleven",
            f"📅 วันที่: {date}",
            f"🏪 รหัสสาขา: {code}",
            f"ชื่อร้าน: {name}",
            f"🔢 จำนวนชิ้น: {pieces}",
        ]
        if baskets not in (None, "", 0):
            lines.append(f"🧺 จำนวนตะกร้า: {baskets}")
        if contact:
            extra = f" ({position})" if position else ""
            lines.append(f"👤 ผู้ติดต่อ: {contact}{extra}")
        if phone:
            lines.append(f"📞 เบอร์โทร: {phone}")
        text = "\n".join(lines)

    messages: list[dict[str, Any]] = [{"type": "text", "text": text}]
    if message_type not in ("short", "summary"):
        for url in photo_urls[:5]:
            messages.append(
                {
                    "type": "image",
                    "originalContentUrl": url,
                    "previewImageUrl": url,
                }
            )
    return messages


def notify_line_groups(
    token: str,
    groups: list[dict[str, Any]],
    payload: dict[str, Any],
    photo_urls: list[str] | None = None,
) -> None:
    if not token or not groups:
        return
    photo_urls = photo_urls or []
    for group in groups:
        messages = build_messages(payload, group.get("message_type") or "full", photo_urls)
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={**line_headers(token), "Content-Type": "application/json"},
                data=json.dumps({"to": group["group_id"], "messages": messages}),
                timeout=15,
            )
        except requests.RequestException:
            continue
