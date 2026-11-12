#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 local-server/server.py &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev -- --host 127.0.0.1 --port 5174
