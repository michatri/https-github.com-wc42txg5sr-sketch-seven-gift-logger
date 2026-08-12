#!/usr/bin/env python3
"""ขั้นที่ 1: ทดสอบว่าเชื่อม DS-2CD2146G2-I ผ่าน RTSP ได้ และบันทึก snapshot."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.camera import (  # noqa: E402
    DATA,
    build_rtsp_url,
    ensure_data_dirs,
    grab_frame,
    open_capture,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ทดสอบ RTSP จากกล้อง Hikvision")
    parser.add_argument(
        "--source",
        default=None,
        help="RTSP URL / path วิดีโอ / เลข webcam (default = จาก camera.env)",
    )
    args = parser.parse_args()

    ensure_data_dirs()
    source: str | int | None = args.source
    if source is not None and isinstance(source, str) and source.isdigit():
        source = int(source)

    if source is None:
        url = build_rtsp_url()
        safe = url
        if "@" in url:
            safe = "rtsp://***:***@" + url.split("@", 1)[1]
        print(f"กำลังเชื่อม: {safe}")
    else:
        print(f"กำลังเปิดแหล่งภาพ: {source}")

    cap = open_capture(source)
    frame = grab_frame(cap, warmup=8)
    h, w = frame.shape[:2]
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = DATA / "captures" / f"camera_ok_{stamp}.jpg"
    cv2.imwrite(str(out), frame)

    print("OK — เชื่อมกล้องสำเร็จ")
    print(f"  resolution: {w}x{h}")
    print(f"  reported_fps: {fps}")
    print(f"  snapshot: {out}")


if __name__ == "__main__":
    main()
