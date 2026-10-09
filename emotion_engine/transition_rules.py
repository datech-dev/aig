"""
Transition Rules Engine: Evaluates and filters proposed emotional state transitions.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import math
import logging
from .models import (
    EmotionState,
    ProposedEmotionChange,
    UserEmotionPreferences,
)
from .interfaces import TransitionPolicyProtocol, EmotionRegistryProtocol

logger = logging.getLogger(__name__)


class TransitionRulesEngine(TransitionPolicyProtocol):
    """
    Applies configurable policies, clamps, confidence filters, and user overrides
    to proposed emotion state transitions.
    """

    def __init__(
        self,
        max_delta_per_turn: float = 0.35,
        min_confidence_threshold: float = 0.50,
        enable_decay: bool = True,
    ):
        self.max_delta_per_turn = max_delta_per_turn
        self.min_confidence_threshold = min_confidence_threshold
        self.enable_decay = enable_decay

    def evaluate_transitions(
        self,
        current_state: EmotionState,
        proposed_changes: List[ProposedEmotionChange],
        registry: EmotionRegistryProtocol,
        preferences: Optional[UserEmotionPreferences] = None,
        elapsed_seconds: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates proposed emotion changes and returns a list of approved transition operations:
        [
            {
                "emotion_id": "anger",
                "sub_emotion": "playful_anger",
                "new_intensity": 0.35,
                "delta": 0.20,
                "reason": "playful_banter",
                "approved": True,
                "action": "update"  # "update", "set", "remove"
            }
        ]
        """
        approved_transitions: List[Dict[str, Any]] = []

        for prop in proposed_changes:
            emotion_id = prop.emotion_id
            defn = registry.get(emotion_id)

            # 1. Registry verification
            if not defn or not defn.enabled:
                logger.debug(f"Emotion '{emotion_id}' is not registered or disabled in registry. Skipping.")
                continue

            # 2. User preferences check (user override)
            if preferences and not preferences.is_emotion_enabled(emotion_id, default=True):
                logger.info(f"Emotion '{emotion_id}' is disabled by user preferences. Skipping.")
                continue

            # 3. Confidence threshold check
            if prop.confidence < self.min_confidence_threshold:
                logger.debug(f"Proposed change for '{emotion_id}' rejected: confidence {prop.confidence} < {self.min_confidence_threshold}")
                continue

            current_intensity = current_state.get_intensity(emotion_id)
            multiplier = preferences.get_intensity_multiplier(emotion_id) if preferences else 1.0

            # Calculate raw delta & target
            if prop.target_intensity is not None:
                target = prop.target_intensity * multiplier
                raw_delta = target - current_intensity
            elif prop.delta_intensity is not None:
                raw_delta = prop.delta_intensity * multiplier
                target = current_intensity + raw_delta
            else:
                raw_delta = defn.default_intensity * multiplier
                target = current_intensity + raw_delta

            # 4. Clamp delta per turn
            clamped_delta = max(-self.max_delta_per_turn, min(self.max_delta_per_turn, raw_delta))
            final_intensity = current_intensity + clamped_delta

            # 5. Clamp to emotion definition intensity range
            final_intensity = defn.intensity_range.clamp(final_intensity)

            # 6. Validate sub-emotion
            sub_emotion = prop.sub_emotion
            if sub_emotion and defn.sub_emotions and sub_emotion not in defn.sub_emotions:
                logger.warning(f"Unknown sub-emotion '{sub_emotion}' for '{emotion_id}'. Falling back to default.")
                sub_emotion = defn.sub_emotions[0] if defn.sub_emotions else None
            elif not sub_emotion and defn.sub_emotions:
                sub_emotion = defn.sub_emotions[0]

            # 7. Check if intensity drops below threshold (removal / reset)
            if final_intensity <= defn.decay.min_threshold:
                action = "remove"
                final_intensity = 0.0
            else:
                action = "update"

            approved_transitions.append({
                "emotion_id": emotion_id,
                "sub_emotion": sub_emotion,
                "new_intensity": round(final_intensity, 4),
                "delta": round(clamped_delta, 4),
                "confidence": prop.confidence,
                "reason": prop.reason or prop.trigger_type,
                "approved": True,
                "action": action,
            })

        return approved_transitions
