import os
import tempfile
import torch
import numpy as np
import soundfile as sf
import json
import traceback
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from huggingface_hub import login
from dotenv import load_dotenv
from dia.model import Dia

# Load env + login HF
load_dotenv()
hf_token = os.getenv("HF_TOKEN")
if not hf_token:
    raise RuntimeError("HF_TOKEN not found in environment variables")
login(token=hf_token)

# Device selection
if torch.cuda.is_available():
    device = torch.device("cuda")
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
print(f"Using device: {device}")

# Load Dia model
try:
    model = Dia.from_pretrained(
        "nari-labs/Dia-1.6B-0626",
        device=device
    )
except Exception as e:
    print("Failed to load model:", e)
    raise

app = FastAPI()


@app.post("/")
async def generate_audio(
    user_prompt: str = Form(...),
    properties: str = Form(...),
    audio_prompt: UploadFile | None = None,  # optional style reference
):
    # Parse generation props
    try:
        props = json.loads(properties)
    except json.JSONDecodeError as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

    max_new_tokens = props.get("max_new_tokens", 3097)
    cfg_scale = props.get("cfg_scale", 3.0)
    temperature = props.get("temperature", 1.8)
    top_p = props.get("top_p", 0.95)
    cfg_filter_top_k = props.get("cfg_filter_top_k", 45)
    speed_factor = props.get("speed_factor", 1.0)
    seed = props.get("seed", -1)

    if not user_prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Save audio prompt if provided
    prompt_path_for_generate = None
    if audio_prompt is not None:
        tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_bytes = await audio_prompt.read()
        tmp_audio.write(audio_bytes)
        tmp_audio.close()
        prompt_path_for_generate = tmp_audio.name

    # Seed setup
    if seed is None or seed < 0:
        seed = np.random.randint(0, 2**32 - 1)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Run generation
    with torch.inference_mode():
        output_audio_np = model.generate(
            user_prompt,
            max_tokens=max_new_tokens,
            cfg_scale=cfg_scale,
            temperature=temperature,
            top_p=top_p,
            cfg_filter_top_k=cfg_filter_top_k,
            use_torch_compile=False,
            verbose=True,
            audio_prompt=prompt_path_for_generate  # optional
        )

    if output_audio_np is None:
        raise HTTPException(status_code=500, detail="Model returned no audio")

    # Adjust speed if needed
    sr = 44100
    if speed_factor != 1.0:
        original_len = len(output_audio_np)
        target_len = int(original_len / speed_factor)
        x_original = np.arange(original_len)
        x_resampled = np.linspace(0, original_len - 1, target_len)
        output_audio_np = np.interp(x_resampled, x_original, output_audio_np)

    # Save to WAV
    tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    sf.write(tmp_path, output_audio_np.astype(np.float32), sr)

    # Return file
    return FileResponse(
        tmp_path,
        media_type="audio/wav",
        filename="output.wav"
    )


@app.get("/up")
def is_up():
    """Health check endpoint."""
    return True
