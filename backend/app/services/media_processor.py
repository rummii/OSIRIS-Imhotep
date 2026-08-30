"""Upload media processing: image normalisation + video frame sampling.

OpenCV (headless) is used so we have zero OS codec dependencies:

* images are decoded, down-scaled to a bounded max dimension and re-encoded
  as JPEG — this keeps the Gemini inline-data request payload small.
* videos are written to a temp file, sampled at evenly-spaced timestamps and
  returned as JPEG frames for multimodal evaluation (per the SOW spec).

Unsupported / corrupt files are logged into the manifest and skipped so a
single bad attachment never takes down a whole analysis run.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import cv2
import exifread
import numpy as np
from fastapi import UploadFile

logger = logging.getLogger("osiris.media")

IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
VIDEO_MIME = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/mpeg",
    "video/3gpp",
    "video/x-matroska",
}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mpeg", ".mpg", ".3gp", ".mkv"}

MAX_DIMENSION = 1600          # longest edge of an image after down-scaling (px)
JPEG_QUALITY = 85             # re-encode quality for images / sampled frames


@dataclass
class SpatialMetadata:
    """GPS/EXIF spatial metadata extracted from an image or video."""
    latitude: Optional[float] = None          # decimal degrees
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None        # meters above WGS84 ellipsoid
    accuracy_m: Optional[float] = None        # horizontal accuracy in meters
    captured_at: Optional[str] = None         # ISO 8601 timestamp from EXIF
    source_file: str = ""                     # original filename

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "accuracy_m": self.accuracy_m,
            "captured_at": self.captured_at,
            "source_file": self.source_file,
        }

    def is_valid(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass
class MediaPart:
    """One uploadable unit handed to the Gemini service."""

    kind: str                  # "image" | "video"
    filename: str
    mime_type: str
    bytes: bytes = b""                  # processed image bytes (JPEG) for images
    frames: list[tuple[str, bytes]] = field(default_factory=list)  # (mime, jpeg) pairs
    spatial: Optional[SpatialMetadata] = None  # GPS/EXIF data


@dataclass
class MediaBundle:
    parts: list[MediaPart] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)

    @property
    def spatial_manifest(self) -> dict[str, Optional[dict]]:
        """Return {filename: SpatialMetadata.to_dict() | None} for all parts."""
        return {part.filename: part.spatial.to_dict() if part.spatial else None for part in self.parts}

    def summary(self) -> str:
        return ";\n".join(
            f"{e['filename']} ({e['kind']}, {e.get('frames', 0)} frames)" for e in self.log
        )


def classify_file(filename: str, content_type: str | None) -> str | None:
    """Return ``'image'``, ``'video'`` or ``None`` for an upload."""
    mime = (content_type or "").lower()
    if mime in IMAGE_MIME:
        return "image"
    if mime in VIDEO_MIME:
        return "video"
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def _extract_exif_gps(data: bytes, filename: str) -> Optional[SpatialMetadata]:
    """Extract GPS coordinates and timestamp from image EXIF data.

    Returns None if no valid GPS data is found or on parse errors.
    """
    try:
        tags = exifread.process_file(io.BytesIO(data), details=False, stop_tag="GPS GPSLatitude")
    except Exception as exc:
        logger.debug("EXIF parse failed for %s: %s", filename, exc)
        return None

    # Helper to convert EXIF rational to float
    def _to_degrees(value) -> Optional[float]:
        if not value:
            return None
        try:
            # exifread returns Ratio objects for DMS (degrees, minutes, seconds)
            d = float(value.values[0].num) / float(value.values[0].den)
            m = float(value.values[1].num) / float(value.values[1].den)
            s = float(value.values[2].num) / float(value.values[2].den)
            return d + (m / 60.0) + (s / 3600.0)
        except Exception:
            return None

    # Latitude
    lat_ref = str(tags.get("GPS GPSLatitudeRef", "")).strip().upper()
    lat_val = tags.get("GPS GPSLatitude")
    lat = _to_degrees(lat_val)
    if lat is not None and lat_ref == "S":
        lat = -lat

    # Longitude
    lon_ref = str(tags.get("GPS GPSLongitudeRef", "")).strip().upper()
    lon_val = tags.get("GPS GPSLongitude")
    lon = _to_degrees(lon_val)
    if lon is not None and lon_ref == "W":
        lon = -lon

    # Altitude
    alt = None
    alt_val = tags.get("GPS GPSAltitude")
    alt_ref = str(tags.get("GPS GPSAltitudeRef", "")).strip()
    if alt_val:
        try:
            alt = float(alt_val.values[0].num) / float(alt_val.values[0].den)
            if alt_ref == "1":  # below sea level
                alt = -alt
        except Exception:
            alt = None

    # Accuracy (DOP) - GPS HDOP if available
    accuracy = None
    dop_val = tags.get("GPS GPSDOP") or tags.get("GPS GPSHPositioningError")
    if dop_val:
        try:
            accuracy = float(dop_val.values[0].num) / float(dop_val.values[0].den)
        except Exception:
            accuracy = None

    # Timestamp
    captured_at = None
    dt_tag = tags.get("EXIF DateTimeOriginal") or tags.get("EXIF DateTimeDigitized") or tags.get("Image DateTime")
    if dt_tag:
        # EXIF format: "YYYY:MM:DD HH:MM:SS"
        try:
            dt_str = str(dt_tag).replace(":", "-", 2)
            captured_at = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").isoformat()
        except Exception:
            captured_at = None

    if lat is None or lon is None:
        return None

    return SpatialMetadata(
        latitude=lat,
        longitude=lon,
        altitude_m=alt,
        accuracy_m=accuracy,
        captured_at=captured_at,
        source_file=filename,
    )


def _encode_jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise ValueError("Failed to encode JPEG frame")
    return buf.tobytes()


def _downscale_image(image: np.ndarray, max_dim: int = MAX_DIMENSION) -> np.ndarray:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest > max_dim:
        scale = max_dim / float(longest)
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image


def extract_video_frames(video_path: str, max_frames: int) -> list[bytes]:
    """Sample ``max_frames`` evenly-spaced JPEG frames from a video file."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video file")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            # Fallback: read sequentially until max_frames reached.
            raw: list[np.ndarray] = []
            while len(raw) < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                raw.append(frame)
            frames = [_encode_jpeg(_downscale_image(f)) for f in raw]
        else:
            indices = np.linspace(0, max(total - 1, 0), min(max_frames, total)).astype(int)
            frames = []
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frame = cap.read()
                if ok:
                    frames.append(_encode_jpeg(_downscale_image(frame)))
    finally:
        cap.release()

    if not frames:
        raise ValueError("No decodable frames found in video")
    return frames

