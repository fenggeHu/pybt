from apps.telegram_bot.telegram_bot import _format_event


def test_format_event_handles_notification_intent_event() -> None:
    ev = {
        "event_type": "NotificationIntentEvent",
        "data": {
            "intent_type": "strategy_signal",
            "message": "SIGNAL AAA LONG strength=0.8",
            "strategy_id": "plugin",
            "symbol": "AAA",
            "direction": "LONG",
        },
    }

    text = _format_event(ev)
    assert text == "SIGNAL AAA LONG strength=0.8"
