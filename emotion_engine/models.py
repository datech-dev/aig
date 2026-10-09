"""
Data models and typed structures for Emotion and Behavior Engine.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json


@dataclass
class IntensityRange:
    min: float = 0.0
    max: float = 1.0

    def clamp(self, value: float) -> float:
        return max(self.min, min(self.max, value))


@dataclass
class DecayConfig:
    strategy: str = "exponential"  # "exponential", "linear", "step", "none"
    half_life_seconds: float = 900.0  # 15 minutes default for exponential
    decay_rate_per_turn: float = 0.1  # For linear or turn-based decay
    min_threshold: float = 0.05       # Below this, emotion resets to inactive


@dataclass
class ResponseStyleConfig:
    tone: str = "balanced"            # e.g., "playful", "warm", "direct", "reserved", "sassy"
    expressiveness: str = "intensity_based"
    prompt_instructions: Dict[str, str] = field(default_factory=dict)
    voice_modifiers: Dict[str, Any] = field(default_factory=dict)
    suggested_emojis: List[str] = field(default_factory=list)
    suggested_action_styles: List[str] = field(default_factory=list)


@dataclass
class MediaMappingConfig:
    preferred_gifs: List[str] = field(default_factory=list)
    suggested_stickers: List[str] = field(default_factory=list)
    image_prompt_modifiers: List[str] = field(default_factory=list)


@dataclass
class TriggerDefinition:
    keywords: List[str] = field(default_factory=list)
    intent_patterns: List[str] = field(default_factory=list)
    context_keys: List[str] = field(default_factory=list)
    default_sub_emotion: Optional[str] = None
    default_intensity_delta: float = 0.2


@dataclass
class EmotionDefinition:
    id: str
    display_name: str
    description: str = ""
    version: int = 1
    enabled: bool = True
    default_intensity: float = 0.2
    intensity_range: IntensityRange = field(default_factory=IntensityRange)
    sub_emotions: List[str] = field(default_factory=list)
    sub_emotion_descriptions: Dict[str, str] = field(default_factory=dict)
    triggers: List[TriggerDefinition] = field(default_factory=list)
    decay: DecayConfig = field(default_factory=DecayConfig)
    response_style: ResponseStyleConfig = field(default_factory=ResponseStyleConfig)
    compatible_emotions: List[str] = field(default_factory=list)
    conflicting_emotions: List[str] = field(default_factory=list)
    priority: int = 50  # Higher priority overrides lower priority on conflicts (1-100)
    safety_profile: str = "respectful_expression"
    media_mappings: MediaMappingConfig = field(default_factory=MediaMappingConfig)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmotionDefinition":
        d = dict(data)
        if "intensity_range" in d and isinstance(d["intensity_range"], dict):
            d["intensity_range"] = IntensityRange(**d["intensity_range"])
        if "decay" in d and isinstance(d["decay"], dict):
            d["decay"] = DecayConfig(**d["decay"])
        if "response_style" in d and isinstance(d["response_style"], dict):
            d["response_style"] = ResponseStyleConfig(**d["response_style"])
        if "media_mappings" in d and isinstance(d["media_mappings"], dict):
            d["media_mappings"] = MediaMappingConfig(**d["media_mappings"])
        if "triggers" in d and isinstance(d["triggers"], list):
            d["triggers"] = [TriggerDefinition(**t) if isinstance(t, dict) else t for t in d["triggers"]]
        return cls(**d)


@dataclass
class ActiveEmotion:
    emotion_id: str
    intensity: float
    sub_emotion: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    peak_intensity: float = 0.0
    turns_active: int = 0
    trigger_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion_id": self.emotion_id,
            "intensity": self.intensity,
            "sub_emotion": self.sub_emotion,
            "started_at": self.started_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "peak_intensity": self.peak_intensity,
            "turns_active": self.turns_active,
            "trigger_reason": self.trigger_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActiveEmotion":
        return cls(
            emotion_id=data["emotion_id"],
            intensity=float(data["intensity"]),
            sub_emotion=data.get("sub_emotion"),
            started_at=datetime.fromisoformat(data["started_at"]) if isinstance(data.get("started_at"), str) else (data.get("started_at") or datetime.utcnow()),
            last_updated=datetime.fromisoformat(data["last_updated"]) if isinstance(data.get("last_updated"), str) else (data.get("last_updated") or datetime.utcnow()),
            peak_intensity=float(data.get("peak_intensity", data["intensity"])),
            turns_active=int(data.get("turns_active", 0)),
            trigger_reason=data.get("trigger_reason", ""),
        )


@dataclass
class EmotionState:
    user_id: int
    persona_key: str = "juhi"
    active_emotions: Dict[str, ActiveEmotion] = field(default_factory=dict)
    primary_emotion_id: Optional[str] = None
    current_mood: str = "content"  # Broad baseline mood, e.g. "content", "playful", "pensive", "longing"
    last_interaction: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def get_intensity(self, emotion_id: str) -> float:
        if emotion_id in self.active_emotions:
            return self.active_emotions[emotion_id].intensity
        return 0.0

    def has_emotion(self, emotion_id: str, threshold: float = 0.1) -> bool:
        return self.get_intensity(emotion_id) >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "persona_key": self.persona_key,
            "active_emotions": {k: v.to_dict() for k, v in self.active_emotions.items()},
            "primary_emotion_id": self.primary_emotion_id,
            "current_mood": self.current_mood,
            "last_interaction": self.last_interaction.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmotionState":
        active = {}
        for k, v in data.get("active_emotions", {}).items():
            active[k] = ActiveEmotion.from_dict(v) if isinstance(v, dict) else v
        return cls(
            user_id=data["user_id"],
            persona_key=data.get("persona_key", "juhi"),
            active_emotions=active,
            primary_emotion_id=data.get("primary_emotion_id"),
            current_mood=data.get("current_mood", "content"),
            last_interaction=datetime.fromisoformat(data["last_interaction"]) if isinstance(data.get("last_interaction"), str) else (data.get("last_interaction") or datetime.utcnow()),
            version=data.get("version", 1),
        )


@dataclass
class ProposedEmotionChange:
    emotion_id: str
    target_intensity: Optional[float] = None
    delta_intensity: Optional[float] = None
    sub_emotion: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""
    trigger_type: str = "conversational_cue"  # "conversational_cue", "event", "memory", "direct_action"


@dataclass
class DetectionResult:
    detected_event: str = "general_chat"
    proposed_changes: List[ProposedEmotionChange] = field(default_factory=list)
    confidence: float = 1.0
    reason_codes: List[str] = field(default_factory=list)
    needs_clarification: bool = False
    raw_response: Optional[str] = None


@dataclass
class ResponsePlan:
    persona_key: str
    primary_emotion: Optional[str]
    active_emotions_summary: Dict[str, Dict[str, Any]]
    tone_directives: List[str]
    behavior_instructions: List[str]
    safety_boundary_notes: List[str]
    suggested_emojis: List[str]
    suggested_media_type: Optional[str] = None  # "gif", "sticker", "image", None
    media_intent_query: Optional[str] = None
    voice_parameters: Dict[str, Any] = field(default_factory=dict)
    prompt_fragment: str = ""


@dataclass
class UserEmotionPreferences:
    user_id: int
    persona_key: str = "juhi"
    enabled_emotions: Dict[str, bool] = field(default_factory=dict)
    intensity_multipliers: Dict[str, float] = field(default_factory=dict)
    interaction_mode: str = "balanced"  # "balanced", "intense", "gentle", "wholesome"
    custom_overrides: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_emotion_enabled(self, emotion_id: str, default: bool = True) -> bool:
        return self.enabled_emotions.get(emotion_id, default)

    def get_intensity_multiplier(self, emotion_id: str) -> float:
        return max(0.0, min(2.0, self.intensity_multipliers.get(emotion_id, 1.0)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "persona_key": self.persona_key,
            "enabled_emotions": self.enabled_emotions,
            "intensity_multipliers": self.intensity_multipliers,
            "interaction_mode": self.interaction_mode,
            "custom_overrides": self.custom_overrides,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserEmotionPreferences":
        return cls(
            user_id=data["user_id"],
            persona_key=data.get("persona_key", "juhi"),
            enabled_emotions=data.get("enabled_emotions", {}),
            intensity_multipliers=data.get("intensity_multipliers", {}),
            interaction_mode=data.get("interaction_mode", "balanced"),
            custom_overrides=data.get("custom_overrides", {}),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else (data.get("updated_at") or datetime.utcnow()),
        )


@dataclass
class EmotionTransitionEvent:
    user_id: int
    persona_key: str
    trigger_event: str
    proposed_changes: List[Dict[str, Any]]
    applied_changes: List[Dict[str, Any]]
    reason_code: str
    confidence: float
    created_at: datetime = field(default_factory=datetime.utcnow)
