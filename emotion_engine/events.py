"""
Typed internal events for Emotion and Behavior Engine lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from .models import (
    EmotionState,
    ProposedEmotionChange,
    ResponsePlan,
    DetectionResult,
)


@dataclass
class UserMessageReceived:
    user_id: int
    persona_key: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmotionChangeProposed:
    user_id: int
    persona_key: str
    detection_result: DetectionResult
    current_state: EmotionState
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EmotionStateUpdated:
    user_id: int
    persona_key: str
    previous_state: Optional[EmotionState]
    new_state: EmotionState
    applied_changes: List[Dict[str, Any]]
    trigger_reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ResponsePlanCreated:
    user_id: int
    persona_key: str
    response_plan: ResponsePlan
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConversationStateReset:
    user_id: int
    persona_key: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
