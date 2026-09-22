#!/data/data/com.termux/files/usr/bin/bash

cd "$(dirname "$0")"
source venv/bin/activate

if ! redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

echo "Redis:"
redis-cli ping

echo "Starting AI Agency with Gunicorn..."

exec gunicorn -c gunicorn.conf.py app:app
