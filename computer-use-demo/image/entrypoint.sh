#!/bin/bash
set -e

./start_all.sh
./novnc_startup.sh

# Start FastAPI backend (replaces Streamlit)
cd $HOME
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info &

echo "✨ Computer Use Demo API is ready!"
echo "➡️  API: http://localhost:8000"
echo "➡️  API Docs: http://localhost:8000/docs"
echo "➡️  Frontend: http://localhost:8000/"
echo "➡️  VNC (noVNC): http://localhost:6080/vnc.html"

# Keep the container running
tail -f /dev/null
