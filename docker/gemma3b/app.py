from fastapi import FastAPI, Body
import os
from starlette.middleware.cors import CORSMiddleware  # ✅ Import this
from .slm import SLM, SLMConfig

app = FastAPI(title="Gemma SLM")

# ✅ Allow frontend (HTML/JS) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict to ["http://127.0.0.1:8000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Initialize Gemma
slm = SLM(
    SLMConfig(
        token=os.getenv("HF_TOKEN", ""),
        model_id=os.getenv("GEMMA_MODEL", "google/gemma-2-2b-it"),
        max_new_tokens=256,
    )
)

# ✅ Helper to build conversation format
def _chat(system_text: str, user_text: str):
    return [[
        {"role": "system", "content": [{"type": "text", "text": system_text}]},
        {"role": "user", "content": [{"type": "text", "text": user_text}]},
    ]]

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/generate")
def generate(payload=Body(...)):
    system = payload.get("system", "")
    user   = payload.get("user", "")
    return {"text": slm.input(_chat(system, user))}
