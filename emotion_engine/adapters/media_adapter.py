"""
Media Output Adapter: Selects GIFs, stickers, or visual prompts based on the emotional plan.
"""

from typing import Dict, Any, Optional, List
import re
import os
import logging
from .base import BaseOutputAdapter
from ..models import ResponsePlan

logger = logging.getLogger(__name__)


class MediaOutputAdapter(BaseOutputAdapter):
    """
    Adapter for selecting or preparing rich media (GIFs, stickers, generated images)
    that reflect the current emotional response plan.
    """

    def __init__(self, available_gifs: Optional[List[str]] = None):
        self.available_gifs = available_gifs or []

    async def format_output(
        self,
        text_response: str,
        plan: ResponsePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "type": "media",
            "has_media": False,
            "media_type": None,
            "media_target": None,
        }

        # 1. Check explicit tag in response text first
        gif_match = re.search(r'\[SEND_GIF:\s*(.*?)(?:\]|$)', text_response, re.IGNORECASE)
        if gif_match:
            query = gif_match.group(1).strip()
            result.update({
                "has_media": True,
                "media_type": "gif",
                "media_target": query,
                "source": "explicit_tag",
            })
            return result

        image_match = re.search(r'\[GENERATE_IMAGE:\s*(.*?)(?:\]|$)', text_response, re.IGNORECASE | re.DOTALL)
        if image_match:
            result.update({
                "has_media": True,
                "media_type": "image",
                "media_target": image_match.group(1).strip(),
                "source": "explicit_tag",
            })
            return result

        # 2. Plan-based recommendation
        if plan.suggested_media_type and plan.media_intent_query:
            result.update({
                "has_media": True,
                "media_type": plan.suggested_media_type,
                "media_target": plan.media_intent_query,
                "source": "plan_recommendation",
            })

        return result
