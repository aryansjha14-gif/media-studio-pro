"""Video operations built on ffmpeg / ffprobe subprocesses.

ffmpeg is a hard dependency of this backend (installed in the Dockerfile).
`ffprobe` is used when present; when it is not, `probe()` falls back to parsing
`ffmpeg -i` output so a slim container image still works.

All functions are async wrappers so they never block the event loop.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe")


class FFmpegError(RuntimeError):
    """Raised for a missing binary, a non-zero exit, or a timeout."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def _run(cmd: list[str], timeout: float = 240.0) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(
            f"'{cmd[0]}' is not installed on this server — video features are unavailable. "
            "Install ffmpeg (apt-get install ffmpeg) or use the provided Dockerfile."
        ) from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FFmpegError(f"{cmd[0]} timed out after {timeout}s") from None
    if proc.returncode != 0:
        tail = stderr.decode("utf-8", "ignore")[-1500:]
        raise FFmpegError(f"{cmd[0]} failed ({proc.returncode}): {tail}")
    return stdout.decode("utf-8", "ignore")


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_DIMENSIONS_RE = re.compile(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_CODEC_RE = re.compile(r"Video:\s*([a-zA-Z0-9_]+)")


def _parse_ffmpeg_stderr(text: str) -> dict:
    """Extract the same fields as ffprobe from `ffmpeg -i` stderr."""
    info: dict = {"width": None, "height": None, "duration": 0.0, "fps": 0.0, "codec": None}
    if m := _DURATION_RE.search(text):
        h, mnt, sec = m.groups()
        info["duration"] = round(int(h) * 3600 + int(mnt) * 60 + float(sec), 3)
    if m := _DIMENSIONS_RE.search(text):
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    if m := _FPS_RE.search(text):
        info["fps"] = round(float(m.group(1)), 2)
    if m := _CODEC_RE.search(text):
        info["codec"] = m.group(1)
    info["has_audio"] = "Audio:" in text
    return info


async def probe(path: Path) -> dict:
    """Return {width, height, duration, fps, codec, has_audio}."""
    if FFPROBE:
        out = await _run(
            [
                FFPROBE, "-v", "error",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(path),
            ]
        )
        data = json.loads(out or "{}")
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), {}
        )
        has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
        fps = 0.0
        rate = video_stream.get("avg_frame_rate") or "0/1"
        try:
            num, den = rate.split("/")
            fps = round(float(num) / float(den), 2) if float(den) else 0.0
        except (ValueError, ZeroDivisionError):
            pass
        return {
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "duration": round(float(data.get("format", {}).get("duration") or 0.0), 3),
            "fps": fps,
            "codec": video_stream.get("codec_name"),
            "has_audio": has_audio,
        }

    # ffprobe absent — `ffmpeg -i` prints stream info to stderr and exits 1.
    if not ffmpeg_available():
        raise FFmpegError("neither ffprobe nor ffmpeg is installed on this server")
    proc = await asyncio.create_subprocess_exec(
        FFMPEG, "-hide_banner", "-i", str(path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return _parse_ffmpeg_stderr(stderr.decode("utf-8", "ignore"))


async def trim(src: Path, dst: Path, start: float, end: float, reencode: bool = True) -> Path:
    duration = max(0.1, end - start)
    if reencode:
        # Frame-accurate; re-encodes to H.264 so the phone can always play it.
        await _run([
            FFMPEG, "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(dst),
        ])
    else:
        # Stream copy — instant but snaps to the nearest keyframe.
        await _run([
            FFMPEG, "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
            "-c", "copy", "-movflags", "+faststart", str(dst),
        ])
    return dst


async def extract_frame(src: Path, dst: Path, at: float) -> Path:
    await _run([
        FFMPEG, "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(src),
        "-frames:v", "1", "-q:v", "2", str(dst),
    ])
    return dst


async def thumbnail(src: Path, dst: Path, at: float = 1.0) -> Path:
    await _run([
        FFMPEG, "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(src),
        "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "4", str(dst),
    ])
    return dst


async def merge(sources: list[Path], dst: Path) -> Path:
    """Concatenate clips. Re-encodes to a common format so mixed inputs work."""
    list_file = dst.with_suffix(".txt")
    lines = [f"file '{s.resolve().as_posix()}'" for s in sources]
    list_file.write_text("\n".join(lines), encoding="utf-8")
    try:
        await _run([
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(dst),
        ])
    finally:
        list_file.unlink(missing_ok=True)
    return dst


async def frames_to_video(frames_dir: Path, dst: Path, fps: int = 24, seconds: float = 4.0) -> Path:
    """Used by the offline mock provider to synthesise a placeholder clip."""
    await _run([
        FFMPEG, "-y", "-framerate", str(fps), "-i", str(frames_dir / "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", f"{seconds:.2f}",
        "-movflags", "+faststart", str(dst),
    ])
    return dst


async def mux_audio(video: Path, audio: Path, dst: Path) -> Path:
    await _run([
        FFMPEG, "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(dst),
    ])
    return dst


async def make_proxy(src: Path, dst: Path, height: int = 540) -> Path:
    """Low-resolution proxy so long or 4K footage scrubs smoothly in the app."""
    await _run([
        FFMPEG, "-y", "-i", str(src),
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
        str(dst),
    ])
    return dst


async def apply_speed(src: Path, dst: Path, factor: float) -> Path:
    """0.25x to 4x. Audio pitch is preserved with atempo."""
    factor = max(0.25, min(4.0, factor))
    video_pts = 1.0 / factor
    # atempo only accepts 0.5..2.0 per instance, so chain it.
    chain, remaining = [], factor
    while remaining > 2.0:
        chain.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        chain.append("atempo=0.5")
        remaining /= 0.5
    chain.append(f"atempo={remaining:.4f}")
    await _run([
        FFMPEG, "-y", "-i", str(src),
        "-filter_complex",
        f"[0:v]setpts={video_pts:.4f}*PTS[v];[0:a]{','.join(chain)}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", str(dst),
    ])
    return dst


async def reverse(src: Path, dst: Path) -> Path:
    await _run([
        FFMPEG, "-y", "-i", str(src),
        "-vf", "reverse", "-af", "areverse",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", str(dst),
    ])
    return dst


async def burn_subtitles(src: Path, srt: Path, dst: Path, font_size: int = 28) -> Path:
    """Burn an SRT into the frame. Needs libass; callers should catch FFmpegError."""
    style = f"Fontsize={font_size},Outline=1,Shadow=0,MarginV=40"
    await _run([
        FFMPEG, "-y", "-i", str(src),
        "-vf", f"subtitles={srt.resolve().as_posix()}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy", str(dst),
    ])
    return dst


async def mix_music(
    video: Path, music: Path, dst: Path, *, volume_db: float = -18.0,
    target_lufs: float = -14.0, fade_in: float = 1.0, fade_out: float = 1.5,
) -> Path:
    """Replace the audio bed with music, normalised to a social-safe loudness."""
    info = await probe(video)
    total = float(info.get("duration") or 0.0)
    fade_out_start = max(0.0, total - fade_out)
    af = (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11,"
        f"volume={volume_db}dB,"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fade_out_start:.2f}:d={fade_out}"
    )
    await _run([
        FFMPEG, "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(music),
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", str(dst),
    ])
    return dst
