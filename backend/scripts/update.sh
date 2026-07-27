#!/bin/bash
set -e

echo "Updating LTE Scanner Backend..."

git pull

source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head

echo "Update complete!"
