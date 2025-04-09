# Imagem base enxuta
FROM python:3.10-slim

# Evita prompt do apt
ENV DEBIAN_FRONTEND=noninteractive

# Diretório de trabalho
WORKDIR /app

# Copia apenas os requirements antes para cache
COPY requirements.txt .

# Instala dependências do sistema e Python
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
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copia os arquivos realmente usados
COPY backend/main.py backend/dashboard.py backend/atualizar_service.py ./backend/
COPY backend/services ./backend/services
COPY backend/data ./backend/data
COPY backend/models ./backend/models

# Expõe a porta (usada no Railway)
EXPOSE 8000

# Comando para subir a API FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]