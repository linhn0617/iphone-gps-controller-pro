#!/bin/bash
PORT="${1:-8090}"
echo "Stopping processes on port $PORT..."
lsof -ti tcp:$PORT | xargs -r kill -9 2>/dev/null || true
sudo lsof -ti tcp:$PORT | xargs -r sudo kill -9 2>/dev/null || true
echo "Done."
