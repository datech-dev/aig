import os
import re
import base64
import logging
import aiohttp
from typing import Optional, Tuple, Dict, Any

import config
import database

logger = logging.getLogger(__name__)

# Regular expressions to strip system tags and action asterisks for voice output
RE_TAGS = re.compile(r'\[(SEND_GIF|GENERATE_IMAGE|EMOTION|IMAGE):[^\]]*\]', re.IGNORECASE)
RE_ACTIONS = re.compile(r'\*[^*]+\*')  # Strips stage directions like *giggles softly*
RE_EMOJIS = re.compile(
    r'[\U00010000-\U0010ffff]|[\u200d\u200c]|[\u2600-\u27BF]|[\uD83C-\uDBFF\uDC00-\uDFFF]',
    flags=re.UNICODE
)


def clean_text_for_speech(text: str) -> str:
    """
    Cleans text response before passing to Sarvam Bulbul v4 TTS:
    - Removes internal system tags like [SEND_GIF: ...], [GENERATE_IMAGE: ...].
    - Removes asterisks roleplay actions (e.g. *giggles*, *smiles warmly*).
    - Cleans redundant spaces and punctuation so speech sounds natural and loving.
    """
    if not text:
        return ""
        
    cleaned = RE_TAGS.sub("", text)
    cleaned = RE_ACTIONS.sub("", cleaned)
    # Remove emojis so TTS does not attempt to speak "red heart smiling face"
    cleaned = RE_EMOJIS.sub("", cleaned)
    
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


async def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    mime_type: str = "audio/wav",
    model: Optional[str] = None
) -> str:
    """
    Transcribes spoken audio using Sarvam Saaras v4 STT model.
    """
    api_key = config.SARVAM_API_KEY
    if not api_key:
        raise ValueError("SARVAM_API_KEY is not configured in environment.")

    stt_model = model or config.SARVAM_STT_MODEL or "saaras:v4"
    url = f"{config.SARVAM_API_BASE_URL.rstrip('/')}/speech-to-text"
    headers = {
        "api-subscription-key": api_key
    }

    form_data = aiohttp.FormData()
    form_data.add_field(
        "file",
        audio_bytes,
        filename=filename,
        content_type=mime_type
    )
    form_data.add_field("model", stt_model)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=form_data, timeout=aiohttp.ClientTimeout(total=25)) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error(f"Sarvam STT failed with status {resp.status}: {err_text}")
                raise RuntimeError(f"Sarvam STT error ({resp.status}): {err_text}")
            
            result = await resp.json()
            transcript = result.get("transcript", "").strip()
            logger.info(f"[Sarvam STT] Transcribed ({stt_model}): '{transcript}'")
            return transcript


async def text_to_speech(
    text: str,
    target_language_code: str = "en-IN",
    speaker: Optional[str] = None,
    model: Optional[str] = None
) -> Tuple[str, str]:
    """
    Synthesizes speech using Sarvam Bulbul v4 TTS model.
    Returns: (audio_base64_string, mime_type)
    """
    api_key = config.SARVAM_API_KEY
    if not api_key:
        raise ValueError("SARVAM_API_KEY is not configured in environment.")

    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        spoken_text = "I'm right here with you, love."

    tts_model = model or config.SARVAM_TTS_MODEL or "bulbul:v4-flash"
    tts_speaker = speaker or config.SARVAM_TTS_SPEAKER or "ishita_enhi_companion"
    url = f"{config.SARVAM_API_BASE_URL.rstrip('/')}/text-to-speech"
    
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": [spoken_text],
        "target_language_code": target_language_code,
        "speaker": tts_speaker,
        "model": tts_model,
        "enable_preprocessing": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=25)) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error(f"Sarvam TTS failed with status {resp.status}: {err_text}")
                raise RuntimeError(f"Sarvam TTS error ({resp.status}): {err_text}")
            
            result = await resp.json()
            audios = result.get("audios", [])
            if not audios:
                raise RuntimeError("Sarvam TTS returned empty audio array.")
                
            audio_base64 = audios[0]
            logger.info(f"[Sarvam TTS] Generated speech ({tts_model} / {tts_speaker}) for {len(spoken_text)} chars")
            return audio_base64, "audio/wav"


async def process_voice_call_turn(
    user_id: int,
    audio_bytes: bytes,
    platform: str = "android_app"
) -> Dict[str, Any]:
    """
    End-to-End Voice Call Turn:
    1. Audio -> Sarvam Saaras v4 (STT) -> User Transcript
    2. User Transcript -> Juhi AI Companion Engine -> AI Text Response
    3. AI Text Response -> Sarvam Bulbul v4 (TTS) -> Juhi Voice Audio
    """
    import ai_engine

    # Step 1: Speech-to-Text
    transcript = await speech_to_text(audio_bytes)
    
    if not transcript:
        # Handle silence / inaudible speech gracefully
        default_reply = "I didn't quite catch that, sweetie. Could you say that again?"
        audio_b64, audio_fmt = await text_to_speech(default_reply)
        return {
            "success": True,
            "user_transcript": "",
            "ai_reply": default_reply,
            "audio_base64": audio_b64,
            "audio_format": audio_fmt,
            "emotion": "attentive",
            "relationship_level": database.get_user_relationship_level(user_id) if hasattr(database, "get_user_relationship_level") else 1
        }

    # Step 2: AI Engine generates context-aware, emotional companion response
    ai_raw_reply = await ai_engine.generate_response(user_id, transcript)
    
    # Step 3: Text-to-Speech via Bulbul v4
    audio_b64, audio_fmt = await text_to_speech(ai_raw_reply)

    # Step 4: Record analytics telemetry event
    try:
        database.log_user_analytics_event(
            user_id=user_id,
            event_name="voice_call_turn",
            event_category="voice_call",
            platform=platform,
            metadata={
                "transcript_length": len(transcript),
                "reply_length": len(ai_raw_reply),
                "stt_model": config.SARVAM_STT_MODEL,
                "tts_model": config.SARVAM_TTS_MODEL,
                "speaker": config.SARVAM_TTS_SPEAKER
            }
        )
    except Exception as e_track:
        logger.warning(f"Failed to track voice call telemetry: {e_track}")

    # Fetch user relationship level & state
    lvl = 1
    try:
        settings = database.get_user_settings(user_id)
        if settings and settings.get("relationship_stage"):
            lvl = int(settings["relationship_stage"])
    except Exception:
        pass

    return {
        "success": True,
        "user_transcript": transcript,
        "ai_reply": ai_raw_reply,
        "audio_base64": audio_b64,
        "audio_format": audio_fmt,
        "relationship_level": lvl
    }
