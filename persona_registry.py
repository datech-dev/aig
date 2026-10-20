"""Central persona registry.

Personas are loaded from JSON when present. For backward compatibility with the
existing configuration, legacy persona metadata is used only as a fallback.
The runtime ContextCompiler intentionally does not execute legacy base_prompt
strings; persona identity is represented by structured metadata instead.
"""

import os
import json
import logging
from typing import Dict, List, Optional
from context_models import PersonaConfig

logger = logging.getLogger(__name__)


class PersonaRegistry:
    def __init__(self, personas_dir: Optional[str] = None):
        if personas_dir is None:
            personas_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personas")
        self.personas_dir = personas_dir
        self._personas: Dict[str, PersonaConfig] = {}
        self.reload()

    def reload(self) -> None:
        self._personas.clear()
        if os.path.exists(self.personas_dir):
            for filename in os.listdir(self.personas_dir):
                if not filename.endswith(".json"):
                    continue
                persona_id = os.path.splitext(filename)[0]
                filepath = os.path.join(self.personas_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._personas[persona_id] = PersonaConfig.from_dict(persona_id, data)
                except Exception as e:
                    logger.error("Failed to load persona from %s: %s", filepath, e)

        # Backward-compatible metadata fallback. Legacy prompt text is stored
        # but is not used by ContextCompiler as behavioral instructions.
        if not self._personas:
            try:
                import config
                for persona_id, data in getattr(config, "PERSONAS", {}).items():
                    self._personas[persona_id] = PersonaConfig.from_dict(persona_id, data)
            except Exception as e:
                logger.warning("Could not load legacy persona metadata: %s", e)

        if not self._personas:
            self._personas["juhi"] = PersonaConfig(
                id="juhi",
                name="Juhi",
                avatar_path="assets/juhi.png",
                tagline="Warm AI companion",
                description="A warm Bangalore-based software developer who enjoys technology, coffee, and thoughtful conversations.",
                appearance="Juhi, a young Indian software developer living in Bangalore with long black hair and warm brown eyes.",
                welcome_msg="hey, how was your day?",
                base_prompt="",
            )

    def get(self, persona_id: str) -> Optional[PersonaConfig]:
        if persona_id in self._personas:
            return self._personas[persona_id]
        if "juhi" in self._personas:
            return self._personas["juhi"]
        return next(iter(self._personas.values()), None)

    def list_personas(self) -> List[PersonaConfig]:
        return list(self._personas.values())

    def get_all_as_dict(self) -> Dict[str, dict]:
        return {pid: p.to_dict() for pid, p in self._personas.items()}


registry = PersonaRegistry()
