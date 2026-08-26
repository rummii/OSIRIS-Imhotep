"""Media pipeline test: run a synthetic image + video through process_uploads
and verify down-scaling, JPEG re-encoding and video frame sampling."""
import io
import os
import sys
import tempfile
import traceback

import cv2
import numpy as np

from app.services.media_processor import process_uploads, classify_file


def build_image_bytes() -> bytes:
    img = np.zeros((400, 600, 3), dtype=np.uint8)
    img[:] = (40, 60, 90)
    cv2.rectangle(img, (50, 50), (250, 250), (0, 200, 255), -1)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def build_video_bytes(tmp: str) -> bytes:
    path = os.path.join(tmp, "synth.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for i in range(30):
        frame = np.full((120, 160, 3), i * 8, dtype=np.uint8)
        cv2.circle(frame, (80, 60), 30, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    with open(path, "rb") as fh:
        return fh.read()


def main() -> int:
    try:
        tmp = tempfile.mkdtemp()
        image_bytes = build_image_bytes()
        video_bytes = build_video_bytes(tmp)

        # classification
        assert classify_file("a.jpg", "image/jpeg") == "image"
        assert classify_file("clip.mp4", "video/mp4") == "video"
        assert classify_file("x.exe", None) is None
        print("CLASSIFY_OK")

        class FakeUpload:
            def __init__(self, name, content_type, data):
                self.filename = name
                self.content_type = content_type
                self.file = io.BytesIO(data)

        uploads = [
            FakeUpload("photo.jpg", "image/jpeg", image_bytes),
            FakeUpload("clip.mp4", "video/mp4", video_bytes),
            FakeUpload("junk.txt", "text/plain", b"hello"),
            FakeUpload("broken.jpg", "image/jpeg", b"not an image"),
        ]

        bundle = process_uploads(uploads, tempfile.mkdtemp(), max_video_frames=6, max_upload_bytes=50 * 1024 * 1024)
        print("MEDIA_LOG", bundle.log)

        kinds = {e["filename"]: e["status"] for e in bundle.log}
        assert kinds["photo.jpg"] == "ok", bundle.log
        assert kinds["clip.mp4"] == "ok", bundle.log
        assert kinds["junk.txt"] == "skipped", bundle.log
        assert kinds["broken.jpg"] == "error", bundle.log

        assert len(bundle.parts) == 2
        img_part = bundle.parts[0]
        assert img_part.kind == "image" and img_part.bytes[:2] == b"\xff\xd8", "image should be JPEG"
        vid_part = bundle.parts[1]
        assert vid_part.kind == "video"
        assert 1 <= len(vid_part.frames) <= 6
        assert all(f[0] == "image/jpeg" and f[1][:2] == b"\xff\xd8" for f in vid_part.frames)
        print("IMAGE_JPEG_OK bytes=", len(img_part.bytes))
        print("VIDEO_FRAMES_OK count=", len(vid_part.frames))

        print("MEDIA_PIPELINE_OK")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
