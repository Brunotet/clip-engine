# Kaggle notebook for clip-engine. Paste each "# %%" block into its own cell.
# Settings: Accelerator = GPU T4 x2 (or P100), Internet = On. Run with Save Version.
# Add-ons > Secrets: WORKER_API_KEY, N8N_TUNNEL_WEBHOOK (your n8n webhook URL),
#                    GITHUB_TOKEN (repo is private), HF_TOKEN (optional)

# %% 1. install
import os, subprocess, sys
def sh(c): print(subprocess.run(c, shell=True, capture_output=True, text=True).stdout[-1500:])
sh("pip install -q fastapi 'uvicorn[standard]' yt-dlp whisperx 'scenedetect[opencv-headless]' soundfile")
sh("which ffmpeg || (apt-get update -qq && apt-get install -y -qq ffmpeg fonts-dejavu-core)")
sh("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared")

# %% 2. get the code
from kaggle_secrets import UserSecretsClient
S = UserSecretsClient()
def secret(k, default=""):
    try: return S.get_secret(k)
    except Exception: return default
tok = secret("GITHUB_TOKEN")
auth = f"{tok}@" if tok else ""
sh(f"rm -rf /kaggle/working/clip-engine && git clone https://{auth}github.com/Brunotet/clip-engine.git /kaggle/working/clip-engine")

# %% 3. start API + tunnel, tell n8n the new URL, stop after 5 idle minutes
import re, time, json, urllib.request
from pathlib import Path
os.chdir("/kaggle/working/clip-engine")
env = dict(os.environ, WORKER_API_KEY=secret("WORKER_API_KEY"), HF_TOKEN=secret("HF_TOKEN"),
           JOBS_DIR="/kaggle/working/jobs", WHISPER_DEVICE="cuda")
api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
                        "--port", "8002"], env=env, stdout=open("api.log", "w"), stderr=subprocess.STDOUT)
tun = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://localhost:8002", "--no-autoupdate"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
url = None
for line in tun.stdout:
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
    if m:
        url = m.group(0); break
print("WORKER URL:", url)
hook = secret("N8N_TUNNEL_WEBHOOK")
if hook and url:
    req = urllib.request.Request(hook, data=json.dumps({"worker_url": url}).encode(),
                                 headers={"Content-Type": "application/json"})
    print("n8n notified:", urllib.request.urlopen(req, timeout=30).status)
IDLE_SEC = 5 * 60
while api.poll() is None:
    time.sleep(30)
    busy = any('"state": "running"' in p.read_text()
               for p in Path("/kaggle/working/jobs").rglob("status.json"))
    idle = time.time() - os.path.getmtime("api.log")
    if not busy and idle > IDLE_SEC:
        print("idle shutdown"); break
api.terminate(); tun.terminate()
