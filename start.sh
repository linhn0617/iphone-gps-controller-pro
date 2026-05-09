#!/bin/bash
set -e
cd "$(dirname "$0")"

PORT="${1:-8090}"

if [ ! -d venv ]; then
  echo "Building venv..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "  iPhone GPS Controller Pro"
echo "  ──────────────────────────"
echo "  http://localhost:${PORT}/"
echo ""
echo "  macOS requires root for USB tunnel (utun interface)"
echo ""

sudo -E "$(which python3)" -m backend.main "$PORT" &
BACKEND_PID=$!

sleep 2
open "http://localhost:${PORT}/"

cleanup() {
  echo ""
  echo "Stopping backend..."
  kill $BACKEND_PID 2>/dev/null || true
  sudo kill $BACKEND_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait $BACKEND_PID
