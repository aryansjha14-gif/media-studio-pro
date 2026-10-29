"""End-to-end smoke test against the in-process ASGI app (no server needed).

    python scripts/smoke_test.py

Runs the full pipeline with AI_PROVIDER=mock: upload -> adjust -> prompt edit
(job poll) -> text-to-image -> video trim -> text-to-video. Prints PASS/FAIL per
step and exits non-zero on any failure. Use this in CI.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AI_PROVIDER", "mock")

import httpx
from PIL import Image

from app.main import app


def make_test_image(path: Path) -> None:
    img = Image.new("RGB", (640, 480), (30, 90, 160))
    for x in range(0, 640, 40):
        for y in range(0, 480, 40):
            if (x // 40 + y // 40) % 2 == 0:
                img.paste((230, 230, 240), (x, y, x + 40, y + 40))
    img.save(path, "JPEG")


def make_test_video(path: Path) -> bool:
    import subprocess

    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=12:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP video steps (ffmpeg unavailable: {exc})")
        return False


async def wait_job(client: httpx.AsyncClient, job_id: str, timeout: float = 120) -> dict:
    waited = 0.0
    while waited < timeout:
        r = await client.get(f"/v1/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        if job["status"] in ("succeeded", "failed"):
            return job
        await asyncio.sleep(0.3)
        waited += 0.3
    raise TimeoutError(f"job {job_id} did not finish in {timeout}s")


async def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        img_path = tmp_dir / "test.jpg"
        make_test_image(img_path)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            check("health", (await client.get("/health")).json()["status"] == "ok")

            with img_path.open("rb") as fh:
                r = await client.post("/v1/media", files={"file": ("test.jpg", fh, "image/jpeg")})
            check("upload image", r.status_code == 201, r.text)
            asset = r.json()
            media_id = asset["id"]
            check("image dimensions detected", asset["width"] == 640 and asset["height"] == 480)

            r = await client.post(
                f"/v1/images/{media_id}/adjust",
                json={"brightness": 1.2, "filter": "sepia", "resize": {"width": 320, "fit": "cover"}},
            )
            check("adjust image", r.status_code == 200, r.text)
            if r.status_code == 200:
                check("adjust resized output", r.json()["width"] == 320)

            r = await client.post(
                f"/v1/images/{media_id}/prompt",
                json={"prompt": "make it a rainy night in Mumbai, neon reflections"},
            )
            check("prompt edit accepted", r.status_code == 202, r.text)
            job = await wait_job(client, r.json()["id"])
            check("prompt edit job succeeded", job["status"] == "succeeded", str(job.get("error")))
            check("prompt edit produced asset", bool(job.get("asset")))

            r = await client.post("/v1/images/generate", json={"prompt": "a studio portrait, soft light"})
            job = await wait_job(client, r.json()["id"])
            check("text-to-image job", job["status"] == "succeeded", str(job.get("error")))

            r = await client.post(f"/v1/images/{media_id}/upscale?factor=2")
            job = await wait_job(client, r.json()["id"])
            check("upscale job", job["status"] == "succeeded", str(job.get("error")))
            if job.get("asset"):
                check("upscale doubled size", job["asset"]["width"] == 1280, str(job["asset"]["width"]))

            r = await client.post(f"/v1/images/{media_id}/remove-background")
            job = await wait_job(client, r.json()["id"])
            check("remove background job", job["status"] == "succeeded", str(job.get("error")))

            # --- video (needs ffmpeg) ------------------------------------- #
            vid_path = tmp_dir / "clip.mp4"
            if make_test_video(vid_path):
                with vid_path.open("rb") as fh:
                    r = await client.post("/v1/media", files={"file": ("clip.mp4", fh, "video/mp4")})
                check("upload video", r.status_code == 201, r.text)
                vid = r.json()
                check("video duration detected", (vid.get("duration") or 0) > 1.0, str(vid.get("duration")))

                r = await client.post(f"/v1/videos/{vid['id']}/trim", json={"start": 0.2, "end": 1.2})
                check("trim video", r.status_code == 200, r.text)
                if r.status_code == 200:
                    check("trimmed duration ~1s", abs((r.json().get("duration") or 0) - 1.0) < 0.4,
                          str(r.json().get("duration")))

                r = await client.post(f"/v1/videos/{vid['id']}/frame", json={"at": 0.5})
                check("extract frame", r.status_code == 200, r.text)

                r = await client.post("/v1/videos/generate", json={"prompt": "drone shot over ghats", "duration": 2})
                job = await wait_job(client, r.json()["id"])
                check("text-to-video job", job["status"] == "succeeded", str(job.get("error")))

            r = await client.get("/v1/jobs")
            check("list jobs", r.status_code == 200 and len(r.json()) >= 4)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
