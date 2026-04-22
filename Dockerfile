FROM python:3.11-bullseye

# Pehle mirrors ko reset karne ki koshish karte hain aur fir install
RUN apt-get update --fix-missing && apt-get install -y \
    wkhtmltopdf \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn main:app --bind 0.0.0.0:$PORT