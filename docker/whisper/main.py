from fastapi import FastAPI, UploadFile, File
import whisper
import tempfile

app = FastAPI()

# Load Whisper model once at startup
model = whisper.load_model("base")  # change to "small", "medium", or "large"

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # Save uploaded file temporarily
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    audio_bytes = await file.read()
    tmp.write(audio_bytes)
    tmp.close()

    # Run Whisper
    result = model.transcribe(tmp.name)

    return {"text": result["text"]}
