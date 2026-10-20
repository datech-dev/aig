"""Validation and compatibility bridge for structured LLM responses."""

from dataclasses import dataclass
import json
import re
from typing import Any, Dict, Optional, Sequence

import safety_engine


@dataclass
class ValidatedLLMResponse:
    message: str
    language: str = "auto"
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    media_type: str = "none"
    media_id: Optional[str] = None
    image_prompt: Optional[str] = None


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

    # Robust fallback for slightly truncated JSON: extract "message" directly
    msg_match = re.search(r'"message"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if msg_match:
        try:
            cleaned_msg = json.loads(f'"{msg_match.group(1)}"')
            return {"message": cleaned_msg, "media": {"type": "none"}}
        except Exception:
            return {"message": msg_match.group(1), "media": {"type": "none"}}

    return None


def clamp_to_word_limit(message: str, max_words: int = 15) -> str:
    """Clamps message to max_words cleanly at sentence or clause boundaries."""
    words = message.split()
    if len(words) <= max_words:
        return message

    sentences = re.split(r'(?<=[.!?])\s+', message)
    accum = []
    for s in sentences:
        cand = ' '.join(accum + [s]) if accum else s
        if len(cand.split()) <= max_words:
            accum.append(s)
        else:
            break
    if accum:
        return ' '.join(accum)

    clauses = re.split(r'(?<=[,;:\-])\s+', message)
    accum = []
    for c in clauses:
        cand = ' '.join(accum + [c]) if accum else c
        if len(cand.split()) <= max_words:
            accum.append(c)
        else:
            break
    if accum:
        return ' '.join(accum).rstrip(',;:- ')

    return ' '.join(words[:max_words]).rstrip(',;:- ')


def validate_llm_response(
    raw: str,
    *,
    allowed_gifs: Sequence[str] = (),
    image_allowed: bool = False,
    character_appearance: str = "Juhi, a young Indian software developer living in Bangalore",
    allow_long: bool = False,
    max_words: int = 15,
) -> ValidatedLLMResponse:
    """Validate model output and never execute unvalidated media actions."""
    data = _extract_json(raw)

    # If structured output fails, return safe text only. No media action is allowed.
    if not data:
        fallback = re.sub(r"\[(?:GENERATE_IMAGE|SEND_GIF):[^\]]*\]", "", raw or "").strip()
        safe_fb = safety_engine.scan_output_safety(fallback)
        if not allow_long and safe_fb:
            safe_fb = clamp_to_word_limit(safe_fb, max_words=max_words)
        return ValidatedLLMResponse(message=safe_fb)

    message = data.get("message")
    if not isinstance(message, str):
        message = ""
    message = safety_engine.scan_output_safety(message.strip())
    if not allow_long and message:
        message = clamp_to_word_limit(message, max_words=max_words)

    language = data.get("language", "auto")
    if not isinstance(language, str) or len(language) > 20:
        language = "auto"

    emotion_data = data.get("emotion") if isinstance(data.get("emotion"), dict) else {}
    emotion = emotion_data.get("name", "neutral")
    if not isinstance(emotion, str):
        emotion = "neutral"
    try:
        intensity = float(emotion_data.get("intensity", 0.0))
    except (TypeError, ValueError):
        intensity = 0.0
    intensity = max(0.0, min(1.0, intensity))

    media = data.get("media") if isinstance(data.get("media"), dict) else {}
    media_type = media.get("type", "none")
    if media_type not in {"none", "gif", "image"}:
        media_type = "none"

    media_id = media.get("id") if isinstance(media.get("id"), str) else None
    image_prompt = media.get("prompt") if isinstance(media.get("prompt"), str) else None

    # GIFs are only executable when the id was supplied by the application.
    if media_type == "gif":
        allowed = {str(item).lower() for item in allowed_gifs}
        if not media_id or media_id.lower() not in allowed:
            media_type, media_id = "none", None

    # Images are only executable when the application explicitly authorized them.
    if media_type == "image":
        if not image_allowed or not image_prompt:
            media_type, image_prompt = "none", None
        else:
            image_prompt = safety_engine.build_safe_image_prompt(image_prompt, character_appearance)

    return ValidatedLLMResponse(
        message=message,
        language=language,
        emotion=emotion,
        emotion_intensity=intensity,
        media_type=media_type,
        media_id=media_id,
        image_prompt=image_prompt,
    )


def to_legacy_compatible_text(result: ValidatedLLMResponse) -> str:
    """Keep the existing Telegram/media pipeline compatible while making the
    model incapable of directly emitting executable tags.
    """
    parts = [result.message.strip()]
    if result.media_type == "gif" and result.media_id:
        parts.append(f"[SEND_GIF: {result.media_id}]")
    elif result.media_type == "image" and result.image_prompt:
        parts.append(f"[GENERATE_IMAGE: {result.image_prompt}]")
    return "\n".join(part for part in parts if part)
