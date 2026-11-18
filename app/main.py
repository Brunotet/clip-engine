import os, json, uuid, traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app import ingest, analyze, render, compliance

JOBS = Path(os.getenv("JOBS_DIR", "jobs"))
JOBS.mkdir(exist_ok=True)
KEY = os.getenv("WORKER_API_KEY", "")

app = FastAPI(title="clip-engine")
app.mount("/files", StaticFiles(directory=str(JOBS)), name="files")


def auth(k):
    if KEY and k != KEY:
        raise HTTPException(401, "bad key")


def status(job, **kw):
    p = JOBS / job / "status.json"
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur.update(kw)
    p.write_text(json.dumps(cur))


class IngestReq(BaseModel):
    url: str
    start: str | None = None
    end: str | None = None


class RenderReq(BaseModel):
    job_id: str
    plan: dict


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/formats")
def formats():
    return compliance.FORMATS


@app.post("/ingest")
def ingest_ep(r: IngestReq, bg: BackgroundTasks, x_api_key: str = Header("")):
    auth(x_api_key)
    job = uuid.uuid4().hex[:10]
    (JOBS / job).mkdir()
    status(job, stage="ingest", state="running")

    def go():
        try:
            meta = ingest.download(r.url, JOBS / job, r.start, r.end)
            status(job, state="done", meta=meta)
        except Exception:
            status(job, state="error", error=traceback.format_exc()[-800:])
    bg.add_task(go)
    return {"job_id": job}


@app.post("/analyze/{job}")
def analyze_ep(job: str, bg: BackgroundTasks, x_api_key: str = Header("")):
    auth(x_api_key)
    st = json.loads((JOBS / job / "status.json").read_text())
    dur = st["meta"]["duration"]
    status(job, stage="analyze", state="running")

    def go():
        try:
            analyze.run(JOBS / job, dur)
            status(job, state="done")
        except Exception:
            status(job, state="error", error=traceback.format_exc()[-800:])
    bg.add_task(go)
    return {"job_id": job}


@app.get("/analysis/{job}")
def analysis(job: str, x_api_key: str = Header("")):
    """Compact view for the LLM (no full transcript)."""
    auth(x_api_key)
    a = json.loads((JOBS / job / "analysis.json").read_text())
    return {"duration": a["duration"], "outline": a["outline"],
            "candidates": a["candidates"]}


@app.post("/validate")
def validate(plan: dict, x_api_key: str = Header("")):
    auth(x_api_key)
    errs = compliance.validate(plan)
    return {"ok": not errs, "errors": errs}


@app.post("/render")
def render_ep(r: RenderReq, bg: BackgroundTasks, x_api_key: str = Header("")):
    auth(x_api_key)
    errs = compliance.validate(r.plan)
    if errs:
        raise HTTPException(422, {"errors": errs})
    aspect = compliance.FORMATS[r.plan["format"]]["aspect"]
    status(r.job_id, stage="render", state="running")

    def go():
        try:
            render.render(JOBS / r.job_id, r.plan, aspect)
            status(r.job_id, state="done", output=f"files/{r.job_id}/final.mp4")
        except Exception:
            status(r.job_id, state="error", error=traceback.format_exc()[-800:])
    bg.add_task(go)
    return {"job_id": r.job_id}


@app.get("/status/{job}")
def get_status(job: str, x_api_key: str = Header("")):
    auth(x_api_key)
    return json.loads((JOBS / job / "status.json").read_text())
