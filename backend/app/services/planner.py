"""Turn a sentence into an edit decision list.

Rule-based on purpose. A language model is useful for the fuzzy choices (what
"elegant" means), but the output must be a strict structure that a human can
review and a renderer can execute. Rules give deterministic, explainable plans;
an LLM can be layered on top for the phrasing, not for the control flow.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..schemas_extra import AutoPlan, PlanSegment, SkippedSegment
from .analysis import dedupe

TITLE_LINE = re.compile(r"^[A-Z0-9][A-Z0-9 &'\-\.]{2,40}$")


def extract_titles(prompt: str) -> list[str]:
    """Upper-case lines in the prompt are the user's own title list."""
    titles = []
    for raw in prompt.splitlines():
        line = raw.strip().lstrip("0123456789.-) ").strip()
        if line and TITLE_LINE.match(line) and len(line.split()) <= 6:
            titles.append(line)
    return titles


def wants(prompt: str, *needles: str) -> bool:
    low = prompt.lower()
    return any(n in low for n in needles)


def build_plan(
    prompt: str,
    analysed: list[dict],
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    music_media_id: str | None = None,
    min_quality: float = 0.22,
    max_total_seconds: float = 180.0,
) -> AutoPlan:
    kept, dropped = dedupe(analysed)

    # Quality gate: drop shaky, dark or soft shots before they cost render time.
    survivors: list[dict] = []
    for seg in kept:
        if seg["quality"] < min_quality:
            dropped.append({"source_id": seg["source_id"], "start": seg["start"],
                            "reason": f"quality {seg['quality']:.2f} below threshold"})
        else:
            survivors.append(seg)

    # Longest, best shots first when trimming to length; otherwise keep the
    # order the footage was shot in, which is usually the walking order.
    order_mode = "quality" if wants(prompt, "best parts", "highlights", "short") else "source"
    if order_mode == "quality":
        survivors.sort(key=lambda s: s["quality"], reverse=True)

    titles = extract_titles(prompt)
    if titles and wants(prompt, "order", "arrange", "sequence", "logical"):
        # Sort shots by where their title appears in the user's list.
        rank = {t: i for i, t in enumerate(titles)}
        survivors.sort(key=lambda s: rank.get(str(s.get("title", "")), 999))

    segments: list[PlanSegment] = []
    total = 0.0
    for index, seg in enumerate(survivors):
        if total >= max_total_seconds:
            dropped.append({"source_id": seg["source_id"], "start": seg["start"],
                            "reason": "beyond target length"})
            continue
        # Cap a single shot so a 40-second take does not swallow the video.
        length = min(seg["duration"], 6.0)
        total += length
        title = None
        if titles:
            title = titles[min(index, len(titles) - 1)]
        segments.append(PlanSegment(
            source_id=seg["source_id"],
            start=seg["start"],
            end=round(seg["start"] + length, 3),
            order=len(segments) + 1,
            title=title,
            motion="kenburns" if seg["duration"] >= 2.0 else "static",
            quality=seg["quality"],
            note="duplicate risk" if seg["sharpness"] < 0.1 else None,
        ))

    keep_original_audio = not wants(
        prompt, "remove the original audio", "remove audio", "no audio", "mute"
    )
    music = music_media_id
    if wants(prompt, "music") and music is None:
        music = None

    plan = AutoPlan(
        prompt=prompt,
        width=width,
        height=height,
        fps=fps,
        segments=segments,
        skipped=[SkippedSegment(source_id=d["source_id"], reason=d["reason"]) for d in dropped],
        transitions={
            "type": "dissolve" if wants(prompt, "transition", "smooth", "elegant") else "none",
            "duration": 0.4,
        },
        audio={
            "keep_original": keep_original_audio and music is None,
            "music_media_id": music,
            "duck_db": -12,
        },
        cards={
            "intro": _first_upper_line(prompt) if wants(prompt, "opening", "title", "intro") else None,
            "outro": _outro_line(prompt) if wants(prompt, "closing", "end card", "call to action") else None,
        },
        estimated_seconds=round(total, 2),
    )

    if titles and len(titles) > len(segments):
        plan.warnings.append(
            f"{len(titles)} titles but only {len(segments)} usable shots; "
            "some titles were not placed."
        )
    if not segments:
        plan.warnings.append("No usable shots found. Check the footage or lower the quality threshold.")
    if music is None and not keep_original_audio:
        plan.warnings.append(
            "Original audio will be removed but no music track was supplied, "
            "so the video will be silent."
        )
    return plan


def _first_upper_line(prompt: str) -> str | None:
    for raw in prompt.splitlines():
        line = raw.strip()
        if TITLE_LINE.match(line) and len(line.split()) <= 8:
            return line
    return None


def _outro_line(prompt: str) -> str | None:
    match = re.search(r"(call[^\n.]{0,40}|whatsapp[^\n.]{0,40})", prompt, re.I)
    return match.group(1).strip() if match else "Thank you for watching"


def summarise(plan: AutoPlan) -> dict:
    """Human-readable report of what the plan does, shown before rendering."""
    return {
        "shots": len(plan.segments),
        "dropped": len(plan.skipped),
        "seconds": plan.estimated_seconds,
        "titles": [s.title for s in plan.segments if s.title],
        "audio": "music" if plan.audio.get("music_media_id") else (
            "original" if plan.audio.get("keep_original") else "silent"),
        "warnings": plan.warnings,
    }
