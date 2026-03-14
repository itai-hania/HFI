FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app

COPY src/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Chromium browser for Playwright-based scraping (Inspiration search)
RUN playwright install chromium --with-deps

COPY src/ /app/src/
COPY config/ /app/config/

# Create directories for data persistence
RUN mkdir -p /app/data/session /app/data/media

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
