FROM python:3.10-slim

WORKDIR /app

# Ensure Python prints show immediately in Docker logs
ENV PYTHONUNBUFFERED=1

# BLAS thread count — set ≥2 to avoid the historical OpenBLAS+OpenMP hang,
# but high enough to actually use the CPU (Demucs/Whisper are CPU-bound).
ENV OPENBLAS_NUM_THREADS=8
ENV MKL_NUM_THREADS=8
ENV OMP_NUM_THREADS=8

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    gosu \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early — this layer never changes, so it stays cached.
RUN groupadd -r karaoke && useradd -r -g karaoke -d /app -s /sbin/nologin karaoke

# Install build tools (setuptools needed by openai-whisper build)
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel

# Copy requirements file alone — only invalidates the pip layer when
# requirements actually change.
COPY requirements.txt .

# All Python deps in ONE layer:
# - openai-whisper first with --no-build-isolation (needs setuptools at build time)
# - PyAV separately (needs ffmpeg dev headers, installed above)
# - then the rest of requirements.txt
# - then yt-dlp
RUN pip install --no-cache-dir --no-build-isolation openai-whisper==20231117 \
 && pip install --no-cache-dir "av>=12.0.0" \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir yt-dlp

# Copy application code (this is the layer that changes most often)
COPY . .

# Create necessary directories with proper ownership
RUN mkdir -p static/uploads static/processed data \
    && chown -R karaoke:karaoke /app \
    && chmod +x entrypoint.sh

# NOTE: stay as root here. The entrypoint chowns volume mounts
# (which are owned by root by default) and then drops privileges to
# 'karaoke' via gosu before exec'ing gunicorn.

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]

# Production: Gunicorn with 1 worker — Demucs/Whisper are CPU-bound and each
# worker would load its own copy of the models. 1 worker gives the best
# per-job latency; jobs are processed sequentially.
# Timeout 300s for long-running yt-dlp downloads and audio processing.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
