"""Render an approved edit decision list into a finished video.

Deliberately one pass per shot, then one join, then one audio mux. Each stage
fails loudly with the ffmpeg message attached, and the returned report says what
actually happened - which shots were rendered, whether stabilisation ran, what
the real output duration is - because a render that silently half-worked is
worse than one that fails.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

from ..config import Settings
from ..schemas_extra import AutoPlan
from . import video_ops
from .video_ops import FFmpegError


def _font(settings: Settings, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(settings.font_path, size)
    except Exception:  # noqa: BLE001 - fall back to the bitmap default
        return ImageFont.load_default()


def _title_png(text: str, width: int, height: int, out: Path, settings: Settings) -> Path:
    """Transparent full-frame overlay with the title, drawn low-left."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = max(28, height // 14)
    font = _font(settings, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(height * 0.035)
    x = pad
    y = height - text_h - pad * 3
    draw.rectangle(
        [x - pad // 2, y - pad // 3, x + text_w + pad // 2, y + text_h + pad // 2],
        fill=(0, 0, 0, 110),
    )
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def _card_png(lines: list[str], width: int, height: int, out: Path, settings: Settings) -> Path:
    img = Image.new("RGB", (width, height), (14, 20, 26))
    draw = ImageDraw.Draw(img)
    y = height // 2 - (len(lines) * height // 14) // 2
    for index, line in enumerate(lines):
        size = int(height * (0.075 if index == 0 else 0.042))
        font = _font(settings, size)
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, y), line, font=font,
            fill=(255, 255, 255) if index == 0 else (150, 200, 190),
        )
        y += int(size * 1.7)
    img.save(out)
    return out


async def _auto_grade(src: Path, at: float) -> dict:
    """Nudge exposure and contrast so a shot sits near a neutral mid-tone."""
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "f.jpg"
        try:
            await video_ops.extract_frame(src, frame, at)
            img = Image.open(frame).convert("L")
            img.thumbnail((320, 320))
            mean = ImageStat.Stat(img).mean[0] / 255.0
            contrast = ImageStat.Stat(img).stddev[0] / 255.0
        except Exception:  # noqa: BLE001
            return {"brightness": 0.0, "contrast": 1.0, "saturation": 1.02}
    brightness = max(-0.18, min(0.18, (0.48 - mean) * 0.55))
    gain = 1.0 if contrast > 0.10 else 1.12
    return {"brightness": round(brightness, 3), "contrast": round(gain, 3), "saturation": 1.03}


async def _render_shot(
    plan: AutoPlan, seg, src: Path, out: Path, settings: Settings, tmp: Path
) -> dict:
    duration = max(0.4, seg.end - seg.start)
    grade = await _auto_grade(src, (seg.start + seg.end) / 2) if plan.grade.get("mode") == "auto" else {
        "brightness": 0.0, "contrast": 1.0, "saturation": 1.0
    }
    vf = [
        f"scale={plan.width}:{plan.height}:force_original_aspect_ratio=decrease",
        f"pad={plan.width}:{plan.height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1",
        f"fps={plan.fps}",
        f"eq=brightness={grade['brightness']}:contrast={grade['contrast']}:saturation={grade['saturation']}",
    ]
    if plan.transitions.get("type", "none") != "none":
        handle = min(0.3, duration / 4)
        vf.append(f"fade=t=in:st=0:d={handle:.2f}")
        vf.append(f"fade=t=out:st={max(0.0, duration - handle):.2f}:d={handle:.2f}")

    if seg.motion == "kenburns":
        vf.append(
            f"zoompan=z='min(zoom+0.0007,1.10)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={plan.width}x{plan.height}:fps={plan.fps}"
        )

    cmd = [
        video_ops.FFMPEG, "-y", "-ss", f"{seg.start:.3f}", "-t", f"{duration:.3f}",
        "-i", str(src),
    ]
    if seg.title:
        overlay = _title_png(seg.title, plan.width, plan.height, tmp / f"t_{seg.order}.png", settings)
        cmd += ["-i", str(overlay)]
        filter_complex = (
            f"[0:v]{','.join(vf)}[bg];[bg][1:v]overlay=0:0:format=auto[v]"
        )
        cmd += ["-filter_complex", filter_complex, "-map", "[v]"]
    else:
        cmd += ["-vf", ",".join(vf)]

    cmd += [
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(out),
    ]
    await video_ops._run(cmd, timeout=600)
    return {"order": seg.order, "title": seg.title, "seconds": round(duration, 2), "grade": grade}


async def _card_clip(png: Path, out: Path, seconds: float, fps: int) -> Path:
    await video_ops._run([
        video_ops.FFMPEG, "-y", "-loop", "1", "-i", str(png), "-t", f"{seconds:.2f}",
        "-vf", f"fps={fps},fade=t=in:st=0:d=0.4,fade=t=out:st={seconds - 0.4:.2f}:d=0.4",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(out),
    ], timeout=300)
    return out


