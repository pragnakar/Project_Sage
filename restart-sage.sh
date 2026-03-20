#!/usr/bin/env bash
# Restart sage-solver-cloud so the updated runner.py takes effect.
# Run this from the Project_Sage directory.

set -e

echo "=== SAGE Cloud Restart Script ==="

# Find and kill the running sage-cloud process
SAGE_PID=$(lsof -ti :$(python3 -c "import json,pathlib; d=json.loads(pathlib.Path.home().joinpath('.sage/cloud.json').read_text()); print(d['port'])" 2>/dev/null) 2>/dev/null || echo "")

if [ -n "$SAGE_PID" ]; then
    echo "Stopping sage-solver-cloud (PID $SAGE_PID)..."
    kill "$SAGE_PID"
    sleep 2
    echo "Stopped."
else
    echo "No running sage-solver-cloud found (or could not detect port)."
fi

# Start fresh
echo "Starting sage-solver-cloud..."
cd "$(dirname "$0")/sage-solver-cloud"
python3 -m sage_cloud &
CLOUD_PID=$!
echo "sage-solver-cloud started (PID $CLOUD_PID)"

# Wait for it to write discovery file
echo "Waiting for startup..."
sleep 3

if python3 -c "import json,pathlib; d=json.loads(pathlib.Path.home().joinpath('.sage/cloud.json').read_text()); print('  Ready at http://localhost:' + str(d['port']))"; then
    echo ""
    echo "=== Restart complete ==="
    echo "Now restart Claude Desktop (or reload the SAGE MCP) to reconnect."
else
    echo "WARNING: Discovery file not found. Check sage-solver-cloud logs."
fi
