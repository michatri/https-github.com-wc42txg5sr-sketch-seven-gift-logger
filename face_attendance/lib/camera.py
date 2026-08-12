"""Shared helpers for Hikvision RTSP + OpenCV face pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
DATA = ROOT / "data"
CONFIG = ROOT / "config"

YUNET_PATH = MODELS / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS / "face_recognizer_fast.onnx"


def load_camera_env() -> None:
    env_path = CONFIG / "camera.env"
    example = CONFIG / "camera.example.env"
    if env_path.exists():
        load_dotenv(env_path)
    elif example.exists():
        load_dotenv(example)


def build_rtsp_url() -> str:
    load_camera_env()
    explicit = os.getenv("RTSP_URL", "").strip()
    if explicit:
        return explicit

    ip = os.getenv("CAMERA_IP", "192.168.1.64").strip()
    user = quote(os.getenv("CAMERA_USER", "admin").strip(), safe="")
    password = quote(os.getenv("CAMERA_PASS", "").strip(), safe="")
    channel = os.getenv("CAMERA_CHANNEL", "101").strip()
    if not password:
        raise SystemExit(
            "ตั้ง CAMERA_PASS ใน face_attendance/config/camera.env ก่อน "
            "หรือใส่ RTSP_URL ตรง ๆ"
        )
    return f"rtsp://{user}:{password}@{ip}:554/Streaming/Channels/{channel}"


def open_capture(source: str | int | None = None) -> cv2.VideoCapture:
    """Open RTSP / webcam / video file. Default = camera.env RTSP."""
    if source is None:
        source = build_rtsp_url()

    # FFmpeg backend handles Hikvision H.265/H.264 more reliably
    if isinstance(source, str) and source.startswith("rtsp://"):
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        raise SystemExit(f"เปิดแหล่งภาพไม่สำเร็จ: {source}")
    return cap


def grab_frame(cap: cv2.VideoCapture, warmup: int = 5) -> np.ndarray:
    frame = None
    for _ in range(max(warmup, 1)):
        ok, frame = cap.read()
        if not ok or frame is None:
            raise SystemExit("อ่านเฟรมจากกล้องไม่ได้ — เช็ก IP/รหัส/เครือข่าย/RTSP")
    return frame


@dataclass
class FaceHit:
    box: tuple[int, int, int, int]  # x, y, w, h
    score: float
    landmarks: np.ndarray | None = None
    embedding: np.ndarray | None = None
    name: str | None = None
    similarity: float | None = None


class FacePipeline:
    """YuNet detect + SFace recognize (OpenCV Zoo, CPU-friendly)."""

    def __init__(self, score_threshold: float = 0.7) -> None:
        if not YUNET_PATH.exists() or not SFACE_PATH.exists():
            raise SystemExit("ไม่พบโมเดลใน face_attendance/models/")

        self.score_threshold = score_threshold
        self.detector = cv2.FaceDetectorYN.create(
            str(YUNET_PATH),
            "",
            (320, 320),
            score_threshold=score_threshold,
            nms_threshold=0.3,
            top_k=20,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(str(SFACE_PATH), "")

    def detect(self, frame: np.ndarray) -> list[FaceHit]:
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        hits: list[FaceHit] = []
        if faces is None:
            return hits
        for face in faces:
            x, y, bw, bh = face[:4].astype(int)
            score = float(face[-1])
            landmarks = face[4:14].reshape(5, 2).astype(np.float32)
            hits.append(FaceHit(box=(x, y, bw, bh), score=score, landmarks=landmarks))
        return hits

    def embed(self, frame: np.ndarray, hit: FaceHit) -> np.ndarray:
        # FaceRecognizerSF expects the 15-value YuNet row
        face_row = np.asarray(
            [
                *hit.box,
                *hit.landmarks.reshape(-1),
                hit.score,
            ],
            dtype=np.float32,
        )
        aligned = self.recognizer.alignCrop(frame, face_row)
        feat = self.recognizer.feature(aligned)
        return feat.flatten()

    def cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(self.recognizer.match(a, b, cv2.FaceRecognizerSF_FR_COSINE))


def draw_hits(frame: np.ndarray, hits: list[FaceHit]) -> np.ndarray:
    out = frame.copy()
    for hit in hits:
        x, y, w, h = hit.box
        label = hit.name or "unknown"
        if hit.similarity is not None:
            label = f"{label} {hit.similarity:.2f}"
        color = (40, 180, 40) if hit.name and hit.name != "unknown" else (40, 40, 220)
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            out,
            label,
            (x, max(20, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    return out


def ensure_data_dirs() -> None:
    for path in (
        DATA / "enrolled",
        DATA / "captures",
        DATA / "attendance",
        DATA / "gallery",
    ):
        path.mkdir(parents=True, exist_ok=True)
