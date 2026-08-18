#!/usr/bin/env python3
"""ขั้นที่ 3: ลงทะเบียนใบหน้านักเรียนจากรูป (หรือ snapshot จากกล้อง)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.camera import FacePipeline, ensure_data_dirs, grab_frame, open_capture  # noqa: E402
from face_attendance.lib.gallery import EnrollmentError, enroll_from_image  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="ลงทะเบียนใบหน้า 1 คน")
    parser.add_argument("--person-id", required=True, help="เช่น S001_somchai หรือ รหัสนักเรียน")
    parser.add_argument("--image", default=None, help="พาธรูปใบหน้าชัด ๆ")
    parser.add_argument(
        "--from-camera",
        action="store_true",
        help="ถ่าย snapshot จาก RTSP แล้วลงทะเบียน (ยืนคนเดียวหน้ากล้อง)",
    )
    parser.add_argument("--source", default=None, help="override แหล่งภาพเมื่อใช้ --from-camera")
    args = parser.parse_args()

    ensure_data_dirs()
    pipeline = FacePipeline()

    try:
        if args.from_camera:
            source = int(args.source) if args.source and args.source.isdigit() else args.source
            cap = open_capture(source)
            frame = grab_frame(cap, warmup=8)
            cap.release()
            tmp = ROOT / "data" / "enrolled" / f"{args.person_id}_capture.jpg"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(tmp), frame)
            image_path = tmp
            print(f"บันทึก snapshot: {image_path}")
        elif args.image:
            image_path = Path(args.image)
        else:
            raise SystemExit("ใส่ --image หรือ --from-camera")

        meta = enroll_from_image(pipeline, image_path, args.person_id)
    except (EnrollmentError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    print(f"ลงทะเบียนสำเร็จ: {meta['person_id']}")
    print(f"  display_name: {meta.get('display_name')}")
    print(f"  face_score: {meta.get('face_score')}")


if __name__ == "__main__":
    main()
