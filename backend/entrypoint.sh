#!/usr/bin/env bash
set -euo pipefail

ROLE="${GRANTSCOPE_PROCESS_TYPE:-web}"

if [[ "$ROLE" == "worker" ]]; then
  echo "Starting GrantScope worker (GRANTSCOPE_PROCESS_TYPE=worker)"
  exec python -m app.worker
fi

echo "Starting GrantScope web server (GRANTSCOPE_PROCESS_TYPE=web)"
exec gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 120 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --capture-output

