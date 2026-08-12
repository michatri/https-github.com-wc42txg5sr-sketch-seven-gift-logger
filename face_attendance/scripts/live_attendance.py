#!/usr/bin/env python3
"""ขั้นที่ 4: ลงเวลาหลายคนจากสตรีมกล้อง (headless — บันทึกผลเป็น CSV + ภาพ)."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.camera import (  # noqa: E402
    DATA,
    FacePipeline,
    draw_hits,
    ensure_data_dirs,
    load_camera_env,
    open_capture,
)
from face_attendance.lib.gallery import load_gallery, match_embedding  # noqa: E402


def main() -> None:
    load_camera_env()
    parser = argparse.ArgumentParser(description="ทดสอบลงเวลาหลายคนพร้อมกัน")
    parser.add_argument("--source", default=None, help="RTSP / วิดีโอ / webcam")
    parser.add_argument("--seconds", type=int, default=30, help="รันกี่วินาที")
    parser.add_argument("--every", type=float, default=0.5, help="ประมวลผลทุกกี่วินาที")
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("MATCH_THRESHOLD", "0.42")),
        help="cosine threshold",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=int(os.getenv("COOLDOWN_SECONDS", "120")),
        help="กันลงซ้ำ (วินาที)",
    )
    args = parser.parse_args()

    ensure_data_dirs()
    pipeline = FacePipeline()
    gallery = load_gallery(pipeline)
    if not gallery:
        raise SystemExit(
            "ยังไม่มีคนใน gallery — รัน scripts/enroll_face.py ก่อนอย่างน้อย 1 คน"
        )

    print(f"gallery: {len(gallery)} คน → {', '.join(gallery)}")
    source = int(args.source) if args.source and args.source.isdigit() else args.source
    cap = open_capture(source)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = DATA / "attendance" / f"attendance_{stamp}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    last_seen: dict[str, float] = {}
    rows_written = 0

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["timestamp_utc", "person_id", "similarity", "snapshot"]
        )
        writer.writeheader()

        t_end = time.time() + args.seconds
        last_proc = 0.0
        frame_i = 0
        fail_streak = 0
        while time.time() < t_end:
            ok, frame = cap.read()
            if not ok or frame is None:
                fail_streak += 1
                # ไฟล์รูป/วิดีโอจบแล้ว หรือ RTSP หลุดชั่วคราว
                if fail_streak >= 10:
                    print("แหล่งภาพหมดเฟรมหรือหลุดการเชื่อมต่อ — จบการทดสอบ")
                    break
                time.sleep(0.2)
                continue
            fail_streak = 0

            now = time.time()
            if now - last_proc < args.every:
                continue
            last_proc = now
            frame_i += 1

            hits = pipeline.detect(frame)
            for hit in hits:
                emb = pipeline.embed(frame, hit)
                name, sim = match_embedding(pipeline, emb, gallery, args.threshold)
                hit.name = name
                hit.similarity = sim

                if name == "unknown":
                    continue
                prev = last_seen.get(name, 0.0)
                if now - prev < args.cooldown:
                    continue
                last_seen[name] = now

                snap = DATA / "attendance" / f"{stamp}_{name}_{frame_i}.jpg"
                x, y, w, h = hit.box
                crop = frame[max(0, y) : y + h, max(0, x) : x + w]
                cv2.imwrite(str(snap), crop)
                ts = datetime.now(timezone.utc).isoformat()
                writer.writerow(
                    {
                        "timestamp_utc": ts,
                        "person_id": name,
                        "similarity": f"{sim:.4f}",
                        "snapshot": str(snap),
                    }
                )
                f.flush()
                rows_written += 1
                print(f"[ATTEND] {name} sim={sim:.3f}")

            annotated = draw_hits(frame, hits)
            preview = DATA / "attendance" / f"live_preview_{stamp}.jpg"
            cv2.imwrite(str(preview), annotated)
            print(
                f"เฟรม#{frame_i}: faces={len(hits)} "
                f"known={[h.name for h in hits if h.name and h.name != 'unknown']}"
            )

    cap.release()
    print(f"จบแล้ว — บันทึก {rows_written} รายการที่ {csv_path}")


if __name__ == "__main__":
    main()
