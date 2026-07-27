#!/bin/bash
set -e

source .venv/bin/activate

uvicorn app.main:app --host $APP_HOST --port $APP_PORT --reload
