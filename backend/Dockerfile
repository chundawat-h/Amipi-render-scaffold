FROM ubuntu:22.04

# Avoid interactive prompts during apt installations (e.g. tzdata)
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies: Python, Pip, Blender (for 3D renders), and GL libraries (for rembg)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    blender \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
# Note: For Render's 512MB Free Tier, you may experience Out-Of-Memory (OOM) crashes
# with rembg[gpu]. If this happens, change rembg[gpu] to just rembg in requirements.txt.
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Ensure storage directories exist for ephemeral storage
RUN mkdir -p /app/storage/outputs /app/storage/uploads
RUN chmod -R 777 /app/storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
