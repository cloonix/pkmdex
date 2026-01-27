#!/bin/bash
# Start the Pokemon Card Collection web interface

echo "Starting Pokemon Card Collection web interface..."
echo "Navigate to: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")"
uv run uvicorn src.web:app --host 0.0.0.0 --port 8000 --reload
