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


def detect_audio_format(audio_bytes: bytes) -> Tuple[str, str]:
    """
    Inspect magic header bytes to determine file extension and Sarvam-compatible MIME type.
    """
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return "audio.wav", "audio/wav"
    if len(audio_bytes) >= 4 and (audio_bytes[:3] == b"ID3" or audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "audio.mp3", "audio/mpeg"
    if len(audio_bytes) >= 8 and audio_bytes[4:8] == b"ftyp":
        # Sarvam requires 'audio/mp4' or 'audio/x-m4a' for MP4/M4A containers
        return "audio.mp4", "audio/mp4"
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b"OggS":
        return "audio.ogg", "audio/ogg"
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b"fLaC":
        return "audio.flac", "audio/flac"
    # Default fallback
    return "audio.wav", "audio/wav"


async def speech_to_text(
    audio_bytes: bytes,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
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

    det_filename, det_mime = detect_audio_format(audio_bytes)
    final_filename = filename if (filename and "." in filename) else det_filename
    final_mime = mime_type if (mime_type and "/" in mime_type and mime_type != "application/octet-stream") else det_mime

    # Normalize audio/m4a to audio/mp4 for Sarvam API compatibility
    if final_mime == "audio/m4a":
        final_mime = "audio/mp4"

    logger.info(f"[Sarvam STT] Submitting {len(audio_bytes)} bytes as '{final_filename}' ({final_mime}) with model '{stt_model}'")

    form_data = aiohttp.FormData()
    form_data.add_field(
        "file",
        audio_bytes,
        filename=final_filename,
        content_type=final_mime
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
    tts_speaker = speaker or config.SARVAM_TTS_SPEAKER or "simran_en_conversation"
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
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
    platform: str = "android_app"
) -> Dict[str, Any]:
    """
    End-to-End Voice Call Turn:
    1. Audio -> Sarvam Saaras v4 (STT) -> User Transcript
    2. User Transcript -> Juhi AI Companion Engine -> AI Text Response
    3. AI Text Response -> Sarvam Bulbul v4 (TTS) -> Juhi Voice Audio
    """
    import ai_engine

    logger.info(f"[Voice Call Turn] Processing call turn for user {user_id} ({len(audio_bytes)} audio bytes)")

    # Check for empty/micro-duration audio (accidental tap)
    if len(audio_bytes) < 3000:
        logger.warning(f"[Voice Call Turn] Audio too short ({len(audio_bytes)} bytes). Treating as quick tap.")
        default_reply = "I'm listening, sweetie! Tap and speak for a moment so I can hear your lovely voice."
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

    # Step 1: Speech-to-Text with auto-format detection
    try:
        transcript = await speech_to_text(audio_bytes, filename=filename, mime_type=mime_type)
    except Exception as stt_err:
        logger.error(f"[Voice Turn] Sarvam STT error: {stt_err}", exc_info=True)
        transcript = ""
    
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
    try:
        ai_engine.extract_and_save_user_memories(user_id, transcript)
    except Exception as mem_err:
        logger.warning(f"[Voice Call] Memory extraction error: {mem_err}")

    settings = database.get_user_settings(user_id) if hasattr(database, "get_user_settings") else None
    persona_key = settings.get("active_persona", "juhi") if settings else "juhi"
    persona = config.PERSONAS.get(persona_key, config.PERSONAS["juhi"]) if hasattr(config, "PERSONAS") else {"name": "Juhi"}
    xp = settings.get("relationship_xp", 0) if settings else 0
    u_nick = settings.get("user_nickname", "sweetie") if (settings and settings.get("user_nickname")) else "sweetie"
    ai_nick = settings.get("ai_nickname", persona.get("name", "Juhi")) if (settings and settings.get("ai_nickname")) else persona.get("name", "Juhi")
    user_orientation = settings.get("user_orientation", "straight") if settings else "straight"

    chat_mode = database.get_chat_mode(user_id) if hasattr(database, "get_chat_mode") else "normal"
    memories = database.get_user_memories(user_id) if hasattr(database, "get_user_memories") else []
    history = database.get_chat_history(user_id, persona_key) if hasattr(database, "get_chat_history") else []

    # Persist user speech transcript in chat history
    try:
        if hasattr(database, "add_chat_message"):
            database.add_chat_message(user_id, persona_key, "user", transcript)
    except Exception as save_err:
        logger.warning(f"[Voice Call] Save user speech error: {save_err}")

    ai_raw_reply = await ai_engine.generate_response(
        persona_key=persona_key,
        relationship_xp=xp,
        user_nickname=u_nick,
        ai_nickname=ai_nick,
        chat_history=history,
        user_message=transcript,
        user_orientation=user_orientation,
        chat_mode=chat_mode,
        memories=memories,
        user_id=user_id
    )

    # Persist AI voice reply in chat history
    try:
        if hasattr(database, "add_chat_message"):
            database.add_chat_message(user_id, persona_key, "assistant", ai_raw_reply)
        if hasattr(database, "add_xp"):
            database.add_xp(user_id, amount=10)
    except Exception as save_err:
        logger.warning(f"[Voice Call] Save assistant speech error: {save_err}")
    
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
