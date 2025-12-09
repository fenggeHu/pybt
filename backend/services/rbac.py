"""Role-based access control service and persistence layer."""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Iterable, Sequence

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Session, relationship

from ..models import Permission, Role, User
from .database import Base, SessionLocal

# Default permission and role definitions. New permissions/roles can be added via the service.
DEFAULT_PERMISSIONS: dict[str, str] = {
    "users.manage": "Manage users and roles",
    "configs.read": "Read configurations",
    "configs.write": "Create/update/delete configurations",
    "runs.read": "View runs",
    "runs.write": "Create/cancel runs",
    "data_sources.read": "Read data sources",
    "data_sources.write": "Create/update/delete/probe data sources",
    "audit.read": "View audit logs",
}

DEFAULT_ROLES: dict[str, dict[str, Iterable[str]]] = {
    "admin": {"permissions": tuple(DEFAULT_PERMISSIONS.keys()), "description": "Full access"},
    "user": {
        "permissions": (
            "configs.read",
            "runs.read",
            "runs.write",
            "data_sources.read",
        ),
        "description": "Standard user access",
    },
}

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    roles = relationship("RoleORM", secondary=user_roles, back_populates="users")


class RoleORM(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    description = Column(String(255), nullable=True)

    users = relationship("UserORM", secondary=user_roles, back_populates="roles")
    permissions = relationship("PermissionORM", secondary=role_permissions, back_populates="roles")


class PermissionORM(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("name", name="uq_permissions_name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=True)

    roles = relationship("RoleORM", secondary=role_permissions, back_populates="permissions")


class RBACService:
    """Encapsulates RBAC operations and hides ORM details from API layers."""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._session_factory = session_factory

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

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def _normalize_username(username: str) -> str:
        return username.strip()

    def _get_permissions_by_names(self, session: Session, names: Iterable[str]) -> list[PermissionORM]:
        wanted = set(names)
        if not wanted:
            return []
        perms = session.query(PermissionORM).filter(PermissionORM.name.in_(wanted)).all()
        found = {p.name for p in perms}
        missing = wanted - found
        if missing:
            raise ValueError(f"unknown permissions: {', '.join(sorted(missing))}")
        return perms

    def _get_roles_by_names(self, session: Session, names: Iterable[str]) -> list[RoleORM]:
        wanted = set(names)
        if not wanted:
            return []
        roles = session.query(RoleORM).filter(RoleORM.name.in_(wanted)).all()
        found = {r.name for r in roles}
        missing = wanted - found
        if missing:
            raise ValueError(f"unknown roles: {', '.join(sorted(missing))}")
        return roles

    def _to_user_model(self, user: UserORM) -> User:
        role_names = [role.name for role in user.roles]
        permissions = sorted({perm.name for role in user.roles for perm in role.permissions})
        primary_role = role_names[0] if role_names else "user"
        return User(
            username=user.username,
            role=primary_role,
            roles=role_names,
            permissions=permissions,
            active=user.is_active,
        )

    def _to_role_model(self, role: RoleORM) -> Role:
        perm_names = [perm.name for perm in role.permissions]
        return Role(name=role.name, description=role.description, permissions=perm_names)

    def _to_permission_model(self, perm: PermissionORM) -> Permission:
        return Permission(name=perm.name, description=perm.description)

    def ensure_seed_data(self, admin_password: str | None = None) -> None:
        """Create default roles/permissions and admin user if missing."""
        admin_password_env = os.environ.get("PYBT_ADMIN_PASSWORD")
        admin_password = admin_password or admin_password_env or "admin"
        admin_password_hash = self._hash_password(admin_password)
        with self._session_scope() as session:
            for name, description in DEFAULT_PERMISSIONS.items():
                existing = session.query(PermissionORM).filter(PermissionORM.name == name).one_or_none()
                if not existing:
                    session.add(PermissionORM(name=name, description=description))

            session.flush()

            for role_name, spec in DEFAULT_ROLES.items():
                role = session.query(RoleORM).filter(RoleORM.name == role_name).one_or_none()
                if not role:
                    role = RoleORM(name=role_name, description=spec.get("description"))
                    session.add(role)
                role.description = spec.get("description")
                role.permissions = self._get_permissions_by_names(session, spec.get("permissions", []))

            session.flush()

            admin_user = session.query(UserORM).filter(UserORM.username == "admin").one_or_none()
            if not admin_user:
                admin_user = UserORM(username="admin", password_hash=admin_password_hash, is_active=True)
                admin_user.roles = self._get_roles_by_names(session, ["admin"])
                session.add(admin_user)
            elif admin_password_env:
                # Allow overriding admin password via env when explicitly provided
                if admin_user.password_hash != admin_password_hash:
                    admin_user.password_hash = admin_password_hash

    def create_role(self, name: str, permissions: Sequence[str], description: str | None = None) -> Role:
        with self._session_scope() as session:
            existing = session.query(RoleORM).filter(RoleORM.name == name).one_or_none()
            if existing:
                raise ValueError("role already exists")
            role = RoleORM(name=name, description=description)
            role.permissions = self._get_permissions_by_names(session, permissions)
            session.add(role)
            session.flush()
            session.refresh(role)
            return self._to_role_model(role)

    def update_role_permissions(
        self, name: str, permissions: Sequence[str], description: str | None = None
    ) -> Role:
        with self._session_scope() as session:
            role = session.query(RoleORM).filter(RoleORM.name == name).one_or_none()
            if not role:
                raise ValueError("role not found")
            role.permissions = self._get_permissions_by_names(session, permissions)
            if description is not None:
                role.description = description
            session.flush()
            session.refresh(role)
            return self._to_role_model(role)

    def list_roles(self) -> list[Role]:
        with self._session_scope() as session:
            roles = session.query(RoleORM).all()
            return [self._to_role_model(role) for role in roles]

    def list_permissions(self) -> list[Permission]:
        with self._session_scope() as session:
            perms = session.query(PermissionORM).all()
            return [self._to_permission_model(perm) for perm in perms]

    def create_user(self, username: str, password: str, roles: Sequence[str] | None = None) -> User:
        username = self._normalize_username(username)
        if not username or not password:
            raise ValueError("username and password are required")
        with self._session_scope() as session:
            existing = session.query(UserORM).filter(UserORM.username == username).one_or_none()
            if existing:
                raise ValueError("user already exists")
            role_names = list(roles) if roles else ["user"]
            user = UserORM(username=username, password_hash=self._hash_password(password), is_active=True)
            user.roles = self._get_roles_by_names(session, role_names)
            session.add(user)
            session.flush()
            session.refresh(user)
            return self._to_user_model(user)

    def authenticate_user(self, username: str, password: str) -> User | None:
        username = self._normalize_username(username)
        if not username or not password:
            return None
        with self._session_scope() as session:
            user = session.query(UserORM).filter(UserORM.username == username).one_or_none()
            if not user or not user.is_active:
                return None
            if user.password_hash != self._hash_password(password):
                return None
            # Refresh relationships before leaving session context
            _ = user.roles  # noqa: F841
            return self._to_user_model(user)

    def get_user(self, username: str) -> User | None:
        username = self._normalize_username(username)
        with self._session_scope() as session:
            user = session.query(UserORM).filter(UserORM.username == username).one_or_none()
            if not user:
                return None
            _ = user.roles  # ensure roles are loaded
            return self._to_user_model(user)

    def list_users(self) -> list[User]:
        with self._session_scope() as session:
            users = session.query(UserORM).all()
            for u in users:
                _ = u.roles
            return [self._to_user_model(user) for user in users]

    def set_user_roles(self, username: str, roles: Sequence[str]) -> User:
        with self._session_scope() as session:
            user = session.query(UserORM).filter(UserORM.username == username).one_or_none()
            if not user:
                raise ValueError("user not found")
            user.roles = self._get_roles_by_names(session, roles)
            session.flush()
            session.refresh(user)
            _ = user.roles
            return self._to_user_model(user)


rbac_service = RBACService()
