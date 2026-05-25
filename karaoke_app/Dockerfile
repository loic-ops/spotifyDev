# syntax=docker/dockerfile:1.4
FROM python:3.10-slim

WORKDIR /app

# Ensure Python prints show immediately in Docker logs
ENV PYTHONUNBUFFERED=1

# BLAS thread count — set ≥2 to avoid the historical OpenBLAS+OpenMP hang,
# but high enough to actually use the CPU (Demucs/Whisper are CPU-bound).
ENV OPENBLAS_NUM_THREADS=8
ENV MKL_NUM_THREADS=8
ENV OMP_NUM_THREADS=8

# Runtime system deps only — ffmpeg binary for audio, libsndfile for soundfile.
# PyAV ships pre-built wheels so we no longer need the libav*-dev headers
# or gcc/pkg-config.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements alone — only invalidates the pip layer when it changes.
COPY requirements.txt .

# Install Python deps in ONE layer with BuildKit pip cache mount.
# Torch from the CPU-only index saves ~1.5GB vs the default CUDA wheels.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.0.0,<2.2" "torchaudio>=2.0.0,<2.2" \
 && pip install -r requirements.txt \
 && pip install yt-dlp

# Copy application code (this is the layer that changes most often)
COPY . .

# Create runtime directories
RUN mkdir -p static/uploads static/processed data

EXPOSE 5000

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
