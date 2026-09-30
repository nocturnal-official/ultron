"""Screen and webcam vision — capture an image and analyze it with the configured brain."""
import io


def _capture_screen() -> bytes:
    try:
        import mss
        import mss.tools
    except ImportError:
        raise RuntimeError("mss is needed for screen capture. Run: pip install mss")
    with mss.mss() as sct:
        mons = sct.monitors
        target = mons[1] if len(mons) > 1 else mons[0]
        shot = sct.grab(target)
        return mss.tools.to_png(shot.rgb, shot.size)


def _capture_camera() -> bytes:
    try:
        import cv2
    except ImportError:
        raise RuntimeError("opencv-python is needed for the camera. Run: pip install opencv-python")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Couldn't open the webcam.")
    for _ in range(8):
        cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("Webcam returned no frame.")
    ok, buf = cv2.imencode(".png", frame)
    return buf.tobytes()


def _downscale(png: bytes, max_wh=(1280, 800)) -> bytes:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("RGB")
        img.thumbnail(max_wh)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=82)
        return out.getvalue()
    except Exception:
        return png


def look(angle: str = "screen", question: str = "What do you see?") -> str:
    """angle: 'screen' or 'camera'. Captures and describes what's there."""
    from ai_helper import analyze_image, provider_available
    if not provider_available():
        return "No AI provider is configured for vision."
    try:
        raw = _capture_camera() if angle.lower().strip() == "camera" else _capture_screen()
    except Exception as e:
        return str(e)
    img = _downscale(raw)
    mime = "image/jpeg" if img[:3] == b"\xff\xd8\xff" else "image/png"
    try:
        return analyze_image(img, question or "Describe what you see.", mime)
    except Exception as e:
        return f"Vision analysis failed: {e}"
