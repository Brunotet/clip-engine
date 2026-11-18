import os, subprocess, textwrap
from pathlib import Path
import urllib.request

FONT = os.getenv("FONT_FILE", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DUCK = float(os.getenv("STREAMER_VOLUME", "0.12"))  # 0 = fully muted


def _wrap(t, w):
    return "\n".join(textwrap.wrap(t, w))


def _dt(textfile, size, y, enable=None):
    s = (f"drawtext=fontfile={FONT}:textfile={textfile}:fontsize={size}:fontcolor=white:"
         f"borderw=4:bordercolor=black:x=(w-text_w)/2:y={y}")
    return s + (f":enable='{enable}'" if enable else "")


def render_clip(src: Path, clip: dict, idx: int, aspect: str, hook: str | None,
                work: Path) -> Path:
    d = clip["end"] - clip["start"]
    out = work / f"part{idx:02d}.mp4"
    cap = work / f"cap{idx}.txt"
    cap.write_text(_wrap(clip["caption"], 22 if aspect == "9:16" else 42))
    inputs = ["-ss", f"{clip['start']:.2f}", "-t", f"{d:.2f}", "-i", str(src)]
    narr = None
    if clip.get("narration_url"):
        narr = work / f"narr{idx}.mp3"
        urllib.request.urlretrieve(clip["narration_url"], narr)
        inputs += ["-i", str(narr)]
    if aspect == "9:16":
        v = ("[0:v]split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
             "crop=1080:1920,boxblur=25:5[b];[fg]scale=1080:-2[f];"
             "[b][f]overlay=(W-w)/2:(H-h)/2[base];")
        cap_y, cap_size = "H-h-220", 54
    else:
        v = "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1[base];"
        cap_y, cap_size = "H-h-90", 46
    draws = [_dt(cap, cap_size, cap_y)]
    if hook and idx == 0:
        hf = work / "hook.txt"
        hf.write_text(_wrap(hook, 18 if aspect == "9:16" else 32))
        draws.append(_dt(hf, 78 if aspect == "9:16" else 64, "h*0.12", "between(t,0,2.5)"))
    v += f"[base]{','.join(draws)}[v]"
    if narr:
        a = (f"[0:a]volume={DUCK}[a0];[1:a]apad[a1];"
             "[a0][a1]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        a = f"[0:a]volume={DUCK}[a]"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", f"{v};{a}", "-map", "[v]",
           "-map", "[a]", "-t", f"{d:.2f}", "-c:v", "libx264", "-preset", "fast",
           "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
           "-ar", "44100", "-ac", "2", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1000:])
    return out


def render(job_dir: Path, plan: dict, aspect: str) -> Path:
    work = job_dir / "render"
    work.mkdir(exist_ok=True)
    src = job_dir / "source.mp4"
    parts = [render_clip(src, c, i, aspect, plan.get("hook_text"), work)
             for i, c in enumerate(plan["clips"])]
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    final = job_dir / "final.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(final)], check=True, capture_output=True)
    return final
