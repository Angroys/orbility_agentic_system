from docker.gemma3b.slm import SLMConfig


config = SLMConfig(
    token="",
    model_id="google/gemma-3-1B-it",
    return_tensors="pt",
    max_new_tokens=500,
    temperature=0.8,
    skip_special_tokens=True,
)