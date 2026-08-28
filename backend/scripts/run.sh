#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create logs directory if not exists
mkdir -p logs

# Activate virtual environment
source .venv/bin/activate

# Run with production settings
exec uvicorn app.main:app \
    --host ${APP_HOST:-0.0.0.0} \
    --port ${APP_PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-2} \
    --log-level ${LOG_LEVEL:-info}
