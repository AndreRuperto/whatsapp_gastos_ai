FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libzbar0 \
    default-jre \
    wget \
 && wget https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata \
    -O /usr/share/tesseract-ocr/5/tessdata/por.traineddata \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia arquivos individuais
COPY backend/atualizar_service.py ./backend/atualizar_service.py
COPY backend/dashboard.py ./backend/dashboard.py
COPY backend/main.py ./backend/main.py
COPY backend/utils.py ./backend/utils.py

# Copia apenas as pastas necessárias
COPY backend/data ./backend/data
COPY backend/models ./backend/models
COPY backend/services ./backend/services

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]