"""
SpeakNote - main.py
FastAPI: Whisper transcription + Groq AI summary + static frontend
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
from groq import Groq
from pydantic import BaseModel

# Load Whisper model & Groq client at startup
print("Loading Whisper model...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Whisper model ready")

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

app = FastAPI(title="SpeakNote API")

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".webm"}
MAX_FILE_SIZE = 50 * 1024 * 1024


class SummarizeRequest(BaseModel):
    text: str


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    suffix = Path(file.filename or "audio.mp3").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported format: " + suffix)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        def do_transcribe(vad):
            kwargs = dict(beam_size=5)
            if vad:
                kwargs["vad_filter"] = True
                kwargs["vad_parameters"] = {"min_silence_duration_ms": 500}
            segs, inf = model.transcribe(tmp_path, **kwargs)
            texts = [s.text.strip() for s in segs if s.text.strip()]
            return texts, inf

        try:
            texts, info = do_transcribe(vad=True)
        except Exception:
            texts, info = do_transcribe(vad=False)

        if not texts:
            raise HTTPException(status_code=422, detail="No speech detected.")

        return {
            "text": "\n".join(texts),
            "language": info.language,
            "duration": round(info.duration, 1),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Transcription failed: " + str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


SYSTEM_PROMPT = (
    "You are a professional content analyst. "
    "Given a speech transcription, produce EXACTLY these three sections in Traditional Chinese:\n\n"
    "=== SECTION 1 ===\n"
    "Start with the emoji and header: 📌 重點摘要\n"
    "Write one flowing paragraph (no bullet points) summarizing the core content.\n\n"
    "=== SECTION 2 ===\n"
    "Start with: 💡 主要關鍵點\n"
    "List 3-5 key points using bullet symbol •\n\n"
    "=== SECTION 3 ===\n"
    "Start with: ❓ 延伸思考\n"
    "List 2-3 thought-provoking questions using bullet symbol •\n\n"
    "Output ONLY these three sections. No extra commentary."
)


@app.post("/api/summarize")
async def summarize(req: SummarizeRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured.")

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Transcription:\n\n" + req.text},
            ],
            temperature=0.6,
            max_tokens=1024,
        )
        return {"summary": completion.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Summary failed: " + str(e))


app.mount("/", StaticFiles(directory=".", html=True), name="static")
