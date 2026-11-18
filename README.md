# clip-engine

GPU worker for a faceless GTA 6 commentary-clip channel. n8n orchestrates, Grok thinks,
this service does the heavy lifting: download -> WhisperX -> scene/loudness scoring ->
frame sampling -> compliance gate -> FFmpeg render (9:16 or 16:9, narration + captions).

The compliance gate ('app/compliance.py' + 'formats.json') refuses any plan that is not
mostly narration, has long raw clips, or lacks captions/hook. That is what keeps videos
in "commentary" territory instead of reused content.

## Deploy (Kaggle, free GPU)
1. New notebook -> Accelerator GPU, Internet On.
2. Add Secrets: WORKER_API_KEY, N8N_TUNNEL_WEBHOOK, GITHUB_TOKEN (repo is private), (HF_TOKEN optional).
3. Paste the cells from 'kaggle/worker_notebook.py' and run with Save Version (not interactive).
4. The notebook starts the API behind a Cloudflare quick tunnel and POSTs the fresh
   'worker_url' to your n8n webhook, so n8n always knows where the worker is.
5. It shuts itself down after 5 minutes with no requests and no running job, so the
   GPU quota is not wasted.

Kaggle limits: weekly GPU quota, sessions end after ~9-12 hours, and the tunnel URL changes
every run. That is why the URL is pushed to n8n instead of hard-coded.

## Endpoints
POST /ingest  ·  POST /analyze/{job}  ·  GET /analysis/{job}  ·  POST /validate
POST /render  ·  GET /status/{job}  ·  GET /formats  ·  files under /files/{job}/

See docs/n8n-flow.md for the workflow and prompts/ for the Grok prompts.

Env: JOBS_DIR, STREAMER_VOLUME (default 0.12, 0 = mute), WHISPER_MODEL, WHISPER_DEVICE, FONT_FILE.
