FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DB_PATH=/app/jhc.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jhc/ jhc/
COPY app/ app/
COPY static/ static/
COPY data/ data/
COPY snapshots/ snapshots/
COPY wsgi.py .

# The database is built from the committed snapshots at image build time,
# so the image carries its own data and needs no Fly volume.
RUN python -m jhc build-db

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--access-logfile", "-", "wsgi:app"]
