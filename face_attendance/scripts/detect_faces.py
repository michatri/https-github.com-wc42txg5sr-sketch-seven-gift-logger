#!/usr/bin/env python3
"""ขั้นที่ 2: ตรวจหลายใบหน้าจากกล้อง/รูป แล้วบันทึกผล."""

from __future__ import annotations

import argparse
import json
import sys
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
    grab_frame,
    open_capture,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ตรวจหลายใบหน้าพร้อมกัน")
    parser.add_argument("--source", default=None, help="RTSP / วิดีโอ / webcam / ว่าง=camera.env")
    parser.add_argument("--image", default=None, help="ทดสอบจากไฟล์รูปแทนสตรีม")
    parser.add_argument("--frames", type=int, default=1, help="จำนวนเฟรมที่จะประมวลผลจากสตรีม")
    args = parser.parse_args()

    ensure_data_dirs()
    pipeline = FacePipeline()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise SystemExit(f"อ่านรูปไม่ได้: {args.image}")
        frames = [frame]
    else:
        source = int(args.source) if args.source and args.source.isdigit() else args.source
        cap = open_capture(source)
        frames = []
        for i in range(max(1, args.frames)):
            frames.append(grab_frame(cap, warmup=3 if i == 0 else 1))
        cap.release()

    summary = []
    for idx, frame in enumerate(frames):
        hits = pipeline.detect(frame)
        annotated = draw_hits(frame, hits)
        out_img = DATA / "captures" / f"faces_{stamp}_{idx:02d}.jpg"
        cv2.imwrite(str(out_img), annotated)

        # บันทึก crop แต่ละใบหน้า
        crops = []
        for j, hit in enumerate(hits):
            x, y, w, h = hit.box
            crop = frame[max(0, y) : y + h, max(0, x) : x + w]
            crop_path = DATA / "captures" / f"faces_{stamp}_{idx:02d}_face{j}.jpg"
            cv2.imwrite(str(crop_path), crop)
            crops.append(
                {
                    "file": str(crop_path),
                    "score": float(hit.score),
                    "box": [int(v) for v in hit.box],
                }
            )

        summary.append(
            {
                "frame_index": idx,
                "face_count": len(hits),
                "annotated": str(out_img),
                "faces": crops,
            }
        )
        print(f"เฟรม {idx}: พบ {len(hits)} ใบหน้า → {out_img}")

    out_json = DATA / "captures" / f"faces_{stamp}.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"สรุป: {out_json}")


if __name__ == "__main__":
    main()
