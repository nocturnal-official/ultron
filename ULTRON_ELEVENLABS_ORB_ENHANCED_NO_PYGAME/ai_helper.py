"""Provider-agnostic AI calls for the action modules.

The original JARVIS tools called Google Gemini directly. Ultron runs on Claude,
ChatGPT or a local model, so these helpers route a plain text prompt or an
image+question to whichever provider is configured in .env — one key, one brain.
"""
import base64

from config import CFG


def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=CFG.anthropic_api_key)


def _openai_client():
    import openai
    return openai.OpenAI(api_key=CFG.openai_api_key)


def complete_text(prompt: str, system: str = "", max_tokens: int = 1500) -> str:
    """Single-shot text generation on the configured provider. Raises on failure."""
    provider = CFG.provider
    if provider == "anthropic":
        client = _anthropic_client()
        kw = {"model": CFG.anthropic_model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
        if system:
            kw["system"] = system
        resp = client.messages.create(**kw)
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    if provider == "openai":
        client = _openai_client()
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        resp = client.chat.completions.create(model=CFG.openai_model, messages=msgs)
        return (resp.choices[0].message.content or "").strip()
    if provider == "ollama":
        import requests
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        r = requests.post(f"{CFG.ollama_url}/api/chat",
                          json={"model": CFG.ollama_model, "messages": msgs, "stream": False},
                          timeout=180)
        r.raise_for_status()
        return (r.json().get("message", {}).get("content") or "").strip()
    raise RuntimeError("No AI provider configured.")


def analyze_image(image_bytes: bytes, question: str, mime_type: str = "image/png") -> str:
    """Ask the configured vision-capable provider about an image."""
    provider = CFG.provider
    b64 = base64.b64encode(image_bytes).decode("ascii")
    if provider == "anthropic":
        client = _anthropic_client()
        resp = client.messages.create(
            model=CFG.anthropic_model, max_tokens=1500,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": b64}},
                {"type": "text", "text": question}]}])
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    if provider == "openai":
        client = _openai_client()
        resp = client.chat.completions.create(
            model=CFG.openai_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}]}])
        return (resp.choices[0].message.content or "").strip()
    if provider == "ollama":
        import requests
        r = requests.post(f"{CFG.ollama_url}/api/chat",
                          json={"model": CFG.ollama_vision_model or CFG.ollama_model,
                                "messages": [{"role": "user", "content": question, "images": [b64]}],
                                "stream": False}, timeout=180)
        r.raise_for_status()
        return (r.json().get("message", {}).get("content") or "").strip()
    raise RuntimeError("No AI provider configured for vision.")


def provider_available() -> bool:
    return bool(CFG.provider)
