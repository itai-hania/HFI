# Processor Service Dockerfile
# ============================
# Multi-stage build for optimized image size and security

# Stage 1: Builder - Install Python dependencies
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY src/processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Final lightweight image
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy globally installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy all source packages
COPY src/ /app/src/
ENV PYTHONPATH=/app/src

RUN mkdir -p /app/data/media /app/data /app/config

# Create non-root user for security
RUN useradd -m -u 1000 processor && \
    chown -R processor:processor /app

USER processor

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from processor.processor import TweetProcessor" || exit 1

LABEL maintainer="HFI Team"
LABEL service="processor"
LABEL description="Translates English tweets to Hebrew and downloads media"

CMD ["python", "-m", "processor.main"]
