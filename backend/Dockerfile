FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates netcat-openbsd \
  && update-ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY certs ./certs
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN pip install -e . \
  && chmod +x ./docker-entrypoint.sh \
  && addgroup --system app \
  && adduser --system --ingroup app app \
  && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
