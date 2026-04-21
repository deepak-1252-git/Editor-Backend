# Python 3.11 use karte hain (Zyada stable aur fast hai)
FROM python:3.11-slim

# System dependencies install karo
# wkhtmltopdf -> HTML to PDF ke liye
# poppler-utils -> PDF to Image ke liye
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# App directory set karo
WORKDIR /app

# Sabse pehle requirements copy aur install karo (Taaki build fast ho)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pura code copy karo
COPY . .

# Render ke liye dynamic port binding (PORT Render apne aap set karta hai)
CMD gunicorn main:app --bind 0.0.0.0:$PORT