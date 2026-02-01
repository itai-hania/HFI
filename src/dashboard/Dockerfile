# Multi-stage build for minimal image size
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY src/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder stage (system-wide)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/dashboard/ .

# Copy common models from parent directory
COPY src/common /app/common

# Copy scraper module (needed for news_scraper)
COPY src/scraper /app/scraper

# Create directories for data persistence
RUN mkdir -p /app/data/media

# Create non-root user for security
RUN useradd -m -u 1000 dashboard && \
    chown -R dashboard:dashboard /app

USER dashboard

# Expose Streamlit default port
EXPOSE 8501

# Health check: Verify Streamlit is serving
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Streamlit configuration for production
# --server.address=0.0.0.0: Listen on all interfaces
# --server.port=8501: Default Streamlit port
# --server.headless=true: Run without browser auto-open
# --server.fileWatcherType=none: Disable file watching for better performance
# --browser.gatherUsageStats=false: Disable telemetry
CMD ["streamlit", "run", "app.py", \
    "--server.address=0.0.0.0", \
    "--server.port=8501", \
    "--server.headless=true", \
    "--server.fileWatcherType=none", \
    "--browser.gatherUsageStats=false"]
