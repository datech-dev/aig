"""
Emotion State Manager: Manages emotional lifecycle, decay, combination, and conflict resolution.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math
import logging
from .models import (
    EmotionState,
    ActiveEmotion,
    ProposedEmotionChange,
    EmotionTransitionEvent,
    UserEmotionPreferences,
)
from .interfaces import (
    EmotionStateManagerProtocol,
    EmotionRegistryProtocol,
    TransitionPolicyProtocol,
    EmotionStateRepositoryProtocol,
)
from .registry import get_default_registry
from .transition_rules import TransitionRulesEngine

logger = logging.getLogger(__name__)


class EmotionStateManager:
    """
    Core service for managing conversational emotion state.
    Independent of any specific LLM provider or UI platform.
    """

    def __init__(
        self,
        registry: Optional[EmotionRegistryProtocol] = None,
        policy: Optional[TransitionPolicyProtocol] = None,
        repository: Optional[EmotionStateRepositoryProtocol] = None,
    ):
        self.registry = registry or get_default_registry()
        self.policy = policy or TransitionRulesEngine()
        self.repository = repository
        self._memory_cache: Dict[Tuple[int, str], EmotionState] = {}

    def get_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        """
        Retrieves the current emotional state for a user and persona.
        Applies decay based on elapsed time since the last interaction.
        """
        cache_key = (user_id, persona_key)
        if cache_key in self._memory_cache:
            state = self._memory_cache[cache_key]
        elif self.repository:
            state = self.repository.get_state(user_id, persona_key)
            self._memory_cache[cache_key] = state
        else:
            state = EmotionState(user_id=user_id, persona_key=persona_key)
            self._memory_cache[cache_key] = state

        # Apply decay dynamically on retrieval
        self._apply_decay(state)
        return state

    def apply_proposed_changes(
        self,
        user_id: int,
        persona_key: str,
        proposed_changes: List[ProposedEmotionChange],
        trigger_event: str = "user_message",
        preferences: Optional[UserEmotionPreferences] = None,
        now: Optional[datetime] = None,
    ) -> EmotionState:
        """
        Processes proposed changes through policy rules, updates state,
        resolves conflicts, updates primary emotion, and persists.
        """
        current_time = now or datetime.utcnow()
        state = self.get_state(user_id, persona_key)
        elapsed_seconds = (current_time - state.last_interaction).total_seconds() if state.last_interaction else 0.0

        # 1. Evaluate transitions via policy
        approved_ops = self.policy.evaluate_transitions(
            current_state=state,
            proposed_changes=proposed_changes,
            registry=self.registry,
            preferences=preferences,
            elapsed_seconds=elapsed_seconds,
        )

        applied_changes: List[Dict[str, Any]] = []

        # 2. Apply updates
        for op in approved_ops:
            e_id = op["emotion_id"]
            action = op["action"]
            new_intensity = op["new_intensity"]
            sub_emotion = op["sub_emotion"]
            reason = op["reason"]

            if action == "remove":
                if e_id in state.active_emotions:
                    del state.active_emotions[e_id]
                    applied_changes.append(op)
            else:
                if e_id in state.active_emotions:
                    active = state.active_emotions[e_id]
                    active.intensity = new_intensity
                    active.sub_emotion = sub_emotion
                    active.last_updated = current_time
                    active.turns_active += 1
                    active.peak_intensity = max(active.peak_intensity, new_intensity)
                    active.trigger_reason = reason
                else:
                    state.active_emotions[e_id] = ActiveEmotion(
                        emotion_id=e_id,
                        intensity=new_intensity,
                        sub_emotion=sub_emotion,
                        started_at=current_time,
                        last_updated=current_time,
                        peak_intensity=new_intensity,
                        turns_active=1,
                        trigger_reason=reason,
                    )
                applied_changes.append(op)

        # 3. Resolve conflicts among active emotions
        self._resolve_conflicts(state)

        # 4. Update primary emotion and baseline mood
        self._update_primary_and_mood(state)
        state.last_interaction = current_time

        # 5. Persist to cache and database
        cache_key = (user_id, persona_key)
        self._memory_cache[cache_key] = state
        if self.repository:
            self.repository.save_state(state)
            if applied_changes:
                event = EmotionTransitionEvent(
                    user_id=user_id,
                    persona_key=persona_key,
                    trigger_event=trigger_event,
                    proposed_changes=[p.__dict__ for p in proposed_changes],
                    applied_changes=applied_changes,
                    reason_code=applied_changes[0]["reason"] if applied_changes else "none",
                    confidence=applied_changes[0].get("confidence", 1.0) if applied_changes else 1.0,
                    created_at=current_time,
                )
                self.repository.log_transition_event(event)

        return state

    def reset_state(self, user_id: int, persona_key: str = "juhi") -> EmotionState:
        """Resets all active emotions back to neutral baseline."""
        state = EmotionState(
            user_id=user_id,
            persona_key=persona_key,
            active_emotions={},
            primary_emotion_id=None,
            current_mood="content",
            last_interaction=datetime.utcnow(),
        )
        cache_key = (user_id, persona_key)
        self._memory_cache[cache_key] = state
        if self.repository:
            self.repository.save_state(state)
        return state

    def set_direct_emotion(
        self,
        user_id: int,
        persona_key: str,
        emotion_id: str,
        intensity: float,
        sub_emotion: Optional[str] = None,
        reason: str = "direct_set",
    ) -> EmotionState:
        """Helper to directly set or force an emotion (useful for testing and admin overrides)."""
        prop = ProposedEmotionChange(
            emotion_id=emotion_id,
            target_intensity=intensity,
            sub_emotion=sub_emotion,
            confidence=1.0,
            reason=reason,
        )
        return self.apply_proposed_changes(
            user_id=user_id,
            persona_key=persona_key,
            proposed_changes=[prop],
            trigger_event="direct_override",
        )

    def _apply_decay(self, state: EmotionState, now: Optional[datetime] = None):
        """Applies mathematical time decay to active temporary emotions."""
        current_time = now or datetime.utcnow()
        if not state.last_interaction or not state.active_emotions:
            return

        elapsed_seconds = max(0.0, (current_time - state.last_interaction).total_seconds())
        if elapsed_seconds < 5.0:
            return  # Negligible elapsed time

        to_remove = []
        for e_id, active in state.active_emotions.items():
            defn = self.registry.get(e_id)
            if not defn or defn.decay.strategy == "none":
                continue

            decay_cfg = defn.decay
            if decay_cfg.strategy == "exponential":
                half_life = max(1.0, decay_cfg.half_life_seconds)
                # N(t) = N0 * (0.5 ^ (t / half_life))
                decay_factor = math.pow(0.5, elapsed_seconds / half_life)
                active.intensity = round(active.intensity * decay_factor, 4)
            elif decay_cfg.strategy == "linear":
                # Linear rate per minute
                rate_per_sec = decay_cfg.decay_rate_per_turn / 60.0
                active.intensity = max(0.0, round(active.intensity - (rate_per_sec * elapsed_seconds), 4))

            if active.intensity <= decay_cfg.min_threshold:
                to_remove.append(e_id)

        for e_id in to_remove:
            del state.active_emotions[e_id]

        if to_remove:
            self._update_primary_and_mood(state)

    def _resolve_conflicts(self, state: EmotionState):
        """
        Resolves conflicts between incompatible active emotions.
        Higher priority emotion suppresses or damps lower priority conflicting emotion.
        """
        active_ids = list(state.active_emotions.keys())
        for i in range(len(active_ids)):
            for j in range(i + 1, len(active_ids)):
                e_a = active_ids[i]
                e_b = active_ids[j]
                if e_a not in state.active_emotions or e_b not in state.active_emotions:
                    continue

                if not self.registry.is_compatible(e_a, e_b):
                    p_a = self.registry.get_priority(e_a)
                    p_b = self.registry.get_priority(e_b)

                    if p_a >= p_b:
                        # e_a dominates; suppress e_b
                        logger.info(f"Conflict resolution: '{e_a}' (p={p_a}) suppresses '{e_b}' (p={p_b})")
                        del state.active_emotions[e_b]
                    else:
                        # e_b dominates; suppress e_a
                        logger.info(f"Conflict resolution: '{e_b}' (p={p_b}) suppresses '{e_a}' (p={p_a})")
                        del state.active_emotions[e_a]

    def _update_primary_and_mood(self, state: EmotionState):
        """Calculates the dominant primary emotion and overall mood."""
        if not state.active_emotions:
            state.primary_emotion_id = None
            state.current_mood = "content"
            return

        # Rank active emotions by (intensity * priority_weight)
        ranked = sorted(
            state.active_emotions.values(),
            key=lambda a: a.intensity * (self.registry.get_priority(a.emotion_id) / 50.0),
            reverse=True,
        )

        top = ranked[0]
        state.primary_emotion_id = top.emotion_id

        # Derive mood
        if top.emotion_id == "anger":
            state.current_mood = "feisty" if top.sub_emotion == "playful_anger" else "upset"
        elif top.emotion_id == "possessiveness":
            state.current_mood = "clingy_and_loving"
        elif top.emotion_id == "happiness":
            state.current_mood = "cheerful"
        elif top.emotion_id == "sadness":
            state.current_mood = "melancholic"
        elif top.emotion_id == "playfulness":
            state.current_mood = "mischievous"
        elif top.emotion_id == "affection":
            state.current_mood = "deeply_loving"
        elif top.emotion_id == "curiosity":
            state.current_mood = "intrigued"
        elif top.emotion_id == "surprise":
            state.current_mood = "astonished"
        elif top.emotion_id == "empathy":
            state.current_mood = "nurturing"
        elif top.emotion_id == "jealousy":
            state.current_mood = "playfully_suspicious"
        else:
            state.current_mood = "expressive"
