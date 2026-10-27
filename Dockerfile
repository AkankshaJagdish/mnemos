# Mnemos API container. The Streamlit UI can run as a separate process/service.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/mnemos.db

WORKDIR /app

# Build tools are not needed for the current pure-Python dependency set.
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend ./backend

# Persistent database mount point.
RUN mkdir -p /data && useradd --create-home --uid 10001 mnemos \
    && chown -R mnemos:mnemos /app /data
USER mnemos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
