# scorm-mcp — ARM uyumlu (Coolify, 16GB/9-core). python:3.11-slim tabanı.
# lxml/nh3 manylinux/musllinux + arm64 wheel'leri kullanır → derleyici gerekmez.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    PORT=8000 \
    HOST=0.0.0.0 \
    MCP_TRANSPORT=http

WORKDIR /app

# ffmpeg — medya işleme (Faz 4: görsel+ses→video, transcode, poster). Erken katman = cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Faz 10 — HyperFrames için Node 22 + headless Chromium sistem kütüphaneleri (opt-in video render).
# Chromium'u HyperFrames/Playwright ilk render'da indirir; burada yalnız sistem bağımlılıkları + Node.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg \
      libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
      fonts-liberation fonts-dejavu-core \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g hyperframes \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Faz 11 — Piper Türkçe ses modeli (opt-in TTS). piper-tts pip ile gelir ('.[tts]'); sesi build'de
# indir → runtime'da indirme yok. arm64 uyumlu (onnxruntime arm64 wheel + saf-Python CLI).
RUN mkdir -p /app/voices \
    && curl -fsSL -o /app/voices/tr_TR-dfki-medium.onnx \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx \
    && curl -fsSL -o /app/voices/tr_TR-dfki-medium.onnx.json \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json
ENV PIPER_VOICE=/app/voices/tr_TR-dfki-medium.onnx

# Önce bağımlılık çözümü için pyproject; sonra kaynak (katman cache)
COPY pyproject.toml README.md ./
COPY core ./core
COPY components ./components
COPY auth ./auth
COPY themes ./themes
COPY compositions ./compositions
COPY runtime ./runtime
COPY server.py ./server.py
COPY examples ./examples
COPY tools ./tools

RUN pip install --upgrade pip && pip install ".[tts]"

# kalıcı volume + non-root kullanıcı
RUN mkdir -p /data && useradd -r -u 10001 -d /app appuser && chown -R appuser /app /data
USER appuser
VOLUME ["/data"]

EXPOSE 8000

# /health 200 kontrolü (curl yok → python urllib)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

# Streamable HTTP transport. (stdio yalnız lokal test: MCP_TRANSPORT=stdio)
CMD ["python", "server.py"]
