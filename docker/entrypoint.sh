#!/bin/sh
# Starts LobbyBoard: update the database, make the first admin if asked,
# clean old logs once a day, then serve.
set -e

mkdir -p /data/media /data/cache
python manage.py migrate --noinput
python manage.py ensure_admin

# Nightly log clean-up (Display settings > Keep logs for).
( while true; do python manage.py cleanup_logs || true; sleep 86400; done ) &

# Enquiries mailbox (Admin > Mail settings). Does nothing until switched on there.
python manage.py poll_mail --loop &

# Big uploads can take a while on a slow network: generous timeout.
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${WEB_WORKERS:-3}" \
  --timeout 600 \
  --access-logfile - \
  --forwarded-allow-ips "*"
