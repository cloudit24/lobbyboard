FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Static files are baked into the image (served by WhiteNoise).
RUN SECRET_KEY="$(python -c "import secrets; print(secrets.token_urlsafe(50))")" python manage.py collectstatic --noinput -v0 \
 && useradd --system --uid 1000 app && mkdir -p /data && chown -R app /data /app
USER app

EXPOSE 8000
VOLUME ["/data"]
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
