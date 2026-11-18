#!/usr/bin/env bash
# Local/other hosts: ./start.sh (Kaggle uses kaggle/worker_notebook.py)
exec uvicorn app.main:app --host 0.0.0.0 --port "$(printenv APP_PORT || echo 8002)"