#!/bin/sh

set -eu

python /app/scheduler.py &
SCHEDULER_PID=$!

gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 2 \
    --access-logfile - \
    --error-logfile - \
    app:app &

GUNICORN_PID=$!

shutdown()
{
    echo "Stopping reporting services..."

    kill -TERM "$GUNICORN_PID" 2>/dev/null || true
    kill -TERM "$SCHEDULER_PID" 2>/dev/null || true

    wait "$GUNICORN_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true

    exit 0
}

trap shutdown TERM INT

while kill -0 "$GUNICORN_PID" 2>/dev/null \
   && kill -0 "$SCHEDULER_PID" 2>/dev/null
do
    sleep 2
done

echo "A reporting process stopped unexpectedly."

shutdown
