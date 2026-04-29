"""
SpeakNote — main.py
FastAPI 後端：提供 Whisper 語音轉文字 API + 靜態前端服務
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel

# =====================================================
# 啟動時載入模型（base 模型，已在 Docker build 時下載）
# =====================================================
print("載入 Whisper 模型中...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Whisper 模型載入完成")

# =====================================================
# FastAPI App
# =====================================================
app = FastAPI(title="SpeakNote API")

# 支援的音訊格式（副檔名）
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".webm"}

# 檔案大小上限：50 MB
MAX_FILE_SIZE = 50 * 1024 * 1024


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    接收音訊檔案，回傳轉錄文字。
    支援：mp3 / wav / m4a / ogg / flac / mp4 / webm
    """
    # 副檔名檢查
    suffix = Path(file.filename or "audio.mp3").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的格式：{suffix}。請上傳 mp3、wav、m4a、ogg 等音訊檔。",
        )

    # 讀取並檢查檔案大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="檔案過大，請上傳 50 MB 以內的音訊檔。")

    # 寫入暫存檔
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 轉錄（自動偵測語言）
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            vad_filter=True,          # 過濾靜音
            vad_parameters={"min_silence_duration_ms": 500},
        )

        # 收集所有片段
        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        full_text = "\n".join(texts)

        return {
            "text": full_text,
            "language": info.language,
            "duration": round(info.duration, 1),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轉錄失敗：{str(e)}")

    finally:
        # 清除暫存檔
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# =====================================================
# 靜態前端（API 路由之後掛載，優先順序較低）
# =====================================================
app.mount("/", StaticFiles(directory=".", html=True), name="static")