def process_uploads(
    uploads: list[UploadFile],
    temp_dir: str,
    max_video_frames: int,
    max_upload_bytes: int,
) -> MediaBundle:
    """Classify, normalise and sample the uploaded media into a MediaBundle."""
    bundle = MediaBundle()
    os.makedirs(temp_dir, exist_ok=True)

    for upload in uploads:
        filename = upload.filename or "unnamed"
        try:
            data = upload.file.read()
        except Exception as exc:  # pragma: no cover - defensive
            bundle.log.append({"filename": filename, "kind": "unknown", "status": "error", "detail": str(exc)})
            continue
        finally:
            upload.file.close()

        if not data:
            bundle.log.append({"filename": filename, "kind": "unknown", "status": "skipped", "detail": "empty file"})
            continue
        if len(data) > max_upload_bytes:
            bundle.log.append({"filename": filename, "kind": "unknown", "status": "skipped", "detail": "file exceeds size limit"})
            continue

        kind = classify_file(filename, upload.content_type)
        if kind is None:
            bundle.log.append({"filename": filename, "kind": "unknown", "status": "skipped", "detail": "unsupported file type"})
            continue

        try:
            if kind == "image":
                part = _process_image(data, filename)
            else:
                part = _process_video(data, filename, temp_dir, max_video_frames)
        except Exception as exc:
            logger.warning("Media processing failed for %s: %s", filename, exc)
            bundle.log.append({"filename": filename, "kind": kind, "status": "error", "detail": str(exc)})
            continue

        bundle.parts.append(part)
        bundle.log.append(
            {
                "filename": filename,
                "kind": kind,
                "status": "ok",
                "frames": len(part.frames) if part.kind == "video" else 0,
            }
        )

    return bundle


def _process_image(data: bytes, filename: str) -> MediaPart:
    # Extract EXIF/GPS before we re-encode (original bytes needed)
    spatial = _extract_exif_gps(data, filename)

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Corrupt or unsupported image (HEIC/RAW is not supported)")
    image = _downscale_image(image)
    jpeg_bytes = _encode_jpeg(image)
    return MediaPart(kind="image", filename=filename, mime_type="image/jpeg", bytes=jpeg_bytes, spatial=spatial)


def _process_video(data: bytes, filename: str, temp_dir: str, max_frames: int) -> MediaPart:
    tmp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{filename}")
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(data)
        frames = extract_video_frames(tmp_path, max_frames)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return MediaPart(
        kind="video",
        filename=filename,
        mime_type="video/mp4",
        frames=[("image/jpeg", frame) for frame in frames],
        spatial=None,
    )


def ensure_temp_dir(temp_dir: str) -> None:
    os.makedirs(temp_dir, exist_ok=True)

