#!/usr/bin/env bash
# stop.sh — stop all System B services started by start.sh

LOG="$(cd "$(dirname "$0")" && pwd)/logs"

if [ ! -d "$LOG" ]; then
    echo "No logs/ directory found — nothing to stop."
    exit 0
fi

stopped=0
for pidfile in "$LOG"/*.pid; do
    [ -f "$pidfile" ] || continue
    name="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "  stopped $name (pid $pid)"
        (( stopped++ )) || true
    fi
    rm -f "$pidfile"
done

[ "$stopped" -eq 0 ] && echo "No services were running." || echo ""
echo "Done."
