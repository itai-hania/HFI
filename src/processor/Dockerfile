# Processor Service Dockerfile
# ============================
# Multi-stage build for optimized image size and security
#
# Architecture Decisions:
# 1. Multi-stage build: Separates build dependencies from runtime (smaller image)
# 2. python:3.11-slim: Balances size (~120MB base) vs functionality
# 3. Non-root user: Security best practice, prevents privilege escalation
# 4. ffmpeg: Required for yt-dlp video processing (HLS, transcoding)
# 5. Explicit layer ordering: Optimizes Docker cache usage

# Stage 1: Builder - Install Python dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
# gcc: Required for compiling some Python packages (e.g., cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY src/processor/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Final lightweight image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
# ffmpeg: Required for yt-dlp video processing (converts streams to MP4)
# curl: Utility for health checks and debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage (avoids build deps in final image)
COPY --from=builder /root/.local /root/.local

# Add Python packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Set Python environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy all source packages
COPY src/ /app/src/
ENV PYTHONPATH=/app/src

# Create directories for data persistence
RUN mkdir -p /app/data/media /app/data /app/config

# Create non-root user for security
# UID 1000 is standard for first user, matches common host UIDs
RUN useradd -m -u 1000 processor && \
    chown -R processor:processor /app

# Switch to non-root user
USER processor

# Health check: Verify Python can import modules
# Runs every 30s, if 3 consecutive failures, container marked unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from processor.processor import TweetProcessor" || exit 1

# Expose no ports (this is a worker service, not an API)

# Labels for metadata
LABEL maintainer="HFI Team"
LABEL service="processor"
LABEL description="Translates English tweets to Hebrew and downloads media"

# Default command: Run the processor in polling mode
CMD ["python", "-m", "processor.main"]
