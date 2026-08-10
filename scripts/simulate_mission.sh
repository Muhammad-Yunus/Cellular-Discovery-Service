#!/bin/bash
# ================================================================================
# Simulate Mission Script - Cellular Discovery Service
# ================================================================================
# Script ini adalah wrapper untuk menjalankan simulate_mission.py dengan mudah.
# Mensimulasikan pergerakan GPS mock dan menjalankan mission scanning seluler.
# Semua parameter akan diteruskan ke Python script.
#
# Cara Penggunaan:
#   ./simulate_mission.sh --count 4 --min-dist 500 --max-dist 1000 --speed 40 --name "TEST-001"
#
# Atau dengan koordinat override:
#   ./simulate_mission.sh --count 4 --lat -6.1506 --lon 106.8967 --speed 40
#
# Atau dengan GPS real:
#   ./simulate_mission.sh --count 5 --min-dist 200 --max-dist 400
#
# ================================================================================

# Path ke direktori project (parent dari scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
BACKEND_DIR="${PROJECT_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"

# Activate virtual environment
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
    export PYTHONPATH="${BACKEND_DIR}:${PYTHONPATH}"
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found at ${VENV_DIR}"
    exit 1
fi

# Jalankan Python script dengan semua argument yang diteruskan
python3 "${SCRIPT_DIR}/simulate_mission.py" "$@"
