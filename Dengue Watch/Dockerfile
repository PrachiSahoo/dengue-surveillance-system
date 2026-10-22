# ==============================================================================
# DengueWatch Multi-Stage Production Dockerfile
# Enterprise Security: Non-Root Execution, Pinned Layers, Health Check
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Image
FROM python:3.11-slim AS runner

WORKDIR /app

# Create unprivileged system user for container security
RUN groupadd -r denguewatch && useradd -r -g denguewatch appuser

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Copy application source
COPY . /app

# Ensure proper permissions for database file creation
RUN chown -R appuser:denguewatch /app

USER appuser

EXPOSE 5000

# Docker Healthcheck targeting the REST API
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health')" || exit 1

ENTRYPOINT ["python", "app.py"]
