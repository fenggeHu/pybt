from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class NotificationIntent:
    intent_type: str
    run_id: str
    strategy_id: str
    symbol: str
    direction: str
    strength: float
    occurred_at: str
    dedupe_key: str
    message: str
    meta: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength,
            "occurred_at": self.occurred_at,
            "dedupe_key": self.dedupe_key,
            "message": self.message,
            "meta": dict(self.meta),
        }
