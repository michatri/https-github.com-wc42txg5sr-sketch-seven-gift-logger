"""Read text from a bank-slip photo with Tesseract when available."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def read_slip_image(path: str | Path) -> tuple[str, str]:
    """Return (ocr_text, engine_note). Never raises for missing tesseract."""
    image_path = Path(path)
    work: Path | None = None
    try:
        image = Image.open(image_path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        if min(image.size) < 900:
            scale = 900 / max(min(image.size), 1)
            image = image.resize((int(image.width * scale), int(image.height * scale)))
        gray = ImageOps.grayscale(image)
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        work = image_path.with_suffix(".ocr.jpg")
        gray.convert("RGB").save(work, "JPEG", quality=92)
    except Exception as exc:  # noqa: BLE001
        return "", f"เปิดรูปไม่ได้: {exc}"

    try:
        import pytesseract
    except ImportError:
        return "", "ยังไม่ได้ติดตั้ง pytesseract กรุณากรอกจำนวนเงินเอง"

    try:
        text = pytesseract.image_to_string(Image.open(work), lang="tha+eng")
    except Exception:
        try:
            text = pytesseract.image_to_string(Image.open(work), lang="eng")
        except Exception as exc:  # noqa: BLE001
            return "", f"อ่าน OCR ไม่สำเร็จ: {exc}"
    finally:
        if work is not None and work.exists() and work != image_path:
            work.unlink(missing_ok=True)

    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not cleaned:
        return "", "OCR ไม่พบข้อความในรูป กรุณากรอกเอง"
    return cleaned, "อ่านข้อความจากรูปด้วย Tesseract แล้ว"
