FROM python:3.11-slim

# Yeh line Poppler install karti hai (Sabse Important)
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render ke liye dynamic port binding
CMD gunicorn main:app --bind 0.0.0.0:$PORT