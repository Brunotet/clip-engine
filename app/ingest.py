import os, subprocess, json
from pathlib import Path


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return float(json.loads(out.stdout)["format"]["duration"])


def download(url: str, job_dir: Path, start: str | None = None,
             end: str | None = None, max_height: int = 1080) -> dict:
    """Download a video. start/end like '01:20:00' to grab only part of a long VOD."""
    out = job_dir / "source.mp4"
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
        raise RuntimeError(res.stderr[-800:])
    title, _, uploader = res.stdout.strip().splitlines()[-1].partition("|||")
    return {"title": title, "uploader": uploader,
            "duration": probe_duration(out), "source_url": url}
