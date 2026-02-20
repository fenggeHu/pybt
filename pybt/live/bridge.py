from typing import Any, Optional

from pybt.core.events import SignalEvent

from .contracts import NotificationIntent


def build_signal_notification_event(
    run_id: Optional[str], event: SignalEvent
) -> dict[str, Any]:
    run_value = run_id or ""
    direction = event.direction.value
    occurred_at = event.timestamp.isoformat()
    dedupe_key = (
        f"{run_value}:{event.strategy_id}:{event.symbol}:{occurred_at}:{direction}"
    )
    intent = NotificationIntent(
        intent_type="strategy_signal",
        run_id=run_value,
        strategy_id=event.strategy_id,
        symbol=event.symbol,
        direction=direction,
        strength=event.strength,
        occurred_at=occurred_at,
        dedupe_key=dedupe_key,
        message=(
            f"SIGNAL {event.symbol} {direction} "
            f"strength={event.strength:.6g} strategy={event.strategy_id}"
        ),
        meta=event.meta,
    )
    return {
        "event_type": "NotificationIntentEvent",
        "timestamp": occurred_at,
        "data": intent.to_payload(),
    }
