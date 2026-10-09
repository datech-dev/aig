"""
Configuration Provider: Manages user-specific emotion preferences and defaults.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
from .models import UserEmotionPreferences
from .interfaces import ConfigurationProviderProtocol, EmotionStateRepositoryProtocol

logger = logging.getLogger(__name__)


class ConfigurationProvider(ConfigurationProviderProtocol):
    """
    Manages loading, updating, and applying user emotion preferences.
    """

    def __init__(self, repository: Optional[EmotionStateRepositoryProtocol] = None):
        self.repository = repository
        self._cache: Dict[str, UserEmotionPreferences] = {}

    def get_user_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        cache_key = f"{user_id}:{persona_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.repository:
            prefs = self.repository.get_preferences(user_id, persona_key)
            self._cache[cache_key] = prefs
            return prefs

        return self.get_default_preferences(user_id, persona_key)

    def update_user_preferences(self, preferences: UserEmotionPreferences) -> bool:
        cache_key = f"{preferences.user_id}:{preferences.persona_key}"
        preferences.updated_at = datetime.utcnow()
        self._cache[cache_key] = preferences

        if self.repository:
            return self.repository.save_preferences(preferences)
        return True

    def get_default_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        return UserEmotionPreferences(
            user_id=user_id,
            persona_key=persona_key,
            enabled_emotions={
                "happiness": True,
                "sadness": True,
                "anger": True,
                "affection": True,
                "playfulness": True,
                "curiosity": True,
                "surprise": True,
                "empathy": True,
                "jealousy": True,
                "possessiveness": True,
            },
            intensity_multipliers={
                "anger": 1.0,
                "possessiveness": 1.0,
            },
            interaction_mode="balanced",
            updated_at=datetime.utcnow(),
        )
