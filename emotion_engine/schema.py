"""
Configuration Schema validation for declarative Emotion Definitions.
"""

from typing import Dict, Any, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMA_VERSIONS = {1}
SUPPORTED_DECAY_STRATEGIES = {"exponential", "linear", "step", "none"}
SUPPORTED_SAFETY_PROFILES = {"respectful_expression", "wholesome_only", "safe_intimacy", "unrestricted"}


class EmotionConfigValidationError(ValueError):
    """Raised when an emotion configuration fails schema validation."""
    pass


def validate_emotion_dict(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates an emotion definition dictionary against the formal schema.
    Returns (is_valid, list_of_error_messages).
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, ["Emotion configuration must be a dictionary/object."]

    # Required field: id
    emotion_id = data.get("id")
    if not emotion_id or not isinstance(emotion_id, str):
        errors.append("Field 'id' is required and must be a non-empty string.")
    elif not emotion_id.replace("_", "").isalnum():
        errors.append(f"Emotion id '{emotion_id}' must be alphanumeric with underscores only.")

    # Required field: display_name
    display_name = data.get("display_name")
    if not display_name or not isinstance(display_name, str):
        errors.append("Field 'display_name' is required and must be a non-empty string.")

    # Schema version
    version = data.get("version", 1)
    if not isinstance(version, int) or version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"Unsupported schema version '{version}'. Supported versions: {SUPPORTED_SCHEMA_VERSIONS}")

    # Intensity Range validation
    intensity_range = data.get("intensity_range", {"min": 0.0, "max": 1.0})
    if not isinstance(intensity_range, dict):
        errors.append("Field 'intensity_range' must be a dictionary with 'min' and 'max'.")
    else:
        min_v = intensity_range.get("min", 0.0)
        max_v = intensity_range.get("max", 1.0)
        if not isinstance(min_v, (int, float)) or not isinstance(max_v, (int, float)):
            errors.append("intensity_range 'min' and 'max' must be numeric.")
        elif min_v < 0.0 or max_v > 1.0 or min_v >= max_v:
            errors.append(f"Invalid intensity range [{min_v}, {max_v}]. Must satisfy 0.0 <= min < max <= 1.0.")

    # Default intensity
    default_intensity = data.get("default_intensity", 0.2)
    if not isinstance(default_intensity, (int, float)):
        errors.append("Field 'default_intensity' must be numeric.")
    elif isinstance(intensity_range, dict) and "min" in intensity_range and "max" in intensity_range:
        if not (intensity_range.get("min", 0.0) <= default_intensity <= intensity_range.get("max", 1.0)):
            errors.append(f"default_intensity ({default_intensity}) must fall within intensity_range.")

    # Sub-emotions
    sub_emotions = data.get("sub_emotions", [])
    if not isinstance(sub_emotions, list) or not all(isinstance(s, str) for s in sub_emotions):
        errors.append("Field 'sub_emotions' must be a list of strings.")

    # Decay validation
    decay = data.get("decay", {})
    if decay and isinstance(decay, dict):
        strategy = decay.get("strategy", "exponential")
        if strategy not in SUPPORTED_DECAY_STRATEGIES:
            errors.append(f"Invalid decay strategy '{strategy}'. Supported strategies: {SUPPORTED_DECAY_STRATEGIES}")
        half_life = decay.get("half_life_seconds", 900.0)
        if not isinstance(half_life, (int, float)) or half_life <= 0:
            errors.append("decay.half_life_seconds must be a positive number.")

    # Safety profile
    safety_profile = data.get("safety_profile", "respectful_expression")
    if safety_profile not in SUPPORTED_SAFETY_PROFILES:
        errors.append(f"Invalid safety_profile '{safety_profile}'. Supported: {SUPPORTED_SAFETY_PROFILES}")

    # Compatible / Conflicting emotions
    compatible = data.get("compatible_emotions", [])
    if not isinstance(compatible, list) or not all(isinstance(c, str) for c in compatible):
        errors.append("Field 'compatible_emotions' must be a list of string IDs.")

    conflicting = data.get("conflicting_emotions", [])
    if not isinstance(conflicting, list) or not all(isinstance(c, str) for c in conflicting):
        errors.append("Field 'conflicting_emotions' must be a list of string IDs.")

    # Priority
    priority = data.get("priority", 50)
    if not isinstance(priority, int) or not (1 <= priority <= 100):
        errors.append(f"Field 'priority' must be an integer between 1 and 100 (got {priority}).")

    return len(errors) == 0, errors
