FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY . .
RUN useradd -r -u 10001 hsl && mkdir -p /app/runs && chown -R hsl /app/runs
USER hsl
ENV HSL_HOST=0.0.0.0 HSL_PORT=8050 HSL_RUNS_DIR=/app/runs HSL_AUTH_MODE=open HSL_LLM=off OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8050/healthz')" || exit 1
CMD gunicorn -w 1 --threads 8 --timeout 300 -b 0.0.0.0:${HSL_PORT:-8050} dash_app:server
