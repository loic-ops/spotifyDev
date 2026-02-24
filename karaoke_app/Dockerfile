FROM python:3.10-slim

WORKDIR /app

# Fix OpenBLAS + OpenMP conflict (prevents hang during Demucs separation)
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OMP_NUM_THREADS=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install build tools
RUN pip install --no-cache-dir --upgrade pip "setuptools<72" wheel

# Copy requirements
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p static/uploads static/processed

EXPOSE 5000

CMD ["python", "app.py"]
