#!/bin/bash
set -e

echo "Installing LTE Scanner Backend..."

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

echo "Installation complete!"
echo "Run 'source .venv/bin/activate' to activate the virtual environment"
