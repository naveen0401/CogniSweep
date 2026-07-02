FROM python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock.txt ./
RUN python -m pip install --upgrade pip==26.1.2 \
    && python -m pip install -r requirements.lock.txt

COPY . .

RUN python deploy/brand_streamlit_shell.py

RUN useradd --create-home --shell /usr/sbin/nologin errorsweep \
    && mkdir -p /data/errorsweep /logs/errorsweep \
    && chown -R errorsweep:errorsweep /app /data/errorsweep /logs/errorsweep

USER errorsweep

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5).read()"

CMD ["python", "-m", "streamlit", "run", "app.py"]
