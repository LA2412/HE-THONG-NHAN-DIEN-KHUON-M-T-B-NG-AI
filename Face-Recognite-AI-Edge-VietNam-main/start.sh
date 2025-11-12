#!/usr/bin/env bash

# Start script for Face Retail AI project.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Python interpreter not found."
  exit 1
fi

$PYTHON_BIN -m pip install -r requirements.txt

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/deep-face-shop}"

if command -v mongo >/dev/null 2>&1; then
  mongo "$MONGO_URI" --eval 'db.runCommand({ ping: 1 })' >/dev/null
elif command -v mongosh >/dev/null 2>&1; then
  mongosh "$MONGO_URI" --eval 'db.runCommand({ ping: 1 })' >/dev/null
else
  echo "Mongo shell not found; skipping ping check."
fi

export MONGO_URI
export TF_ENABLE_ONEDNN_OPTS=0
export FLASK_DEBUG=${FLASK_DEBUG:-0}

exec "$PYTHON_BIN" app.py
