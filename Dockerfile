FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:0

# System packages for GUI and processing
RUN apt-get update && apt-get install -y \
    python3-tk \
    x11-apps \
    libgl1-mesa-glx \
    libxrender1 \
    libsm6 \
    libxext6 \
    libx11-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the full app code
COPY . /app
WORKDIR /app

# Ensure Earth Engine config directory exists
RUN mkdir -p /root/.config/earthengine

CMD ["python", "main_app.py"]