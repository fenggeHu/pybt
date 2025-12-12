import asyncio
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import AuditLog, ConfigTemplate, DataSource, Run, RunStatus
from .database import SessionLocal
from .persistence_models import AuditLogORM, ConfigORM, DataSourceORM, RunORM


class PersistentStore:
    """Persistent store backed by SQLAlchemy."""

    def __init__(self) -> None:
        self._session_factory = SessionLocal
        # Run streams are ephemeral and live in memory
        self.run_streams: dict[str, asyncio.Queue[dict[str, Any]]] = {}

    @contextmanager
    def _session_scope(self) -> Iterable[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Helpers ---

    def _to_config_model(self, orm: ConfigORM) -> ConfigTemplate:
        return ConfigTemplate(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            config=orm.config,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def _to_data_source_model(self, orm: DataSourceORM) -> DataSource:
        return DataSource(
            id=orm.id,
            name=orm.name,
            type=orm.type,
            path=orm.path,
            symbol=orm.symbol,
            description=orm.description,
            healthy=orm.healthy,
            last_checked=orm.last_checked,
        )

    def _to_run_model(self, orm: RunORM) -> Run:
        return Run(
            id=orm.id,
            name=orm.name,
            config=orm.config,
            config_id=orm.config_id,
            status=RunStatus(orm.status),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            progress=orm.progress,
            message=orm.message,
            artifacts=orm.artifacts or [],
        )

    def _to_audit_model(self, orm: AuditLogORM) -> AuditLog:
        return AuditLog(
            id=orm.id,
            actor=orm.actor,
            action=orm.action,
            target=orm.target,
            detail=orm.detail,
            timestamp=orm.timestamp,
        )

    # --- Configs ---

    def list_configs(self) -> list[ConfigTemplate]:
        with self._session_scope() as session:
            rows = session.query(ConfigORM).order_by(ConfigORM.updated_at.desc()).all()
            return [self._to_config_model(r) for r in rows]

    def get_config(self, config_id: str) -> ConfigTemplate | None:
        with self._session_scope() as session:
            row = session.query(ConfigORM).filter(ConfigORM.id == config_id).one_or_none()
            return self._to_config_model(row) if row else None

    def create_config(
        self, name: str, config: dict[str, Any], description: Optional[str] = None, config_id: Optional[str] = None
    ) -> ConfigTemplate:
        with self._session_scope() as session:
            row = ConfigORM(
                id=config_id or uuid4().hex,
                name=name,
                description=description,
                config=config,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return self._to_config_model(row)

    def update_config(self, config_id: str, payload: dict[str, Any]) -> ConfigTemplate:
        with self._session_scope() as session:
            row = session.query(ConfigORM).filter(ConfigORM.id == config_id).one_or_none()
            if not row:
                raise KeyError(config_id)
            
            for key, value in payload.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            # updated_at handled by onupdate
            session.flush()
            session.refresh(row)
            return self._to_config_model(row)

    def delete_config(self, config_id: str) -> None:
        with self._session_scope() as session:
            session.query(ConfigORM).filter(ConfigORM.id == config_id).delete()

    # --- Data Sources ---

    def list_data_sources(self) -> list[DataSource]:
        with self._session_scope() as session:
            rows = session.query(DataSourceORM).order_by(DataSourceORM.name).all()
            return [self._to_data_source_model(r) for r in rows]

    def get_data_source(self, source_id: str) -> DataSource | None:
        with self._session_scope() as session:
            row = session.query(DataSourceORM).filter(DataSourceORM.id == source_id).one_or_none()
            return self._to_data_source_model(row) if row else None

    def create_data_source(
        self,
        name: str,
        source_type: str,
        path: Optional[str] = None,
        symbol: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DataSource:
        with self._session_scope() as session:
            row = DataSourceORM(
                id=uuid4().hex,
                name=name,
                type=source_type,
                path=path,
                symbol=symbol,
                description=description,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return self._to_data_source_model(row)

    def update_data_source(self, source_id: str, payload: dict[str, Any]) -> DataSource:
        with self._session_scope() as session:
            row = session.query(DataSourceORM).filter(DataSourceORM.id == source_id).one_or_none()
            if not row:
                raise KeyError(source_id)
            
            for key, value in payload.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            
            session.flush()
            session.refresh(row)
            return self._to_data_source_model(row)

    def delete_data_source(self, source_id: str) -> None:
        with self._session_scope() as session:
            session.query(DataSourceORM).filter(DataSourceORM.id == source_id).delete()

    # --- Runs ---

    def list_runs(self) -> list[Run]:
        with self._session_scope() as session:
            rows = session.query(RunORM).order_by(RunORM.created_at.desc()).all()
            return [self._to_run_model(r) for r in rows]

    def get_run(self, run_id: str) -> Run | None:
        with self._session_scope() as session:
            row = session.query(RunORM).filter(RunORM.id == run_id).one_or_none()
            return self._to_run_model(row) if row else None

    def create_run(
        self, name: str, config: dict[str, Any], config_id: Optional[str] = None, status: RunStatus = RunStatus.pending
    ) -> Run:
        with self._session_scope() as session:
            row = RunORM(
                id=uuid4().hex,
                name=name,
                config=config,
                config_id=config_id,
                status=status.value,
                progress=0.0,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            
            run_model = self._to_run_model(row)
            
        self.run_streams[run_model.id] = asyncio.Queue()
        self._publish(run_model.id, {"type": "created", "run": run_model.model_dump()})
        return run_model

    def update_run(self, run_id: str, payload: dict[str, Any]) -> Run:
        with self._session_scope() as session:
            row = session.query(RunORM).filter(RunORM.id == run_id).one_or_none()
            if not row:
                raise KeyError(run_id)
            
            for key, value in payload.items():
                if key == "status" and isinstance(value, RunStatus):
                    value = value.value
                if hasattr(row, key):
                    setattr(row, key, value)
            
            session.flush()
            session.refresh(row)
            run_model = self._to_run_model(row)

        self._publish(run_id, {"type": "updated", "run": run_model.model_dump()})
        return run_model

    def get_run_queue(self, run_id: str) -> asyncio.Queue[dict[str, Any]] | None:
        return self.run_streams.get(run_id)

    # --- Audit ---

    def list_audit_logs(self, limit: int = 200) -> list[AuditLog]:
        with self._session_scope() as session:
            rows = session.query(AuditLogORM).order_by(AuditLogORM.timestamp.desc()).limit(limit).all()
            return [self._to_audit_model(r) for r in rows]

    def add_audit(self, actor: str, action: str, target: str, detail: Optional[str] = None) -> AuditLog:
        with self._session_scope() as session:
            row = AuditLogORM(
                id=uuid4().hex,
                actor=actor,
                action=action,
                target=target,
                detail=detail,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return self._to_audit_model(row)

    def _publish(self, run_id: str, event: dict[str, Any]) -> None:
        queue = self.run_streams.get(run_id)
        if queue:
            queue.put_nowait(event)


store = PersistentStore()
