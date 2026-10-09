"""
Extensible Emotion and Behavior Engine for AI Companion (Juhi).
"""

from .models import (
    EmotionDefinition,
    EmotionState,
    ActiveEmotion,
    ProposedEmotionChange,
    DetectionResult,
    ResponsePlan,
    UserEmotionPreferences,
    EmotionTransitionEvent,
)
from .registry import EmotionRegistry
from .state_manager import EmotionStateManager
from .detector import EmotionDetector
from .transition_rules import TransitionRulesEngine
from .composer import ResponseStyleComposer
from .repository import EmotionStateRepository
from .config_provider import ConfigurationProvider

__all__ = [
    "EmotionDefinition",
    "EmotionState",
    "ActiveEmotion",
    "ProposedEmotionChange",
    "DetectionResult",
    "ResponsePlan",
    "UserEmotionPreferences",
    "EmotionTransitionEvent",
    "EmotionRegistry",
    "EmotionStateManager",
    "EmotionDetector",
    "TransitionRulesEngine",
    "ResponseStyleComposer",
    "EmotionStateRepository",
    "ConfigurationProvider",
]
