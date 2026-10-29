"""Footage analysis: the part that lets the app edit without being told shot by shot.

Everything here is local ffmpeg work plus Pillow statistics, so analysis of a long
video costs nothing but time. The results feed the planner (what to keep, in what
order) and the renderer (how to grade each shot).
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from . import video_ops

_SCENE_RE = re.compile(r"pts_time:([0-9.]+)")
_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")


async def scene_cuts(path: Path, threshold: float = 0.32) -> list[float]:
    """Timestamps (seconds) where the shot changes."""
    cmd = [
        video_ops.FFMPEG, "-hide_banner", "-i", str(path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    try:
        _, stderr = await _run_capture(cmd)
    except Exception:  # noqa: BLE001
        return []
    return sorted({round(float(m), 3) for m in _SCENE_RE.findall(stderr)})


async def silence_windows(path: Path, noise_db: int = -32, min_len: float = 0.7) -> list[tuple[float, float]]:
    cmd = [
        video_ops.FFMPEG, "-hide_banner", "-i", str(path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_len}",
        "-f", "null", "-",
    ]
    try:
        _, stderr = await _run_capture(cmd)
    except Exception:  # noqa: BLE001
        return []
    starts = [float(m) for m in _SILENCE_START.findall(stderr)]
    ends = [float(m) for m in _SILENCE_END.findall(stderr)]
    return list(zip(starts, ends + [starts[-1] + min_len] if len(starts) > len(ends) else ends))


async def _run_capture(cmd: list[str]) -> tuple[str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    return "", stderr.decode("utf-8", "ignore")


def _frame_stats(frame_path: Path) -> dict:
    """Sharpness and exposure of one sampled frame, without numpy."""
    img = Image.open(frame_path).convert("L")
    img.thumbnail((480, 480))
    edges = img.filter(ImageFilter.FIND_EDGES)
    sharpness = ImageStat.Stat(edges).stddev[0] / 64.0        # ~0..1
    mean = ImageStat.Stat(img).mean[0] / 255.0                # 0..1
    return {"sharpness": round(min(1.0, sharpness), 3), "luma": round(mean, 3)}


def _average_hash(frame_path: Path, size: int = 8) -> str:
    img = Image.open(frame_path).convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def hamming(a: str, b: str) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


async def analyse_clip(path: Path, media_id: str, *, samples: int = 6) -> dict:
    """Probe a clip, split it into shots, and score each shot."""
    info = await video_ops.probe(path)
    duration = float(info.get("duration") or 0.0)
    cuts = await scene_cuts(path)
    boundaries = [0.0] + [c for c in cuts if 0.4 < c < duration - 0.4] + [duration]

    segments: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for index in range(len(boundaries) - 1):
            start, end = boundaries[index], boundaries[index + 1]
            if end - start < 0.6:
                continue
            mid = (start + end) / 2
            frame = tmp_dir / f"f_{index}.jpg"
            try:
                await video_ops.extract_frame(path, frame, mid)
                stats = _frame_stats(frame)
                frame_hash = _average_hash(frame)
            except Exception:  # noqa: BLE001
                stats, frame_hash = {"sharpness": 0.5, "luma": 0.5}, ""
            quality = round(0.65 * stats["sharpness"] + 0.35 * (1 - abs(stats["luma"] - 0.5) * 2), 3)
            segments.append({
                "source_id": media_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "quality": quality,
                "luma": stats["luma"],
                "sharpness": stats["sharpness"],
                "hash": frame_hash,
            })
    return {"media_id": media_id, "info": info, "segments": segments}


def dedupe(analysed: list[dict], threshold: int = 6) -> tuple[list[dict], list[dict]]:
    """Drop shots that look like a shot we already have. Returns (kept, dropped)."""
    kept: list[dict] = []
    dropped: list[dict] = []
    for clip in analysed:
        for seg in clip["segments"]:
            duplicate = next(
                (k for k in kept
                 if k["hash"] and seg["hash"] and hamming(k["hash"], seg["hash"]) <= threshold),
                None,
            )
            if duplicate is not None:
                dropped.append({"source_id": seg["source_id"], "start": seg["start"],
                                "reason": "duplicate of an earlier shot"})
            else:
                kept.append(seg)
    return kept, dropped
