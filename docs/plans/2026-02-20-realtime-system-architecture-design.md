# PyBT Realtime System Architecture Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete realtime-capable strategy runtime (market listening -> strategy execution -> Telegram push) while preserving the existing `pybt/core` engine skeleton and keeping all new components loosely coupled.

**Architecture:** Keep the current event-driven kernel as the stable core, and add a separate integration plane for realtime ingestion, strategy signal bridging, and notification delivery. All external integrations (feed providers, Telegram, future channels) must go through ports/adapters and event contracts, never directly into core strategy logic.

**Tech Stack:** Python 3.11+, existing `pybt` event bus/engine, optional `requests`/`websockets`/`adata`, FastAPI server app, Telegram Bot API.

---

## 1) Scope & Success Criteria

### 1.1 In Scope
- Realtime market data ingestion with reliability controls.
- Strategy execution on realtime data using existing core engine semantics.
- Telegram push for strategy outputs (not only fills/metrics).
- Extensible architecture for future channels (Slack/email/webhook) without changing core.

### 1.2 Out of Scope (for first implementation)
- Broker/order routing to real exchange.
- Multi-node distributed scheduling.
- Full CEP/stream processing platform.

### 1.3 Success Criteria
- System runs continuously with recoverable transient feed/network failures.
- Strategy signals are observable as first-class events and can be pushed to Telegram.
- Restart-safe notification delivery (no silent drops on process restart).
- `pybt/core` remains the engine kernel, not rewritten.

---

## 2) Non-Negotiable Design Principles

1. **Kernel Stability First**
   - `pybt/core` remains the domain kernel (event bus + engine + interfaces).
   - No Telegram/network-specific code in strategies or core interfaces.

2. **Ports & Adapters**
   - External dependencies are plugged through adapter interfaces.
   - Replacing provider (e.g., AData -> broker WS) requires adapter swap only.

3. **Event Contract as Boundary**
   - Inter-component communication uses typed event envelopes.
   - Event payload versioning is explicit.

4. **At-Least-Once + Idempotent Consumers**
   - Delivery is at-least-once by design.
   - Consumers enforce dedupe via idempotency keys.

5. **Observability by Default**
   - Every stage reports lag, retries, drops, and queue depth.

---

## 3) Current Foundation (Already in Repo)

- Core event-driven runtime: `pybt/core/engine.py`, `pybt/core/event_bus.py`, `pybt/core/interfaces.py`.
- Existing feeds: `pybt/data/rest_feed.py`, `pybt/data/websocket_feed.py`, `pybt/data/adata_feed.py`.
- Strategy abstraction and built-ins: `pybt/strategies/`.
- Server run orchestration and event stream: `apps/server/run_manager.py`, `apps/server/worker.py`, `apps/server/app.py`.
- Telegram app exists: `apps/telegram_bot/telegram_bot.py`.

Key gap today: worker/bot path is primarily centered around `FillEvent`/`MetricsEvent`; strategy output is not yet a first-class notification contract.

---

## 4) Target Architecture (Two-Plane Model)

## 4.1 Plane A: Core Plane (Stable Kernel)
- DataFeed -> Strategy -> Portfolio/Risk -> Execution -> Reporter
- Owned by current `pybt/core` and component packages.
- Keeps deterministic business processing semantics.

## 4.2 Plane B: Integration Plane (Realtime + Delivery)
- Market Listener Adapter Layer
- Strategy Signal Bridge
- Notification Outbox + Notifier Workers
- Delivery Adapters (Telegram first, future extensible)

### 4.3 High-Level Flow
```text
[Market Source]
   -> [Feed Adapter]
   -> [Core Event Bus / Engine]
   -> [SignalEvent + Fill/Metrics]
   -> [Event Bridge]
   -> [Notification Intent Outbox]
   -> [Telegram Notifier]
   -> [Telegram User/Channel]
```

---

## 5) Where Strategy Code Lives (Definitive Rule)

### 5.1 Built-in/Reference Strategies
- Keep in `pybt/strategies/`.
- Purpose: framework examples, defaults, test fixtures.

### 5.2 Business/Custom Strategies
- New top-level package: `strategies/` (repository root).
- Example:
  - `strategies/trend/my_strategy_v1.py`
  - `strategies/mean_reversion/my_mr_strategy.py`

### 5.3 Why this split
- Avoid coupling business alpha logic to framework internals.
- Allow framework upgrades without rewriting strategy modules.
- Keep clear ownership: framework team vs strategy team.

### 5.4 Contract rule
- Custom strategy classes implement the same `Strategy` interface from `pybt/core/interfaces.py`.
- Strategies emit domain signals only; they do not call Telegram or server APIs.

---

## 6) Module Design (New Additions)

Recommended new package:

```text
pybt/live/
  contracts.py                 # shared event envelope + schema version
  ingestion/
    market_listener.py         # source-agnostic listener orchestration
    adapters/
      rest_adapter.py
      websocket_adapter.py
      adata_adapter.py
  bridge/
    strategy_signal_bridge.py  # maps SignalEvent/FillEvent/MetricsEvent -> notification intents
  notify/
    outbox.py                  # durable queue / retry state
    notifier.py                # notifier orchestration port
    telegram_notifier.py       # Telegram adapter implementation
  runtime.py                   # assembly/bootstrap for live mode
```

### 6.1 `contracts.py`
- Define canonical envelope:
  - `event_id`, `run_id`, `seq`, `event_type`, `occurred_at`, `symbol`, `strategy_id`, `payload`, `schema_version`, `trace_id`.
- Define intent types:
  - `strategy_signal`, `fill_report`, `risk_alert`, `system_alert`.

