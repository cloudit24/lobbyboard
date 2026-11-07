#!/bin/sh
# Applies the port saved in Admin > Network settings: writes it to .env and
# restarts the containers. Run from the project folder on the server.
set -e
cd "$(dirname "$0")/.."
PORT=$(docker compose exec -T web python -c "import json;print(json.load(open('/data/network.json'))['port'])")
if grep -q '^PORT=' .env; then sed -i "s/^PORT=.*/PORT=$PORT/" .env; else echo "PORT=$PORT" >> .env; fi
docker compose up -d
echo "Now listening on port $PORT"
