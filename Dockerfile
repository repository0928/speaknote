# =====================================================
# SpeakNote Dockerfile
# Python 3.11 + ffmpeg + Groq API (no local model)
# =====================================================

FROM python:3.11-slim

# ffmpeg for audio compression before sending to Groq
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
