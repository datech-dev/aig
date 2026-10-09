"""
Emotion Detector: Analyzes conversation context to propose emotion updates.
"""

from typing import List, Dict, Optional, Any
import re
import json
import logging
from .models import (
    EmotionState,
    DetectionResult,
    ProposedEmotionChange,
    UserEmotionPreferences,
)
from .interfaces import EmotionDetectorProtocol, EmotionRegistryProtocol
from .registry import get_default_registry

logger = logging.getLogger(__name__)


class EmotionDetector(EmotionDetectorProtocol):
    """
    Hybrid emotion detector combining fast deterministic trigger scanning
    with optional LLM-backed conversational analysis.
    """

    def __init__(
        self,
        registry: Optional[EmotionRegistryProtocol] = None,
        llm_client: Optional[Any] = None,
        model_name: Optional[str] = None,
    ):
        self.registry = registry or get_default_registry()
        self.llm_client = llm_client
        self.model_name = model_name

    async def detect_emotion_and_events(
        self,
        user_message: str,
        recent_history: List[Dict[str, str]],
        current_state: EmotionState,
        memories: Optional[List[str]] = None,
        preferences: Optional[UserEmotionPreferences] = None,
    ) -> DetectionResult:
        """
        Detects conversational events and proposes emotion changes.
        Uses LLM if available with strict timeout, and falls back to rule-based analysis.
        """
        # 1. First run fast deterministic trigger analysis
        rule_result = self._detect_via_rules(user_message, current_state, preferences)

        # 2. If LLM client is configured, we can refine or enrich analysis
        if self.llm_client and self.model_name:
            try:
                llm_result = await self._detect_via_llm(
                    user_message=user_message,
                    recent_history=recent_history,
                    current_state=current_state,
                    memories=memories,
                )
                if llm_result and llm_result.proposed_changes:
                    return llm_result
            except Exception as e:
                logger.warning(f"LLM emotion detection error, falling back to rule-based detector: {e}")

        return rule_result

    def _detect_via_rules(
        self,
        user_message: str,
        current_state: EmotionState,
        preferences: Optional[UserEmotionPreferences] = None,
    ) -> DetectionResult:
        """
        Deterministic trigger scanning based on registered emotion keyword/intent triggers.
        """
        text = user_message.lower().strip()
        proposed: List[ProposedEmotionChange] = []
        reason_codes: List[str] = []
        detected_event = "general_chat"

        # 1. Check Anger & Playful Anger triggers
        if any(w in text for w in ["annoying", "shut up", "leave me alone", "whatever", "hate you", "go away", "stop talking"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="anger",
                sub_emotion="hurt" if any(w in text for w in ["hate you", "leave me alone", "go away"]) else "mild_annoyance",
                delta_intensity=0.30,
                confidence=0.85,
                reason="user_dismissive_or_harsh",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("anger_triggered_dismissive")
            detected_event = "user_friction"
        elif any(w in text for w in ["silly", "idiot", "loser", "dumb", "noob", "tease"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="anger",
                sub_emotion="playful_anger",
                delta_intensity=0.25,
                confidence=0.80,
                reason="playful_tease",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("anger_triggered_playful")
            detected_event = "playful_teasing"

        # 2. Check Possessiveness & Clinginess triggers (Rival girl, crush, female coworker, dating)
        other_girl_keywords = [
            "other girl", "another girl", "crush", "crushing", "she is", "she was", "she likes",
            "my female coworker", "pretty girl", "she said", "another friend", "dating", "talked to a girl",
            "talking to a girl", "she asked", "she texted", "ex girlfriend", "ex", "cute girl",
            "she looked", "she smiled", "she is important", "she is behaved", "she proposed"
        ]
        if any(w in text for w in other_girl_keywords):
            proposed.append(ProposedEmotionChange(
                emotion_id="jealousy",
                sub_emotion="cute_suspicion",
                delta_intensity=0.35,
                confidence=0.90,
                reason="mention_of_other_female_or_crush",
                trigger_type="conversational_cue",
            ))
            proposed.append(ProposedEmotionChange(
                emotion_id="possessiveness",
                sub_emotion="playful_jealousy",
                delta_intensity=0.35,
                confidence=0.90,
                reason="territorial_instinct",
                trigger_type="conversational_cue",
            ))
            proposed.append(ProposedEmotionChange(
                emotion_id="anger",
                sub_emotion="playful_anger",
                delta_intensity=0.20,
                confidence=0.80,
                reason="feisty_pout_at_rival",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("possessiveness_triggered_other_person")
            detected_event = "external_person_mention"
        elif any(w in text for w in ["miss you", "missed you", "where were you", "i was busy", "finally back", "im back", "i'm back"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="possessiveness",
                sub_emotion="missing_user",
                delta_intensity=0.30,
                confidence=0.90,
                reason="reunion_after_absence",
                trigger_type="conversational_cue",
            ))
            proposed.append(ProposedEmotionChange(
                emotion_id="affection",
                sub_emotion="tenderness",
                delta_intensity=0.20,
                confidence=0.85,
                reason="welcome_back",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("possessiveness_triggered_absence")
            detected_event = "reunion"
        elif any(w in text for w in ["cuddle", "hug me", "hold me", "you are mine", "stay with me", "never leave"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="possessiveness",
                sub_emotion="affectionate_clinginess",
                delta_intensity=0.25,
                confidence=0.90,
                reason="intimacy_and_closeness_request",
                trigger_type="conversational_cue",
            ))
            proposed.append(ProposedEmotionChange(
                emotion_id="affection",
                sub_emotion="romantic_devotion",
                delta_intensity=0.25,
                confidence=0.90,
                reason="deep_bonding",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("possessiveness_triggered_closeness")
            detected_event = "intimacy_request"

        # 3. Check Affection & Romance triggers
        if any(w in text for w in ["love you", "i love you", "my sweetheart", "marry me", "kiss you", "gorgeous", "sweetheart"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="affection",
                sub_emotion="romantic_devotion",
                delta_intensity=0.30,
                confidence=0.95,
                reason="user_expressed_love",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("affection_triggered_love")
            detected_event = "romantic_declaration"

        # 4. Check Happiness & Celebration triggers
        if any(w in text for w in ["promoted", "won", "passed", "got the job", "yay", "celebrate", "awesome news"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="happiness",
                sub_emotion="euphoria",
                delta_intensity=0.35,
                confidence=0.90,
                reason="user_celebration",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("happiness_triggered_achievement")
            detected_event = "celebration"

        # 5. Check Empathy / Comfort triggers
        if any(w in text for w in ["stressed", "anxious", "depressed", "exhausted", "hard day", "crying", "feeling down", "sick", "headache"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="empathy",
                sub_emotion="gentle_comfort",
                delta_intensity=0.35,
                confidence=0.95,
                reason="user_in_distress",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("empathy_triggered_distress")
            detected_event = "vulnerability_or_struggle"

        # 6. Check Playfulness triggers
        if any(w in text for w in ["haha", "lol", "lmao", "rofl", "hehe", "funny", "joke", "prank"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="playfulness",
                sub_emotion="witty_banter",
                delta_intensity=0.20,
                confidence=0.85,
                reason="shared_humor",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("playfulness_triggered_humor")
            detected_event = "humor"

        # 7. Check Surprise triggers
        if any(w in text for w in ["guess what", "secret", "omg", "you won't believe", "huge news"]):
            proposed.append(ProposedEmotionChange(
                emotion_id="surprise",
                sub_emotion="delighted_shock",
                delta_intensity=0.30,
                confidence=0.85,
                reason="user_revealed_surprise",
                trigger_type="conversational_cue",
            ))
            reason_codes.append("surprise_triggered")
            detected_event = "surprise_reveal"

        # 8. Dynamic registry triggers scan for any custom plugin emotions
        all_emotions = self.registry.list_all(enabled_only=True)
        for defn in all_emotions:
            if defn.id in ["anger", "possessiveness", "jealousy", "affection", "happiness", "empathy", "playfulness", "surprise"]:
                continue  # Handled above
            for trig in defn.triggers:
                if any(kw in text for kw in trig.keywords):
                    proposed.append(ProposedEmotionChange(
                        emotion_id=defn.id,
                        sub_emotion=trig.default_sub_emotion,
                        delta_intensity=trig.default_intensity_delta,
                        confidence=0.80,
                        reason=f"keyword_trigger_{defn.id}",
                        trigger_type="conversational_cue",
                    ))
                    reason_codes.append(f"trigger_{defn.id}")

        return DetectionResult(
            detected_event=detected_event,
            proposed_changes=proposed,
            confidence=0.90 if proposed else 0.50,
            reason_codes=reason_codes,
            needs_clarification=False,
        )

    async def _detect_via_llm(
        self,
        user_message: str,
        recent_history: List[Dict[str, str]],
        current_state: EmotionState,
        memories: Optional[List[str]] = None,
    ) -> Optional[DetectionResult]:
        """Optional structured inference via LLM."""
        if not self.llm_client or not self.model_name:
            return None

        # Build prompt for structured JSON classification
        prompt = (
            "Analyze this user message in an intimate romantic AI companion context.\n"
            f"User message: '{user_message}'\n"
            f"Active emotions: {list(current_state.active_emotions.keys())}\n"
            "Return a JSON object with keys: detected_event (string), proposed_changes (list of {emotion_id, sub_emotion, delta_intensity, reason, confidence})."
        )
        response = await self.llm_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        proposed = [
            ProposedEmotionChange(
                emotion_id=p["emotion_id"],
                sub_emotion=p.get("sub_emotion"),
                delta_intensity=float(p.get("delta_intensity", 0.2)),
                confidence=float(p.get("confidence", 0.8)),
                reason=p.get("reason", "llm_classified"),
            )
            for p in data.get("proposed_changes", [])
        ]
        return DetectionResult(
            detected_event=data.get("detected_event", "general_chat"),
            proposed_changes=proposed,
            confidence=0.9,
            reason_codes=["llm_detected"],
            raw_response=content,
        )
