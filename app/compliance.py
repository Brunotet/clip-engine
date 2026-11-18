import json
from pathlib import Path

FORMATS = json.loads((Path(__file__).parent.parent / "formats.json").read_text())
WPS = 2.5  # narration words per second


def _narr_sec(c):
    return c.get("narration_sec") or len(c.get("narration_text", "").split()) / WPS


def validate(plan: dict) -> list[str]:
    """Gate before render. Returns a list of problems; empty list = OK."""
    fmt = FORMATS.get(plan.get("format"))
    if not fmt:
        return [f"unknown format: {plan.get('format')}"]
    clips, errs = plan.get("clips", []), []
    if not (fmt["min_clips"] <= len(clips) <= fmt["max_clips"]):
        errs.append(f"clip count must be {fmt['min_clips']}-{fmt['max_clips']}")
    if not plan.get("hook_text"):
        errs.append("missing hook_text")
    total = narr = 0.0
    for i, c in enumerate(clips, 1):
        d = c["end"] - c["start"]
        total += d
        narr += min(_narr_sec(c), d)
        if d > fmt["max_clip_sec"]:
            errs.append(f"clip {i} is {d:.0f}s, max {fmt['max_clip_sec']}s")
        if not c.get("narration_text") or not c.get("caption"):
            errs.append(f"clip {i} needs narration_text and caption (added value)")
    if total > fmt["max_total_sec"]:
        errs.append(f"total {total:.0f}s exceeds {fmt['max_total_sec']}s")
    if total and narr / total < fmt["min_narration_ratio"]:
        errs.append(f"narration covers {narr/total:.0%}, need {fmt['min_narration_ratio']:.0%}")
    return errs
