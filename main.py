"""
SpeakNote — main.py
FastAPI 後端：提供 Whisper 語音轉文字 API + Groq AI 摘要 + 靜態前端服務
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
from groq import Groq
from pydantic import BaseModel

# =====================================================
# 啟動時載入模型與 Groq 客戶端
# =====================================================
print("載入 Whisper 模型中...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Whisper 模型載入完成")

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# =====================================================
# FastAPI App
# =====================================================
app = FastAPI(title="SpeakNote API")

# Pydantic model for summarize request
class SummarizeRequest(BaseModel):
    text: str

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
# Groq AI 摘要端點
# =====================================================
SUMMARIZE_SYSTEM_PROMPT = """你是一位專業的內容分析師，擅長整理語音轉錄內容。
請根據使用者提供的語音轉錄文字，用繁體中文產出以下三個區塊：

📌 重點摘要
（用一段流暢的文字描述內容的核心重點，不要用條列式，像在寫文章摘要那樣）

💡 主要關鍵點
• （條列出 3～5 個最重要的關鍵點）

❓ 延伸思考
• （列出 2～3 個可以從這段內容延伸出的問題或思考方向）

請嚴格按照以上格式輸出，不要加入其他額外說明或前言。"""


@app.post("/api/summarize")
async def summarize(req: SummarizeRequest):
    """
    接收轉錄文字，呼叫 Groq llama-3.3-70b-versatile，回傳三段式摘要。
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="文字內容不能為空。")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="伺服器未設定 GROQ_API_KEY。")

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是語音轉錄內容：\n\n{req.text}"},
            ],
            temperature=0.6,
            max_tokens=1024,
        )
        summary = completion.choices[0].message.content
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要失敗：{str(e)}")


# =====================================================
# 靜態前端（API 路由之後掛載，優先順序較低）
# =====================================================
app.mount("/", StaticFiles(directory=".", html=True), name="static")
