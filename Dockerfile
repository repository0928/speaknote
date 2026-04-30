# =====================================================
# SpeakNote Dockerfile
# Python 3.11 + ffmpeg + faster-whisper (tiny model)
# =====================================================

FROM python:3.11-slim

# 安裝 ffmpeg（faster-whisper 解碼音訊需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先裝 Python 依賴（利用 Docker layer cache）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 預先下載 Whisper tiny 模型（build 時下載，避免啟動後等待）
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8'); print('Model downloaded.')"

# 複製所有專案檔案
COPY . .

# Zeabur 會透過環境變數 PORT 指定 port（預設 8080）
ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