### 6.2 `strategy_signal_bridge.py`
- Subscribes to core events.
- Converts strategy/fill/risk context into push-safe intent messages.
- Applies dedupe key generation (e.g., `run_id:strategy_id:symbol:ts:direction`).

### 6.3 `outbox.py`
- Durable persistence for unsent intents.
- States: `pending`, `sending`, `sent`, `failed`, `dead_letter`.
- Retry metadata: `attempt_count`, `next_retry_at`, `last_error`.

### 6.4 `telegram_notifier.py`
- Pulls from outbox, sends, updates status.
- Handles rate limits and retries with backoff.
- Supports template rendering by intent type.

---

## 7) Event Contracts & Semantics

## 7.1 Event Types
- `MarketEvent` (core)
- `SignalEvent` (core)
- `OrderEvent` (core)
- `FillEvent` (core)
- `MetricsEvent` (core)
- `NotificationIntentEvent` (integration plane)

### 7.2 Delivery Semantics
- Ingestion: at-least-once.
- Bridge: idempotent mapping to intents.
- Notifier: at-least-once to Telegram, dedupe in-domain by `event_id`/dedupe key.

### 7.3 Ordering
- Preserve per-symbol ordering where strategy depends on sequence.
- Use sequence in envelope for replay and debugging.

---

## 8) Configuration Design

Extend current configuration loader without breaking existing config shape.

### 8.1 Strategy Loading (Backward-Compatible)

Support both:
- Built-in style (existing):
```json
{ "type": "moving_average", "symbol": "AAA", "short_window": 5, "long_window": 20 }
```
- Plugin style (new):
```json
{
  "type": "plugin",
  "class_path": "strategies.trend.my_strategy_v1.MyStrategy",
  "params": { "symbol": "AAA", "window": 34 }
}
```

### 8.2 Notification Section (new)
```json
{
  "notifications": {
    "enabled": true,
    "channels": [
      {
        "type": "telegram",
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id": "-100123456",
        "min_level": "signal"
      }
    ],
    "dedupe_ttl_sec": 300
  }
}
```

---

## 9) Reliability & Failure Handling

### 9.1 Feed Reliability
- Exponential reconnect backoff.
- Heartbeat timeout and reconnect.
- Duplicate tick detection.
- Gap detection emits system alert intent.

### 9.2 Runtime Safety
- Circuit breaker for repeated feed failures.
- Kill switch to pause notifications if strategy state is inconsistent.
- Safe degradation mode: stop notification flood during unstable data periods.

### 9.3 Notification Reliability
- Outbox persists before send.
- Retry with bounded backoff.
- Dead-letter store after max retries.

---

## 10) Observability

Emit metrics/logs for:
- feed_lag_ms
- reconnect_count
- dedupe_drop_count
- signal_to_intent_latency_ms
- outbox_pending_count
- notify_success_rate / notify_failure_rate
- telegram_429_count

Add correlation IDs (`trace_id`) from ingestion through notification for troubleshooting.

---

## 11) Security & Ops Notes

- Keep secrets in env vars only (`TELEGRAM_BOT_TOKEN`, API keys).
- Log redaction for tokens/chat IDs.
- Add health endpoints for listener/notifier status.
- Store outbox and audit logs under managed base directory (e.g., `~/.pybt/live/`).

---

## 12) Testing Strategy

### 12.1 Unit Tests
- Strategy plugin loading by `class_path`.
- Signal bridge mapping and dedupe key stability.
- Outbox state transitions.

### 12.2 Integration Tests
- Simulated market stream -> strategy -> intent -> notifier mock.
- Restart test: pending outbox messages recovered and delivered.

### 12.3 Fault Injection Tests
- WebSocket disconnect/reconnect loops.
- Duplicate/out-of-order market messages.
- Telegram 429 and timeout retries.

### 12.4 Replay Tests
- Record event stream and replay to verify deterministic strategy signal generation.

---

## 13) Phased Delivery Plan

### Phase 0: Contract Freeze (Architecture-Only)
- Finalize envelope schema and module boundaries.
- Define acceptance checklist and SLO baselines.

### Phase 1: Strategy Extensibility
- Add plugin strategy loading (`class_path`) with backward compatibility.
- Add tests for built-in + plugin mixed configs.

### Phase 2: Strategy Signal Bridge
- Bridge `SignalEvent` into `NotificationIntentEvent`.
- Extend worker/server event exposure as needed.

### Phase 3: Durable Notification Pipeline
- Implement outbox + retry worker + Telegram adapter.
- Add delivery idempotency and dead-letter behavior.

### Phase 4: Realtime Hardening
- Gap detection, heartbeats, resilience metrics, alerting.
- Add fault injection and replay test suite.

### Phase 5: Production Rollout
- Canary with one symbol + one strategy.
- Expand to multi-strategy after SLO stabilization.

---

## 14) Acceptance Checklist

- [ ] Core kernel files remain architecture-stable; no external coupling added.
- [ ] Strategy code location is split: `pybt/strategies/` (built-in), `strategies/` (business).
- [ ] New strategy can be added via config only (no core file modification).
- [ ] Signal events can be delivered to Telegram via outbox pipeline.
- [ ] Restart does not drop pending notifications.
- [ ] Reconnect/429 paths are tested and observable.

---

## 15) Recommended First PR Slice

1. Add strategy plugin loading (`class_path`) + tests.
2. Introduce `pybt/live/contracts.py` and bridge skeleton.
3. Wire `SignalEvent` -> notification intent path (no Telegram send yet).
4. Add outbox persistence and notifier interface.
5. Add Telegram adapter and end-to-end integration tests.

This ordering gives fast validation of architecture boundaries before heavier runtime hardening.
