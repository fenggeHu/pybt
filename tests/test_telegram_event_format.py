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


def test_format_event_handles_data_source_error_event() -> None:
    ev = {
        "event_type": "DataSourceStatusEvent",
        "data": {
            "source_type": "sse",
            "status": "error",
            "failures": 2,
            "cooldown_seconds": 2.0,
            "message": "timeout",
        },
    }
    text = _format_event(ev)
    assert text is not None
    assert "DATA SOURCE ALERT" in text
    assert "source=sse" in text
    assert "status=error" in text


def test_format_event_ignores_non_error_source_status() -> None:
    ev = {
        "event_type": "DataSourceStatusEvent",
        "data": {
            "source_type": "sse",
            "status": "ok",
            "message": "recovered",
        },
    }
    assert _format_event(ev) is None
