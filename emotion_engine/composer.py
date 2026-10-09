"""
Response Style Composer: Converts active emotional state into structured response plans and prompt instructions.
"""

from typing import List, Dict, Optional, Any
import logging
from .models import (
    EmotionState,
    ResponsePlan,
    UserEmotionPreferences,
)
from .interfaces import ResponseStyleComposerProtocol, EmotionRegistryProtocol
from .registry import get_default_registry

logger = logging.getLogger(__name__)


class ResponseStyleComposer(ResponseStyleComposerProtocol):
    """
    Composes structured prompt fragments and behavioral directives from active emotions.
    Maintains clean separation between base character personality, baseline mood, active emotions,
    and output media adapters.
    """

    def __init__(self, registry: Optional[EmotionRegistryProtocol] = None):
        self.registry = registry or get_default_registry()

    def compose_plan(
        self,
        current_state: EmotionState,
        base_persona_key: str = "juhi",
        relationship_xp: int = 0,
        chat_mode: str = "normal",
        memories: Optional[List[str]] = None,
        preferences: Optional[UserEmotionPreferences] = None,
        channel: str = "telegram",
    ) -> ResponsePlan:
        """
        Synthesizes active emotions, personality, relationship stage, and safety boundaries into a ResponsePlan.
        """
        tone_directives: List[str] = []
        behavior_instructions: List[str] = []
        safety_boundaries: List[str] = []
        suggested_emojis: List[str] = []
        active_summary: Dict[str, Dict[str, Any]] = {}
        voice_params: Dict[str, Any] = {"pitch": 1.0, "speed": 1.0, "emotion": "neutral"}
        preferred_gifs: List[str] = []

        # 1. Baseline mood directive
        tone_directives.append(f"Current baseline mood: {current_state.current_mood}.")

        # 2. Process active emotions in priority order
        sorted_actives = sorted(
            current_state.active_emotions.values(),
            key=lambda a: (a.intensity * (self.registry.get_priority(a.emotion_id) / 50.0)),
            reverse=True,
        )

        for active in sorted_actives:
            e_id = active.emotion_id
            defn = self.registry.get(e_id)
            if not defn:
                continue

            active_summary[e_id] = {
                "display_name": defn.display_name,
                "intensity": active.intensity,
                "sub_emotion": active.sub_emotion,
                "intensity_level": self._describe_intensity(active.intensity),
            }

            # Style instructions
            resp_style = defn.response_style
            sub_inst = resp_style.prompt_instructions.get(active.sub_emotion or "")
            if sub_inst:
                behavior_instructions.append(f"[{defn.display_name} ({active.sub_emotion}, intensity={active.intensity:.2f})]: {sub_inst}")
            elif defn.description:
                behavior_instructions.append(f"[{defn.display_name} (intensity={active.intensity:.2f})]: Express {defn.description.lower()}")

            # Suggested emojis
            for em in resp_style.suggested_emojis:
                if em not in suggested_emojis:
                    suggested_emojis.append(em)

            # Preferred media mappings
            for g in defn.media_mappings.preferred_gifs:
                if g not in preferred_gifs:
                    preferred_gifs.append(g)

            # Safety rules
            if defn.custom_metadata.get("boundary_rule"):
                safety_boundaries.append(f"Safety constraint for {defn.display_name}: {defn.custom_metadata['boundary_rule']}")

            # Voice tuning
            if resp_style.voice_modifiers:
                voice_params["pitch"] += resp_style.voice_modifiers.get("pitch_offset", 0.0) * active.intensity
                voice_params["speed"] += resp_style.voice_modifiers.get("rate_offset", 0.0) * active.intensity
                if "emotion_tag" in resp_style.voice_modifiers and active.intensity >= 0.3:
                    voice_params["emotion"] = resp_style.voice_modifiers["emotion_tag"]

        # 3. Build dynamic prompt fragment
        prompt_lines: List[str] = []
        if active_summary:
            prompt_lines.append("\n### 🎭 DYNAMIC EMOTION & BEHAVIOR ENGINE (Active Emotional State):")
            active_items = [
                f"{v['display_name']} ({v['intensity_level']}, intensity={v['intensity']:.2f}, sub={v['sub_emotion']})"
                for v in active_summary.values()
            ]
            prompt_lines.append(f"- Active Emotions: {', '.join(active_items)}")
            
            if behavior_instructions:
                prompt_lines.append("- Behavioral & Tone Guidance for this turn:")
                for inst in behavior_instructions:
                    prompt_lines.append(f"  * {inst}")

            if safety_boundaries:
                for sb in safety_boundaries:
                    prompt_lines.append(f"- CRITICAL EMOTION BOUNDARY: {sb}")

            if suggested_emojis:
                prompt_lines.append(f"- Recommended expressive emojis to weave naturally: {' '.join(suggested_emojis[:6])}")

        prompt_fragment = "\n".join(prompt_lines)

        # Decide suggested media query
        media_intent = None
        if preferred_gifs and sorted_actives and sorted_actives[0].intensity >= 0.4:
            media_intent = preferred_gifs[0]

        return ResponsePlan(
            persona_key=base_persona_key,
            primary_emotion=current_state.primary_emotion_id,
            active_emotions_summary=active_summary,
            tone_directives=tone_directives,
            behavior_instructions=behavior_instructions,
            safety_boundary_notes=safety_boundaries,
            suggested_emojis=suggested_emojis,
            suggested_media_type="gif" if media_intent else None,
            media_intent_query=media_intent,
            voice_parameters=voice_params,
            prompt_fragment=prompt_fragment,
        )

    def _describe_intensity(self, intensity: float) -> str:
        if intensity >= 0.75:
            return "high"
        elif intensity >= 0.40:
            return "moderate"
        elif intensity >= 0.15:
            return "mild"
        return "subtle"
