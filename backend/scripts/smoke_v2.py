"""v2 checks: resumable large upload, prompt planning, and a real auto-edit render.

    python scripts/smoke_v2.py

Generates test footage with ffmpeg, pushes it through the chunked-upload path in
several chunks, asks the planner for an edit decision list, then renders it and
probes the output. Exits non-zero on any failure.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AI_PROVIDER", "mock")

import httpx

from app.main import app

PROMPT = """GROUND FLOOR FOR RENT
LIVING ROOM
BEDROOM 1
KITCHEN
Remove the original audio and add soft background music.
Use smooth transitions and subtle zoom effects.
Add a professional opening and closing screen.
"""


def make_clips(tmp: Path) -> list[Path]:
    clips = []
    specs = [
        ("living.mp4", "testsrc2=size=640x360:rate=24:duration=4"),
        ("bedroom.mp4", "smptebars=size=640x360:rate=24:duration=3"),
        ("kitchen.mp4", "testsrc=size=640x360:rate=24:duration=3"),
    ]
    for name, src in specs:
        path = tmp / name
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-c:v", "libx264",
             "-pix_fmt", "yuv420p", str(path)],
            check=True, capture_output=True, timeout=120,
        )
        clips.append(path)
    return clips


async def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        clips = make_clips(tmp)
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=600) as client:
            health = (await client.get("/health")).json()
            features = health["features"]
            check("health reports feature totals",
                  features["total"] >= 280
                  and features["total"] == features["implemented"] + features["planned"],
                  str(features))
            check("upload limit is 20 GB", health["max_upload_gb"] == 20.0)

            feats = (await client.get("/v1/features/summary")).json()
            check("feature summary",
                  feats["total"] >= 280
                  and feats["implemented"] >= 100
                  and feats["total"] == feats["implemented"] + feats["planned"],
                  str(feats))

            # --- resumable upload in 3 chunks ---------------------------- #
            media_ids = []
            for clip in clips:
                data = clip.read_bytes()
                init = (await client.post("/v1/uploads", json={
                    "filename": clip.name, "total_bytes": len(data), "mime": "video/mp4",
                })).json()
                upload_id, chunk = init["upload_id"], max(1024, init["chunk_size"] // 64)
                offset = 0
                while offset < len(data):
                    piece = data[offset:offset + chunk]
                    r = await client.put(
                        f"/v1/uploads/{upload_id}?offset={offset}",
                        content=piece, headers={"content-type": "application/octet-stream"},
                    )
                    if r.status_code != 200:
                        break
                    offset = r.json()["received"]
                status = (await client.get(f"/v1/uploads/{upload_id}")).json()
                check(f"chunked upload complete: {clip.name}",
                      status["received"] == len(data) and status["complete"])
                asset = (await client.post(f"/v1/uploads/{upload_id}/complete")).json()
                check(f"asset registered: {clip.name}", "id" in asset, str(asset)[:200])
                media_ids.append(asset["id"])

            # resume behaviour: wrong offset must be rejected
            init = (await client.post("/v1/uploads", json={
                "filename": "x.mp4", "total_bytes": 4096, "mime": "video/mp4",
            })).json()
            bad = await client.put(f"/v1/uploads/{init['upload_id']}?offset=99", content=b"abc")
            check("offset mismatch rejected", bad.status_code == 409, str(bad.status_code))

            # --- plan ---------------------------------------------------- #
            plan_resp = await client.post("/v1/auto/plan", json={
                "prompt": PROMPT, "media_ids": media_ids, "width": 1280, "height": 720, "fps": 24,
            })
            check("plan created", plan_resp.status_code == 200, plan_resp.text[:300])
            plan = plan_resp.json()
            check("plan has shots", len(plan["segments"]) >= 3, str(len(plan.get("segments", []))))
            titles = [s["title"] for s in plan["segments"] if s.get("title")]
            check("titles extracted from prompt", "LIVING ROOM" in titles, str(titles))
            check("audio policy read from prompt", plan["audio"]["keep_original"] is False,
                  str(plan["audio"]))
            check("transitions enabled", plan["transitions"]["type"] == "dissolve",
                  str(plan["transitions"]))
            check("intro card from prompt", bool(plan["cards"]["intro"]), str(plan["cards"]))

            # --- render -------------------------------------------------- #
            render_resp = await client.post("/v1/auto/render", json={"plan": plan})
            check("render accepted", render_resp.status_code == 202, render_resp.text[:300])
            job_id = render_resp.json()["id"]

            job = None
            for _ in range(200):
                job = (await client.get(f"/v1/jobs/{job_id}")).json()
                if job["status"] in ("succeeded", "failed"):
                    break
                await asyncio.sleep(1.0)

            check("render job succeeded", job and job["status"] == "succeeded",
                  str(job.get("error"))[:400] if job else "no job")
            if job and job.get("asset"):
                asset = job["asset"]
                check("output is 720p", asset["width"] == 1280 and asset["height"] == 720,
                      f"{asset['width']}x{asset['height']}")
                check("output has duration", (asset["duration"] or 0) > 4.0, str(asset["duration"]))
                meta = asset.get("meta") or {}
                check("render report attached", meta.get("shots_rendered", 0) >= 3, str(meta)[:300])

                video = await client.get(asset["url"].replace("http://test", ""))
                check("rendered file downloadable", video.status_code == 200 and len(video.content) > 10000,
                      str(len(video.content) if video.status_code == 200 else video.status_code))

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("All v2 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
