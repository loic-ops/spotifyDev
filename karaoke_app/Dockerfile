# syntax=docker/dockerfile:1.4
FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OMP_NUM_THREADS=8

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .


RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.0.0,<2.2" "torchaudio>=2.0.0,<2.2" \
 && pip install -r requirements.txt \
 && pip install yt-dlp

COPY . .

RUN mkdir -p static/uploads static/processed data \
 && chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
