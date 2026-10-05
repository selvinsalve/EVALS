#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ -d "$DIR/myenv" ]; then
    source "$DIR/myenv/bin/activate"
elif [ -d "$DIR/../myenv" ]; then
    source "$DIR/../myenv/bin/activate"
fi

echo "Starting DeepEval Synthesizer FastAPI Server on http://0.0.0.0:8000 ..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
