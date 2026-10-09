"""
Voice Output Adapter: Synthesizes TTS modulation parameters based on active emotional plan.
"""

from typing import Dict, Any, Optional
import re
from .base import BaseOutputAdapter
from ..models import ResponsePlan


class VoiceOutputAdapter(BaseOutputAdapter):
    """
    Voice adapter that maps emotion intensities to TTS parameters (pitch, speaking rate, voice emotion tag).
    """

    def __init__(self, tts_provider: Optional[Any] = None):
        self.tts_provider = tts_provider

    async def format_output(
        self,
        text_response: str,
        plan: ResponsePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Strip all formatting artifacts and action tags for spoken voice
        clean_speech = re.sub(r'\[.*?\]', '', text_response)
        clean_speech = re.sub(r'[*_~`#]', '', clean_speech).strip()

        params = dict(plan.voice_parameters)

        audio_bytes = None
        if self.tts_provider:
            try:
                audio_bytes = await self.tts_provider.synthesize(clean_speech, **params)
            except Exception:
                pass  # Graceful fallback, voice provider failure does not break text

        return {
            "type": "voice",
            "spoken_text": clean_speech,
            "voice_parameters": params,
            "has_audio": audio_bytes is not None,
            "audio_bytes": audio_bytes,
        }
