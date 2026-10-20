"""Structured memory representation with explicit type and TTL semantics."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MemoryItem:
    id: Optional[int]
    user_id: int
    memory_text: str
    memory_type: str = "fact"  # fact, preference, event, emotional_state, temporary
    valid_until: Optional[str] = None
    importance: int = 1
    confidence: float = 1.0
    created_at: Optional[str] = None

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        if not self.valid_until:
            return False
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        try:
            exp_str = self.valid_until.replace("Z", "+00:00")
            dt = datetime.fromisoformat(exp_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return current_time > dt
        except Exception:
            # Invalid TTLs are treated as non-expiring for backward compatibility.
            return False
