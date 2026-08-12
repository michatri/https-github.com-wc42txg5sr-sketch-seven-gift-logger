#!/usr/bin/env python3
"""ทดสอบ pipeline แบบออฟไลน์ด้วยรูปตัวอย่าง (ไม่ต้องมีกล้อง)."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from face_attendance.lib.camera import DATA, FacePipeline, draw_hits, ensure_data_dirs  # noqa: E402
from face_attendance.lib.gallery import enroll_from_image, load_gallery, match_embedding  # noqa: E402


SAMPLE_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/"
    "4.x/samples/data/lena.jpg"
)


def main() -> None:
    ensure_data_dirs()
    sample = DATA / "captures" / "sample_lena.jpg"
    sample.parent.mkdir(parents=True, exist_ok=True)
    if not sample.exists():
        print("ดาวน์โหลดรูปตัวอย่าง...")
        urllib.request.urlretrieve(SAMPLE_URL, sample)

    pipeline = FacePipeline()
    img = cv2.imread(str(sample))
    hits = pipeline.detect(img)
    print(f"detect: {len(hits)} face(s)")
    if not hits:
        raise SystemExit("FAIL: ไม่พบใบหน้าในรูปตัวอย่าง")

    meta = enroll_from_image(pipeline, sample, "demo_lena")
    print(f"enroll: {meta['person_id']}")

    gallery = load_gallery(pipeline)
    emb = pipeline.embed(img, hits[0])
    name, sim = match_embedding(pipeline, emb, gallery, threshold=0.35)
    print(f"match: {name} sim={sim:.3f}")
    if name != "demo_lena":
        raise SystemExit("FAIL: จับคู่ไม่ถูกต้อง")

    out = DATA / "captures" / "selftest_annotated.jpg"
    hits[0].name = name
    hits[0].similarity = sim
    cv2.imwrite(str(out), draw_hits(img, hits))
    print(f"OK — self-test ผ่าน → {out}")
    _ = np  # silence linter if unused in some envs


if __name__ == "__main__":
    main()
