#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

RUNTIME_PIP="/opt/anaconda3/bin/pip"

# Install into dev venv (editable — for testing/development)
pip install -e sage-solver-core/
pip install -e sage-solver-mcp/
pip install -e sage-solver-cloud/

# Install into runtime Python (non-editable — for Claude Desktop)
"$RUNTIME_PIP" install --quiet sage-solver-core/
"$RUNTIME_PIP" install --quiet sage-solver-mcp/
"$RUNTIME_PIP" install --quiet sage-solver-cloud/

echo ""
echo "All three packages reinstalled."
echo "  Dev venv:  $(which python) (editable)"
echo "  Runtime:   /opt/anaconda3/bin/python (non-editable, for Claude Desktop)"
