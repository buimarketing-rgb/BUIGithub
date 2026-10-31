FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache
WORKDIR /app

ARG INSTALL_ML=true
ARG INSTALL_WHISPER=false

COPY requirements*.txt ./
RUN pip install -r requirements.txt \
 && if [ "$INSTALL_ML" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements-ml.txt && \
      (python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || echo 'WARNING: could not pre-download the embedding model; it will be fetched at runtime'); \
    fi \
 && if [ "$INSTALL_WHISPER" = "true" ]; then apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/* && pip install -r requirements-voice.txt; fi

COPY . .
RUN useradd --create-home --uid 10001 bui && mkdir -p /data/uploads && chown -R bui:bui /data /app /opt/hf-cache 2>/dev/null || true
USER bui
ENV UPLOAD_DIR=/data/uploads
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
