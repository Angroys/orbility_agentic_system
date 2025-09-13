from fastapi import FastAPI, Body
import os
from .slm import SLM, SLMConfig

app = FastAPI(title="Gemma SLM")

slm = SLM(SLMConfig(
    token=os.getenv("HF_TOKEN", ""),
    model_id=os.getenv("GEMMA_MODEL", "google/gemma-2-2b-it"),
    max_new_tokens=256,
))

def _chat(system_text: str, user_text: str):
    return [[
        {"role":"system","content":[{"type":"text","text":system_text}]},
        {"role":"user","content":[{"type":"text","text":user_text}]},
    ]]

@app.get("/health")
def health(): return {"ok": True}

@app.post("/generate")
def generate(payload=Body(...)):
    system = payload.get("system","")
    user   = payload.get("user","")
    return {"text": slm.input(_chat(system, user))}
