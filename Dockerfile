# Emare Asistan - FastAPI Backend
FROM python:3.12-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama
COPY . .

# Port
EXPOSE 8000

# Uvicorn ile başlat
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
