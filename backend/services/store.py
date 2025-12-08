import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from ..models import AuditLog, ConfigTemplate, DataSource, Run, RunStatus


class InMemoryStore:
    """Non-persistent store for demo purposes. Swap with DB in production."""

    def __init__(self) -> None:
        self.configs: dict[str, ConfigTemplate] = {}
        self.data_sources: dict[str, DataSource] = {}
        self.runs: dict[str, Run] = {}
        self.run_streams: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self.audit_logs: list[AuditLog] = []

    def create_config(
        self, name: str, config: dict[str, Any], description: Optional[str] = None, config_id: Optional[str] = None
    ) -> ConfigTemplate:
        now = datetime.utcnow()
        cfg = ConfigTemplate(
            id=config_id or uuid4().hex,
            name=name,
            description=description,
            config=config,
            created_at=now,
            updated_at=now,
        )
        self.configs[cfg.id] = cfg
        return cfg

    def update_config(self, config_id: str, payload: dict[str, Any]) -> ConfigTemplate:
        if config_id not in self.configs:
            raise KeyError(config_id)
        current = self.configs[config_id]
        updated = current.copy(update={**payload, "updated_at": datetime.utcnow()})
        self.configs[config_id] = updated
        return updated

    def delete_config(self, config_id: str) -> None:
        if config_id in self.configs:
            del self.configs[config_id]

    def create_data_source(
        self,
        name: str,
        source_type: str,
        path: Optional[str] = None,
        symbol: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DataSource:
        ds = DataSource(
            id=uuid4().hex,
            name=name,
            type=source_type,
            path=path,
            symbol=symbol,
            description=description,
            healthy=None,
            last_checked=None,
        )
        self.data_sources[ds.id] = ds
        return ds

    def update_data_source(self, source_id: str, payload: dict[str, Any]) -> DataSource:
        if source_id not in self.data_sources:
            raise KeyError(source_id)
        updated = self.data_sources[source_id].copy(update=payload)
        self.data_sources[source_id] = updated
        return updated

    def delete_data_source(self, source_id: str) -> None:
        if source_id in self.data_sources:
            del self.data_sources[source_id]

    def create_run(
        self, name: str, config: dict[str, Any], config_id: Optional[str] = None, status: RunStatus = RunStatus.pending
    ) -> Run:
        now = datetime.utcnow()
        run = Run(
            id=uuid4().hex,
            name=name,
            config=config,
            config_id=config_id,
            status=status,
            created_at=now,
            updated_at=now,
            progress=0.0,
            message=None,
            artifacts=[],
        )
        self.runs[run.id] = run
        self.run_streams[run.id] = asyncio.Queue()
        self._publish(run.id, {"type": "created", "run": run.model_dump()})
        return run

    def update_run(self, run_id: str, payload: dict[str, Any]) -> Run:
        if run_id not in self.runs:
            raise KeyError(run_id)
        updated = self.runs[run_id].copy(update={**payload, "updated_at": datetime.utcnow()})
        self.runs[run_id] = updated
        self._publish(run_id, {"type": "updated", "run": updated.model_dump()})
        return updated

    def get_run_queue(self, run_id: str) -> asyncio.Queue[dict[str, Any]] | None:
        return self.run_streams.get(run_id)

    def add_audit(self, actor: str, action: str, target: str, detail: Optional[str] = None) -> AuditLog:
        entry = AuditLog(
            id=uuid4().hex,
            actor=actor,
            action=action,
            target=target,
            detail=detail,
            timestamp=datetime.utcnow(),
        )
        self.audit_logs.append(entry)
        return entry

    def _publish(self, run_id: str, event: dict[str, Any]) -> None:
        queue = self.run_streams.get(run_id)
        if queue:
            queue.put_nowait(event)


store = InMemoryStore()