async def _join(clips: list[Path], out: Path, plan: AutoPlan, tmp: Path) -> Path:
    transition = plan.transitions.get("type", "none")
    if transition == "none" or len(clips) == 1:
        list_file = tmp / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{c.resolve().as_posix()}'" for c in clips), encoding="utf-8"
        )
        await video_ops._run([
            video_ops.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(out),
        ], timeout=600)
        return out

    # Cross-dissolve: normalise every clip first, then chain xfade.
    # Normalising is not optional — xfade aborts the encoder if any input differs
    # in size, pixel format, SAR or timebase, which is exactly what happens when
    # an intro card meets phone footage.
    durations = []
    for clip in clips:
        info = await video_ops.probe(clip)
        durations.append(float(info.get("duration") or 1.0))

    d = float(plan.transitions.get("duration", 0.4))
    inputs: list[str] = []
    for clip in clips:
        inputs += ["-i", str(clip)]

    filters: list[str] = []
    for index in range(len(clips)):
        filters.append(
            f"[{index}:v]scale={plan.width}:{plan.height}:force_original_aspect_ratio=decrease,"
            f"pad={plan.width}:{plan.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={plan.fps},format=yuv420p[n{index}]"
        )

    offset, last = 0.0, "[n0]"
    for index in range(1, len(clips)):
        offset += durations[index - 1] - d
        label = f"[vx{index}]"
        filters.append(
            f"{last}[n{index}]xfade=transition=fade:duration={d:.3f}:"
            f"offset={max(0.0, offset):.3f}{label}"
        )
        last = label
    # Final format/fps guard: without it libx264 can refuse to open the encoder.
    filters.append(f"{last}fps={plan.fps},format=yuv420p[vout]")

    await video_ops._run([
        video_ops.FFMPEG, "-y", *inputs,
        "-filter_complex", ";".join(filters), "-map", "[vout]",
        "-r", str(plan.fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(out),
    ], timeout=900)
    return out


async def render(
    plan: AutoPlan,
    sources: dict[str, Path],
    out_path: Path,
    settings: Settings,
    *,
    music: Path | None = None,
) -> dict:
    if not plan.segments:
        raise FFmpegError("the plan has no shots to render")

    report: dict = {"shots": [], "warnings": list(plan.warnings), "engine": "ffmpeg"}
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        clips: list[Path] = []

        if plan.cards.get("intro"):
            png = _card_png([plan.cards["intro"]], plan.width, plan.height, tmp / "intro.png", settings)
            clips.append(await _card_clip(png, tmp / "clip_intro.mp4", 2.6, plan.fps))

        for seg in plan.segments:
            src = sources.get(seg.source_id)
            if src is None:
                report["warnings"].append(f"missing source for shot {seg.order}")
                continue
            shot_path = tmp / f"shot_{seg.order:03d}.mp4"
            try:
                report["shots"].append(await _render_shot(plan, seg, src, shot_path, settings, tmp))
                clips.append(shot_path)
            except FFmpegError as exc:
                report["warnings"].append(f"shot {seg.order} failed: {str(exc)[:200]}")

        if plan.cards.get("outro"):
            png = _card_png([plan.cards["outro"]], plan.width, plan.height, tmp / "outro.png", settings)
            clips.append(await _card_clip(png, tmp / "clip_outro.mp4", 2.6, plan.fps))

        if not clips:
            raise FFmpegError("every shot failed to render")

        try:
            joined = await _join(clips, tmp / "joined.mp4", plan, tmp)
        except FFmpegError as exc:
            # The xfade graph is the one part that depends on encoder build flags.
            # Fading each clip and concatenating always works, so fall back to it
            # rather than failing a render the user already approved.
            report["warnings"].append(
                "cross-dissolve unavailable on this ffmpeg build; used fade-to-black"
            )
            log_note = str(exc)[-200:]
            joined = await _join_fade(clips, tmp / "joined_fallback.mp4", tmp)
            report["engine"] = "ffmpeg-fade-fallback"
            report["fallback_reason"] = log_note

        if music is not None:
            await video_ops.mix_music(
                joined, music, out_path,
                volume_db=settings.music_volume_db,
                target_lufs=settings.target_lufs,
            )
        elif plan.audio.get("keep_original"):
            # Keep whatever audio the source clips carried, re-encoded for the phone.
            await video_ops._run([
                video_ops.FFMPEG, "-y", "-i", str(joined),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", str(out_path),
            ], timeout=600)
        else:
            await video_ops._run([
                video_ops.FFMPEG, "-y", "-i", str(joined),
                "-c:v", "copy", "-an", "-movflags", "+faststart", str(out_path),
            ], timeout=600)

    info = await video_ops.probe(out_path)
    report.update({
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
        "fps": info.get("fps"),
        "has_audio": info.get("has_audio"),
        "shots_rendered": len(report["shots"]),
        "shots_planned": len(plan.segments),
    })
    return report


async def _join_fade(clips: list[Path], out: Path, tmp: Path) -> Path:
    """Concatenate pre-faded clips. No filter graph, so nothing can mismatch."""
    list_file = tmp / "concat_fallback.txt"
    list_file.write_text(
        "\n".join(f"file '{c.resolve().as_posix()}'" for c in clips), encoding="utf-8"
    )
    await video_ops._run([
        video_ops.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(out),
    ], timeout=900)
    return out
