import os, subprocess, json
from pathlib import Path


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def _download_one(url, job_dir, start, end, max_height):
    out = job_dir / "source.mp4"
    if out.exists():
        out.unlink()
    cmd = ["yt-dlp", "-f",
           f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
           "--merge-output-format", "mp4", "--no-playlist",
           "-o", str(out), "--print", "%(title)s|||%(uploader)s",
           "--no-simulate"]
    ck = os.getenv("YT_COOKIES_TXT", "").strip()
    if ck:  # optional YouTube cookies (Netscape format) to pass the bot check
        cf = "/tmp/yt_cookies.txt"
        with open(cf, "w") as fh:
            fh.write(ck + "\n")
        os.chmod(cf, 0o600)
        cmd += ["--cookies", cf]
    if start or end:
        cmd += ["--download-sections", f"*{start or '0'}-{end or 'inf'}"]
    cmd.append(url)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not out.exists():
        raise RuntimeError(res.stderr[-600:])
    title, _, uploader = res.stdout.strip().splitlines()[-1].partition("|||")
    return {"title": title, "uploader": uploader,
            "duration": probe_duration(out), "source_url": url}


def download(url: str, job_dir: Path, start: str | None = None,
             end: str | None = None, max_height: int = 1080) -> dict:
    """url may be 'primary || fallback || START-END': if the primary fails
    (e.g. YouTube bot check) the fallback (e.g. a Twitch VOD) is tried, with its
    own optional START-END range (HH:MM:SS-HH:MM:SS)."""
    parts = [p.strip() for p in url.split("||")]
    attempts = [(parts[0], start, end)]
    if len(parts) > 1 and parts[1]:
        fs, _, fe = (parts[2] if len(parts) > 2 else "").partition("-")
        attempts.append((parts[1], fs or None, fe or None))
    errors = []
    for u, s, e in attempts:
        try:
            meta = _download_one(u, job_dir, s, e, max_height)
            meta["used_fallback"] = u != attempts[0][0]
            return meta
        except Exception as ex:
            errors.append(u + " -> " + str(ex)[-250:])
    raise RuntimeError(" | ".join(errors)[-800:])
