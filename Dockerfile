FROM python:3.10-slim

# Instalar ffmpeg y libasound2 requeridos por pydub y Azure Speech
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]