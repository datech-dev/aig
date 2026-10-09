"""
Emotion Registry: Central catalog for loading, validating, and querying emotion definitions.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from .models import EmotionDefinition
from .schema import validate_emotion_dict, EmotionConfigValidationError
from .interfaces import EmotionRegistryProtocol

logger = logging.getLogger(__name__)

DEFAULT_DEFINITIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "definitions")


class EmotionRegistry(EmotionRegistryProtocol):
    """
    Central registry for emotion definitions.
    Loads declarative emotion configurations (JSON/dict), validates them against the formal schema,
    and provides query/registration capabilities.
    """

    def __init__(self, definitions_dir: Optional[str] = None, auto_load: bool = True):
        self.definitions_dir = definitions_dir or DEFAULT_DEFINITIONS_DIR
        self._emotions: Dict[str, EmotionDefinition] = {}
        self._validation_errors: Dict[str, List[str]] = {}
        if auto_load:
            self.load_definitions_from_directory(self.definitions_dir)

    def load_definitions_from_directory(self, dir_path: str) -> int:
        """Loads all .json emotion definition files from a directory."""
        if not os.path.exists(dir_path):
            logger.warning(f"Definitions directory does not exist: {dir_path}")
            return 0

        loaded_count = 0
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                filepath = os.path.join(dir_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    success = self.register_from_dict(data, overwrite=True)
                    if success:
                        loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load emotion definition file '{filename}': {e}")
                    self._validation_errors[filename] = [str(e)]
        logger.info(f"Loaded {loaded_count} emotion definitions from {dir_path}")
        return loaded_count

    def register_from_dict(self, data: Dict[str, Any], overwrite: bool = False) -> bool:
        """Validates and registers an emotion definition from a dictionary."""
        is_valid, errors = validate_emotion_dict(data)
        emotion_id = data.get("id", "unknown")
        if not is_valid:
            logger.error(f"Emotion config validation failed for '{emotion_id}': {errors}")
            self._validation_errors[emotion_id] = errors
            return False

        if emotion_id in self._emotions and not overwrite:
            logger.warning(f"Emotion '{emotion_id}' already registered. Use overwrite=True to replace.")
            return False

        try:
            definition = EmotionDefinition.from_dict(data)
            self._emotions[emotion_id] = definition
            if emotion_id in self._validation_errors:
                del self._validation_errors[emotion_id]
            return True
        except Exception as e:
            logger.error(f"Error instantiating EmotionDefinition for '{emotion_id}': {e}")
            self._validation_errors[emotion_id] = [str(e)]
            return False

    def register(self, definition: EmotionDefinition, overwrite: bool = False) -> bool:
        """Registers a typed EmotionDefinition object."""
        return self.register_from_dict(definition.to_dict(), overwrite=overwrite)

    def unregister(self, emotion_id: str) -> bool:
        """Removes an emotion definition from the registry."""
        if emotion_id in self._emotions:
            del self._emotions[emotion_id]
            return True
        return False

    def get(self, emotion_id: str) -> Optional[EmotionDefinition]:
        """Retrieves an emotion definition by ID."""
        return self._emotions.get(emotion_id)

    def list_all(self, enabled_only: bool = False) -> List[EmotionDefinition]:
        """Lists all registered emotion definitions."""
        if enabled_only:
            return [e for e in self._emotions.values() if e.enabled]
        return list(self._emotions.values())

    def get_validation_errors(self) -> Dict[str, List[str]]:
        """Returns any validation errors encountered during loading."""
        return dict(self._validation_errors)

    def is_compatible(self, emotion_a: str, emotion_b: str) -> bool:
        """Checks if two emotions are compatible for simultaneous co-existence."""
        if emotion_a == emotion_b:
            return True

        def_a = self.get(emotion_a)
        def_b = self.get(emotion_b)

        if not def_a or not def_b:
            return True  # Unknown emotions default to allowed

        # Check explicit conflict lists
        if emotion_b in def_a.conflicting_emotions or emotion_a in def_b.conflicting_emotions:
            return False

        # If compatible_emotions is defined and non-empty, check if it's listed
        if def_a.compatible_emotions and emotion_b not in def_a.compatible_emotions:
            # Not explicitly in compatible list, check if def_b allows def_a
            if def_b.compatible_emotions and emotion_a not in def_b.compatible_emotions:
                return False

        return True

    def get_priority(self, emotion_id: str) -> int:
        """Returns the priority of an emotion (default 50)."""
        defn = self.get(emotion_id)
        return defn.priority if defn else 50


# Global singleton instance for easy access
_default_registry: Optional[EmotionRegistry] = None

def get_default_registry() -> EmotionRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = EmotionRegistry()
    return _default_registry
