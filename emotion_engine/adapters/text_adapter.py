"""
Text Output Adapter: Formats and cleans text responses according to emotion style rules.
"""

from typing import Dict, Any, Optional
import re
from .base import BaseOutputAdapter
from ..models import ResponsePlan


class TextOutputAdapter(BaseOutputAdapter):
    """
    Standard text adapter for messaging platforms (Telegram, Web, App).
    Cleans tags and handles emotional formatting nuances.
    """

    async def format_output(
        self,
        text_response: str,
        plan: ResponsePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cleaned = text_response.strip()

        # Remove system command tags if present in text payload
        cleaned = re.sub(r'\[GENERATE_IMAGE:\s*.*?\]', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\[SEND_GIF:\s*.*?\]', '', cleaned, flags=re.IGNORECASE).strip()

        return {
            "type": "text",
            "text": cleaned,
            "primary_emotion": plan.primary_emotion,
            "tone": plan.tone_directives,
            "suggested_emojis": plan.suggested_emojis,
        }
