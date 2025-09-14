import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

app = FastAPI(title="Orbility UI + Uploader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

N8N_WEBHOOK = os.getenv(
    "N8N_WEBHOOK",
    "http://localhost:5678/webhook-test/speech-input",
)

from pydub import AudioSegment
import io

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        # Read WebM from browser
        raw = await file.read()

        # Convert WebM -> WAV
        audio = AudioSegment.from_file(io.BytesIO(raw), format="webm")
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        # Forward WAV to n8n
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                N8N_WEBHOOK,
                files={"file": ("recording.wav", wav_io, "audio/wav")},
            )
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forwarding failed: {e}")


# --- Serve static frontend ---
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
