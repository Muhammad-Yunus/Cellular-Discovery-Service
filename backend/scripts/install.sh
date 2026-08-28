#!/bin/bash
set -e

echo "========================================="
echo "Cellular Discovery Service - Production Install"
echo "========================================="
echo ""

# Check prerequisites
echo "[1/7] Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "Error: pip3 is required"; exit 1; }
python3 --version | grep -q "3.1[2-9]" || { echo "Error: Python 3.12+ is required"; exit 1; }
echo "  ✓ Python $(python3 --version)"

# Check PostgreSQL
echo "[2/7] Checking PostgreSQL..."
command -v psql >/dev/null 2>&1 || { echo "Error: PostgreSQL client is required"; exit 1; }
echo "  ✓ PostgreSQL found"

# Navigate to backend directory
cd "$(dirname "$0")/../backend"
echo ""
echo "[3/7] Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "  Using existing virtual environment"
else
    python3 -m venv .venv
    echo "  ✓ Virtual environment created"
fi

# Activate virtual environment
source .venv/bin/activate
echo ""
echo "[4/7] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install psutil
echo "  ✓ Dependencies installed"

# Database migrations
echo ""
echo "[5/7] Running database migrations..."
if [ -z "${DATABASE_URL}" ]; then
    source .env 2>/dev/null || true
fi

# Check if we can run migrations
if alembic check || alembic upgrade head 2>/dev/null; then
    echo "  ✓ Database migrations completed"
else
    echo "  ⚠ Skipping database migration (run manually if needed)"
fi

# Create logs directory
echo ""
echo "[6/7] Creating logs directory..."
mkdir -p logs
echo "  ✓ Logs directory created"

# Systemd service setup
echo ""
echo "[7/7] Setting up systemd service..."
SERVICE_FILE="/etc/systemd/system/lte-scanner.service"

if [ ! -f "$SERVICE_FILE" ] || [ "$(readlink -f /etc/systemd/system/lte-scanner.service 2>/dev/null)" != "$(pwd)/../lte-scanner.service" ]; then
    # Create symlink to service file
    sudo ln -sf "$(pwd)/../lte-scanner.service" "$SERVICE_FILE"
    echo "  ✓ Service file created"
else
    echo "  Service file already exists"
fi

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Configure .env file: vi $PWD/.env"
echo "  2. Start the service:"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable lte-scanner.service"
echo "     sudo systemctl start lte-scanner.service"
echo "  3. Check status:"
echo "     sudo systemctl status lte-scanner.service"
echo "  4. View logs:"
echo "     journalctl -u lte-scanner.service -f"
echo "     OR: tail -f $PWD/logs/app.log"
echo ""
echo "API Documentation: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "========================================="
