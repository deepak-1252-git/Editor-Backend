FROM python:3.11-slim

# System dependencies install karo
# wkhtmltopdf -> HTML to PDF ke liye
# poppler-utils -> PDF to Image ke liye
RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    poppler-utils \
    libnss3 \
    libasound2 \
    libatk1.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# App directory set karo
WORKDIR /app

# Sabse pehle requirements copy aur install karo (Taaki build fast ho)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn main:app --bind 0.0.0.0:$PORT