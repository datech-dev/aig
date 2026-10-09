"""
Protocols and interfaces for the Emotion and Behavior Engine.
"""

from typing import Protocol, runtime_checkable, Dict, List, Optional, Any
from datetime import datetime
from .models import (
    EmotionDefinition,
    EmotionState,
    ProposedEmotionChange,
    DetectionResult,
    ResponsePlan,
    UserEmotionPreferences,
    EmotionTransitionEvent,
)


@runtime_checkable
class EmotionRegistryProtocol(Protocol):
    """Registry interface for emotion definitions."""
    def get(self, emotion_id: str) -> Optional[EmotionDefinition]:
        ...

    def list_all(self, enabled_only: bool = False) -> List[EmotionDefinition]:
        ...

    def register(self, definition: EmotionDefinition, overwrite: bool = False) -> bool:
        ...

    def unregister(self, emotion_id: str) -> bool:
        ...

    def is_compatible(self, emotion_a: str, emotion_b: str) -> bool:
        ...


@runtime_checkable
class EmotionStateManagerProtocol(Protocol):
    """Interface for managing emotional state, transitions, decay, and persistence."""
    def get_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        ...

    def apply_proposed_changes(
        self,
        user_id: int,
        persona_key: str,
        proposed_changes: List[ProposedEmotionChange],
        trigger_event: str = "user_message",
        preferences: Optional[UserEmotionPreferences] = None,
        now: Optional[datetime] = None,
    ) -> EmotionState:
        ...

    def reset_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        ...



@runtime_checkable
class EmotionDetectorProtocol(Protocol):
    """Detector interface for extracting proposed emotional changes from conversation."""
    async def detect_emotion_and_events(
        self,
        user_message: str,
        recent_history: List[Dict[str, str]],
        current_state: EmotionState,
        memories: Optional[List[str]] = None,
        preferences: Optional[UserEmotionPreferences] = None,
    ) -> DetectionResult:
        ...


@runtime_checkable
class TransitionPolicyProtocol(Protocol):
    """Policy engine determining which proposed changes to approve/clamp/modify."""
    def evaluate_transitions(
        self,
        current_state: EmotionState,
        proposed_changes: List[ProposedEmotionChange],
        registry: EmotionRegistryProtocol,
        preferences: Optional[UserEmotionPreferences] = None,
        elapsed_seconds: float = 0.0,
    ) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class EmotionStateRepositoryProtocol(Protocol):
    """Persistence repository for user emotion state and event logs."""
    def get_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        ...

    def save_state(self, state: EmotionState) -> bool:
        ...

    def get_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        ...

    def save_preferences(self, preferences: UserEmotionPreferences) -> bool:
        ...

    def log_transition_event(self, event: EmotionTransitionEvent) -> bool:
        ...


@runtime_checkable
class ResponseStyleComposerProtocol(Protocol):
    """Composes structured response plans and prompt instructions from active emotion state."""
    def compose_plan(
        self,
        current_state: EmotionState,
        base_persona_key: str,
        relationship_xp: int,
        chat_mode: str = "normal",
        memories: Optional[List[str]] = None,
        preferences: Optional[UserEmotionPreferences] = None,
        channel: str = "telegram",
    ) -> ResponsePlan:
        ...


@runtime_checkable
class OutputAdapterProtocol(Protocol):
    """Adapter transforming response plan for specific output channels/media."""
    async def format_output(
        self,
        text_response: str,
        plan: ResponsePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...


@runtime_checkable
class ConfigurationProviderProtocol(Protocol):
    """Provides user and system emotion behavior configuration."""
    def get_user_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        ...

    def update_user_preferences(self, preferences: UserEmotionPreferences) -> bool:
        ...

    def get_default_preferences(self, user_id: int, persona_key: str = "juhi") -> UserEmotionPreferences:
        ...
