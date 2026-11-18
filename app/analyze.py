import os, re, json, subprocess
from pathlib import Path
import numpy as np

HYPE = re.compile(r"\b(no way|let'?s go|bro|what the|oh my|insane|crazy|wait|"
                  r"yo+|bruh|chase|wanted|escape|mission|objective|heist|"
                  r"passed|failed|complete[d]?|checkpoint)\b", re.I)


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def extract_audio(src: Path, wav: Path):
    _run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)])


def transcribe(wav: Path) -> list[dict]:
    import whisperx
    device = os.getenv("WHISPER_DEVICE", "cuda")
    compute = os.getenv("WHISPER_COMPUTE", "float16" if device == "cuda" else "int8")
    model = whisperx.load_model(os.getenv("WHISPER_MODEL", "large-v3"), device,
                                compute_type=compute)
    audio = whisperx.load_audio(str(wav))
    result = model.transcribe(audio, batch_size=int(os.getenv("WHISPER_BATCH", "8")))
    align_model, meta = whisperx.load_align_model(result["language"], device)
    result = whisperx.align(result["segments"], align_model, meta, audio, device)
    tok = os.getenv("HF_TOKEN")
    if tok:  # optional speaker labels
        from whisperx.diarize import DiarizationPipeline
        diar = DiarizationPipeline(use_auth_token=tok, device=device)(audio)
        result = whisperx.assign_word_speakers(diar, result)
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip(),
             "speaker": s.get("speaker")} for s in result["segments"]]


def scene_cuts(src: Path) -> list[float]:
    from scenedetect import detect, ContentDetector
    return [s[0].get_seconds() for s in detect(str(src), ContentDetector(threshold=27))]


def loudness(wav: Path) -> np.ndarray:
    import soundfile as sf
    data, sr = sf.read(str(wav))
    n = int(len(data) // sr)
    return np.array([float(np.sqrt(np.mean(data[i*sr:(i+1)*sr] ** 2))) for i in range(n)])


def _z(x):
    x = np.asarray(x, dtype=float)
    return (x - x.mean()) / (x.std() + 1e-9)


def candidates(duration, segs, cuts, rms, win=(8, 18), step=4, top=12) -> list[dict]:
    wins = []
    for L in (win[0], 12, win[1]):
        for s in np.arange(0, max(duration - L, 1), step):
            wins.append((float(s), float(s + L)))
    loud = np.array([rms[int(s):int(e)].mean() if int(e) <= len(rms) else 0 for s, e in wins])
    cutn = np.array([sum(s <= c < e for c in cuts) for s, e in wins])
    kw, txt = [], []
    for s, e in wins:
        t = " ".join(x["text"] for x in segs if x["start"] < e and x["end"] > s)
        txt.append(t)
        kw.append(len(HYPE.findall(t)) + len(t.split()) / 40)
    score = 0.45 * _z(loud) + 0.35 * _z(kw) + 0.2 * _z(cutn)
    order = np.argsort(-score)
    picked = []
    for i in order:
        s, e = wins[i]
        if all(e <= p["start"] or s >= p["end"] for p in picked):
            picked.append({"id": f"c{len(picked)+1}", "start": s, "end": e,
                           "score": round(float(score[i]), 3), "text": txt[i]})
        if len(picked) >= top:
            break
    return sorted(picked, key=lambda p: p["start"])


def frames(src: Path, cands: list[dict], out: Path):
    out.mkdir(exist_ok=True)
    for c in cands:
        c["frames"] = []
        for k, frac in enumerate((0.15, 0.5, 0.85)):
            t = c["start"] + (c["end"] - c["start"]) * frac
            f = out / f"{c['id']}_{k}.jpg"
            _run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(src),
                  "-frames:v", "1", "-vf", "scale=640:-2", str(f)])
            c["frames"].append(f"frames/{f.name}")


def outline(segs, chunk=60) -> list[dict]:
    """Compact transcript in 60s blocks for the LLM to find missions/moments."""
    blocks, cur, t0 = [], [], 0.0
    for s in segs:
        if s["start"] - t0 >= chunk and cur:
            blocks.append({"t": round(t0), "text": " ".join(cur)})
            cur, t0 = [], s["start"]
        cur.append(s["text"])
    if cur:
        blocks.append({"t": round(t0), "text": " ".join(cur)})
    return blocks


def run(job_dir: Path, duration: float) -> dict:
    src, wav = job_dir / "source.mp4", job_dir / "audio.wav"
    extract_audio(src, wav)
    segs = transcribe(wav)
    cuts, rms = scene_cuts(src), loudness(wav)
    cands = candidates(duration, segs, cuts, rms)
    frames(src, cands, job_dir / "frames")
    result = {"duration": duration, "outline": outline(segs),
              "candidates": cands, "transcript": segs}
    (job_dir / "analysis.json").write_text(json.dumps(result))
    return result
