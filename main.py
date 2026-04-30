"""
SpeakNote - main.py
FastAPI: Groq Whisper API transcription + Groq AI summary + static frontend
"""

import os
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel

app = FastAPI(title="SpeakNote API")

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".webm"}
MAX_FILE_SIZE = 200 * 1024 * 1024   # 200 MB upload limit
GROQ_MAX_BYTES = 23 * 1024 * 1024   # 23 MB — Groq hard limit is 25 MB

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


class SummarizeRequest(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"status": "ok"}


def compress_audio(src_path: str, dst_path: str) -> None:
    """Convert audio to mono mp3 at 32kbps using ffmpeg.
    50 min * 60 s * 32 kbps / 8 = ~11.7 MB — well within Groq's 25 MB limit.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-ac", "1",          # mono
        "-ar", "16000",      # 16 kHz sample rate
        "-b:a", "32k",       # 32 kbps
        dst_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg compression failed: " + result.stderr.decode())


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    suffix = Path(file.filename or "audio.mp3").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported format: " + suffix)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 200 MB).")

    if not os.environ.get("GROQ_API_KEY"):
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured.")

    # Write original file to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        original_path = tmp.name

    audio_path = original_path

    try:
        # Compress if over Groq's size limit
        if len(content) > GROQ_MAX_BYTES:
            compressed_path = original_path + "_compressed.mp3"
            try:
                compress_audio(original_path, compressed_path)
                audio_path = compressed_path
            except Exception as e:
                raise HTTPException(status_code=500, detail="Audio compression failed: " + str(e))

        # Send to Groq Whisper API
        try:
            with open(audio_path, "rb") as f:
                filename = Path(audio_path).name
                transcription = groq_client.audio.transcriptions.create(
                    file=(filename, f.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                    prompt="以下是一段語音內容，請完整轉錄。",
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail="Transcription API error: " + str(e))

        text = transcription.text.strip() if hasattr(transcription, "text") else ""
        language = getattr(transcription, "language", "unknown")
        duration = getattr(transcription, "duration", 0)

        if not text:
            raise HTTPException(
                status_code=422,
                detail="No speech detected. Please check the audio has clear speech."
            )

        return {
            "text": text,
            "language": language,
            "duration": round(float(duration), 1) if duration else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Transcription failed: " + str(e))
    finally:
        for p in [original_path, original_path + "_compressed.mp3"]:
            try:
                if os.path.exists(p):
                    os.unlink(p)
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
