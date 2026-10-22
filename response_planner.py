"""Response planning layer.

The planner resolves application state before the LLM call. It does not generate
prompt prose or ask the LLM to resolve policy conflicts.
"""

from typing import Optional, Sequence

from context_models import RelationshipState, EmotionContext, ResponsePlanContext, SafetyDecision
import safety_engine


class ResponsePlanner:
    """Resolve relationship, emotion, language and media intent into one plan."""

    def plan(
        self,
        relationship: RelationshipState,
        emotion: Optional[EmotionContext] = None,
        user_message: Optional[str] = None,
        memories: Optional[Sequence[str]] = None,
        available_gifs: Optional[Sequence[str]] = None,
    ) -> ResponsePlanContext:
        constraints = []
        user_message = user_message or ""

        safety_decision = None
        if user_message:
            scan_res = safety_engine.scan_input_safety(user_message)
            safety_decision = SafetyDecision(
                is_safe=scan_res.is_safe,
                action="ALLOW" if scan_res.is_safe else "BLOCK",
                reason=None if scan_res.is_safe else scan_res.category,
                override_response=None if scan_res.is_safe else scan_res.refusal_message,
            )
            if not scan_res.is_safe:
                return ResponsePlanContext(
                    goal="return safety response",
                    tone="calm and respectful",
                    constraints=[],
                    safety_decision=safety_decision,
                )

        constraints.append("Keep the response strictly within 15 words (usually 1 short sentence) unless explicitly asked for a detailed explanation.")
        if relationship.chat_mode == "normal":
            tone = "warm, caring, supportive best friend"
            goal = "respond naturally with empathy and wholesome support"
            constraints.append("Keep the response wholesome and avoid explicit sexual content.")
        else:
            tone = "warm, affectionate, playful romantic companion"
            goal = "build a natural romantic connection while respecting policy and relationship boundaries"
            if relationship.xp < 250:
                constraints.append("Keep early-stage affection light, playful and non-explicit.")

        emotion_name = emotion.current_emotion if emotion else "neutral"
        emotion_intensity = max(0.0, min(1.0, emotion.intensity if emotion else 0.0))
        if emotion_name != "neutral":
            constraints.append(f"Express the current emotion naturally; do not announce it as a label. ({emotion_name}, {emotion_intensity:.2f})")
            if emotion and emotion.avoid:
                constraints.extend(f"Avoid {item}." for item in emotion.avoid)

        language, code_mixing = self._detect_language(user_message)
        ask_question = self._should_ask_question(user_message)
        media = self._detect_media_intent(user_message, available_gifs or [])

        relevant_memory_followup = any(
            isinstance(memory, str) and "pending event:" in memory.lower()
            for memory in (memories or [])
        )

        return ResponsePlanContext(
            goal=goal,
            tone=tone,
            constraints=constraints,
            safety_decision=safety_decision,
            emotion=emotion_name,
            emotion_intensity=emotion_intensity,
            language=language,
            code_mixing=code_mixing,
            ask_question=ask_question,
            initiative="medium",
            media=media,
            relevant_memory_followup=relevant_memory_followup,
        )

    @staticmethod
    def _should_ask_question(message: str) -> bool:
        stripped = message.strip().lower()
        if not stripped:
            return False
        if stripped.endswith("?"):
            return True
        if stripped in {"hi", "hello", "hey", "hii", "heyy", "haha", "lol", "hehe", "ok", "okay"}:
            return False
        return any(token in stripped for token in ("what", "why", "how", "when", "where", "who", "tell me"))

    @staticmethod
    def _detect_language(message: str):
        if not message:
            return "auto", None

        tamil = sum(1 for ch in message if "\u0B80" <= ch <= "\u0BFF")
        devanagari = sum(1 for ch in message if "\u0900" <= ch <= "\u097F")
        latin = sum(1 for ch in message if ch.isascii() and ch.isalpha())

        if tamil > 2:
            return "ta", "tamil_script" if latin else None
        if devanagari > 2:
            return "hi", "hindi_script" if latin else None

        lower = message.lower()
        tamil_roman = {"enna", "epdi", "seri", "illa", "iruka", "irukku", "romba", "saptiya", "sollu", "venum"}
        hindi_roman = {"kya", "kaise", "hai", "haan", "nahi", "acha", "accha", "mujhe", "tum", "aap", "kyun"}
        words = set(lower.replace("?", " ").replace("!", " ").split())
        if words & tamil_roman:
            return "ta", "tanglish"
        if words & hindi_roman:
            return "hi", "hinglish"
        return "en", None

    @staticmethod
    def _detect_media_intent(message: str, available_gifs: Sequence[str]):
        lower = (message or "").lower()
        photo_keywords = ("photo", "picture", "selfie", "pic", "pics", "image", "look like", "show yourself")
        action_keywords = ("send", "show", "give", "share", "take", "click", "your", "ur", "u", "a", "see", "want", "can i", "plz", "please")
        
        has_photo_word = any(pk in lower for pk in photo_keywords)
        has_action_word = any(ak in lower for ak in action_keywords)

        image_requested = (has_photo_word and has_action_word) or any(
            phrase in lower
            for phrase in (
                "send me a photo",
                "send a photo",
                "send me a picture",
                "send a picture",
                "send me a selfie",
                "send a selfie",
                "send me your selfie",
                "send your selfie",
                "show me your photo",
                "show me a picture",
                "show me your picture",
                "show your picture",
                "show me your selfie",
                "show your selfie",
                "your selfie",
                "ur selfie",
                "cute selfie",
                "take a selfie",
                "send selfie",
                "send pic",
                "send pics",
                "send photo",
                "send your pic",
                "send your photo",
                "send me your pic",
                "send me your photo",
            )
        )
        gif_requested = any(token in lower for token in ("gif", "reaction gif", "send a gif", "send gif")) or any(
            phrase in lower for phrase in ("kiss", "mwah", "blush", "lip lock", "cuddle")
        )
        return {
            "image_requested": image_requested,
            "gif_allowed": True,
            "gif_requested": gif_requested,
            "available_gifs": list(available_gifs),
        }


planner = ResponsePlanner()
