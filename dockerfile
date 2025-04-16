FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

COPY requirements.txt .

# Instala dependências do sistema
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
    gnupg \
    curl \
    unzip \
 && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google.gpg \
 && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update && apt-get install -y google-chrome-stable

# Instala o ChromeDriver exatamente compatível com a versão 135 do Chrome
RUN wget -O /tmp/chromedriver.zip https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/135.0.7049.84/linux64/chromedriver-linux64.zip \
 && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
 && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
 && chmod +x /usr/local/bin/chromedriver \
 && rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

# Baixa o modelo de OCR em português
RUN wget https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata \
    -O /usr/share/tesseract-ocr/5/tessdata/por.traineddata

# Instala pacotes Python
RUN pip install --no-cache-dir -r requirements.txt \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia os arquivos e pastas do backend
COPY backend/atualizar_service.py ./backend/atualizar_service.py
COPY backend/dashboard.py ./backend/dashboard.py
COPY backend/main.py ./backend/main.py
COPY backend/utils.py ./backend/utils.py
COPY backend/data ./backend/data
COPY backend/models ./backend/models
COPY backend/services ./backend/services

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]