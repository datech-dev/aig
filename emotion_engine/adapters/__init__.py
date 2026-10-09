"""
Output adapters package for formatting response plans across text, voice, stickers, gifs, and images.
"""

from .base import BaseOutputAdapter
from .text_adapter import TextOutputAdapter
from .voice_adapter import VoiceOutputAdapter
from .media_adapter import MediaOutputAdapter

__all__ = [
    "BaseOutputAdapter",
    "TextOutputAdapter",
    "VoiceOutputAdapter",
    "MediaOutputAdapter",
]
