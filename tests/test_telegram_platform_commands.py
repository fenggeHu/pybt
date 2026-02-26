import asyncio

from apps.telegram_bot.telegram_bot import (
    _close_shared_http_client,
    _filter_runs_for_display,
    _format_compare_response,
    _help_lines,
    _format_plugins,
    _format_signal_items,
    _parse_runs_tokens,
    _shared_http_client_manager,
    _parse_filter_tokens,
    _parse_plugins_tokens,
    _program_help_text,
)


def test_parse_filter_tokens_supports_common_filters() -> None:
    out = _parse_filter_tokens(
        [
            "strategy_id=ma",
            "symbol=600000",
            "since_seq=10",
            "limit=30",
            "include_debug=true",
        ]
    )
    assert out == {
        "strategy_id": "ma",
        "symbol": "600000",
        "since_seq": 10,
        "limit": 30,
        "include_debug": True,
    }


def test_parse_filter_tokens_supports_debug_shortcuts() -> None:
    assert _parse_filter_tokens(["debug"])["include_debug"] is True
    assert _parse_filter_tokens(["nodebug"])["include_debug"] is False


def test_format_compare_response_contains_deltas() -> None:
    text = _format_compare_response(
        {
            "ok": True,
            "comparison": {
                "left_run_id": "r1",
                "right_run_id": "r2",
                "left_state": "completed",
                "right_state": "completed",
                "left_last_seq": 12,
                "right_last_seq": 18,
                "summary_delta": {"final_equity": 3000.0},
                "event_count_delta": {"NotificationIntentEvent": 2},
            },
        }
    )
    assert "Compare: r1 -> r2" in text
    assert "final_equity: 3000.0" in text
    assert "NotificationIntentEvent: 2" in text


def test_format_signal_items_handles_signal_and_debug_events() -> None:
    text = _format_signal_items(
        {
            "ok": True,
            "run_id": "r2",
            "last_seq": 20,
            "signals": [
                {
                    "seq": 11,
                    "event_type": "NotificationIntentEvent",
                    "strategy_id": "ma",
                    "symbol": "600000",
                    "direction": "LONG",
                    "strength": 1.0,
                    "message": "signal",
                },
                {
                    "seq": 12,
                    "event_type": "StrategyDebugEvent",
                    "strategy_id": "ma",
                    "symbol": "600000",
                    "stage": "hold",
                    "message": "no crossover",
                },
            ],
        }
    )
    assert "Run: r2" in text
    assert "SIGNAL seq=11" in text
    assert "DEBUG seq=12" in text


def test_parse_plugins_tokens_supports_shorthand_and_enabled() -> None:
    out = _parse_plugins_tokens(["strategy", "enabled=true"])
    assert out == {"kind": "strategy", "enabled": True}
    assert _parse_plugins_tokens(["on"]) == {"enabled": True}
    assert _parse_plugins_tokens(["off"]) == {"enabled": False}


def test_format_plugins_contains_status_lines() -> None:
    text = _format_plugins(
        {
            "ok": True,
            "registry_path": "/tmp/plugin.jsonc",
            "plugins": [
                {
                    "name": "moving_average",
                    "kind": "strategy",
                    "enabled": True,
                    "summary": "ma strategy",
                },
                {
                    "name": "sina_marketdata",
                    "kind": "data_feed",
                    "enabled": False,
                    "summary": "sina api",
                },
            ],
        }
    )
    assert "Registry: /tmp/plugin.jsonc" in text
    assert "[ON] strategy.moving_average" in text
    assert "[OFF] data_feed.sina_marketdata" in text


def test_program_help_text_contains_new_commands() -> None:
    text = _program_help_text()
    assert "/program_start <config_name>" in text
    assert "/program_stop <run_id>" in text
    assert "/plugins [kind=<kind>|<kind>] [enabled=true|false|on|off]" in text
    assert "/program_help" in text
    assert "/run_compare <left_run_id> <right_run_id>" not in text


def test_program_help_text_includes_draft_when_advanced(monkeypatch) -> None:
    monkeypatch.setenv("PYBT_BOT_ADVANCED", "1")
    text = _program_help_text()
    assert "/program_start <config_name|draft>" in text
    assert "/run_compare <left_run_id> <right_run_id>" in text


def test_help_lines_hides_draft_commands_by_default(monkeypatch) -> None:
    monkeypatch.delenv("PYBT_BOT_ADVANCED", raising=False)
    lines = _help_lines()
    joined = "\n".join(lines)
    assert "/run_draft" not in joined
    assert "/set_feed" not in joined


def test_help_lines_shows_draft_commands_when_advanced(monkeypatch) -> None:
    monkeypatch.setenv("PYBT_BOT_ADVANCED", "true")
    lines = _help_lines()
    joined = "\n".join(lines)
    assert "/run_draft" in joined
    assert "/set_feed" in joined


def test_shared_http_client_reused_between_calls() -> None:
    async def _run() -> None:
        async with _shared_http_client_manager() as c1:
            async with _shared_http_client_manager() as c2:
                assert c1 is c2
        await _close_shared_http_client()

    asyncio.run(_run())


def test_parse_runs_tokens_supports_state_and_limit() -> None:
    out = _parse_runs_tokens(["running", "limit=5"])
    assert out == {"state": "running", "limit": 5}
    assert _parse_runs_tokens(["all"]) == {"state": None}


def test_filter_runs_for_display_prioritizes_running_when_unfiltered() -> None:
    runs = [
        {"run_id": "a", "state": "completed", "started_at": "2026-01-01T00:00:00+00:00"},
        {"run_id": "b", "state": "running", "started_at": "2026-01-01T00:00:00+00:00"},
        {"run_id": "c", "state": "failed", "started_at": "2026-01-02T00:00:00+00:00"},
    ]
    out = _filter_runs_for_display(runs, state=None, limit=10)
    assert out[0]["run_id"] == "b"

    only_failed = _filter_runs_for_display(runs, state="failed", limit=10)
    assert len(only_failed) == 1
    assert only_failed[0]["run_id"] == "c"
