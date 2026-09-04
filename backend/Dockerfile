FROM python:3.11-slim

# Prevent Python from writing pyc files & buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run as non-root user for production security
RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render injects PORT; default to 8000 for local/docker-compose runs
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
