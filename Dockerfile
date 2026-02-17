FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .  # ← КОПИРУЕМ ВСЁ ИЗ КОРНЯ РЕПОЗИТОРИЯ

CMD ["python", "bot.py"]
