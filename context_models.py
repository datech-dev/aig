"""Typed models used by the Juhi response-planning and context-compilation pipeline."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PersonaConfig:
    id: str
    name: str
    avatar_path: str
    tagline: str
    description: str
    appearance: str
    welcome_msg: str
    base_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "avatar_path": self.avatar_path,
            "tagline": self.tagline,
            "description": self.description,
            "appearance": self.appearance,
            "welcome_msg": self.welcome_msg,
            "base_prompt": self.base_prompt,
        }

    @classmethod
    def from_dict(cls, persona_id: str, data: Dict[str, Any]) -> "PersonaConfig":
        return cls(
            id=persona_id,
            name=data.get("name", "Juhi"),
            avatar_path=data.get("avatar_path", "assets/juhi.png"),
            tagline=data.get("tagline", ""),
            description=data.get("description", ""),
            appearance=data.get("appearance", ""),
            welcome_msg=data.get("welcome_msg", ""),
            base_prompt=data.get("base_prompt", ""),
        )


@dataclass
class RelationshipState:
    level: int = 1
    xp: int = 0
    title: str = "Acquaintances"
    guideline: str = "Be polite, friendly, helpful, and respectful."
    chat_mode: str = "normal"
    user_gender: str = "male"
    ai_gender: str = "female"
    user_nickname: Optional[str] = None
    ai_nickname: Optional[str] = None


@dataclass
class EmotionContext:
    current_emotion: str = "neutral"
    intensity: float = 0.0
    trigger: Optional[str] = None
    behaviors: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)


@dataclass
class MemoryContext:
    memories: List[str] = field(default_factory=list)
    time_context: Optional[str] = None
    recent_topics: List[str] = field(default_factory=list)


@dataclass
class SafetyDecision:
    is_safe: bool = True
    action: str = "ALLOW"
    reason: Optional[str] = None
    override_response: Optional[str] = None


@dataclass
class ResponsePlanContext:
    goal: str = "respond naturally"
    tone: str = "warm, casual, affectionate"
    constraints: List[str] = field(default_factory=list)
    safety_decision: Optional[SafetyDecision] = None
    emotion: str = "neutral"
    emotion_intensity: float = 0.0
    language: str = "auto"
    code_mixing: Optional[str] = None
    ask_question: bool = False
    initiative: str = "medium"
    media: Optional[Dict[str, Any]] = None
    relevant_memory_followup: bool = False


@dataclass
class LLMContext:
    persona: PersonaConfig
    relationship: RelationshipState
    emotion: EmotionContext
    memory: MemoryContext
    response_plan: ResponsePlanContext
    user_message: str
