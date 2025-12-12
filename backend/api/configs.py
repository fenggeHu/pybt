from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models import ConfigTemplate, ValidationResult, User
from ..services import store, validate_config_payload
from ..services.auth import require_permission

router = APIRouter(tags=["configs"])


class ConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict[str, Any]


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class ConfigValidationRequest(BaseModel):
    config: dict[str, Any]


@router.get("/configs", response_model=list[ConfigTemplate])
async def list_configs(user: User = Depends(require_permission("configs.read"))) -> list[ConfigTemplate]:
    return store.list_configs()


@router.post("/configs", response_model=ConfigTemplate)
async def create_config(payload: ConfigCreate, user: User = Depends(require_permission("configs.write"))) -> ConfigTemplate:
    cfg = store.create_config(name=payload.name, description=payload.description, config=payload.config)
    store.add_audit(actor=user.username, action="create_config", target=cfg.id)
    return cfg


@router.get("/configs/{config_id}", response_model=ConfigTemplate)
async def get_config(config_id: str, user: User = Depends(require_permission("configs.read"))) -> ConfigTemplate:
    cfg = store.get_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="config not found")
    return cfg


@router.put("/configs/{config_id}", response_model=ConfigTemplate)
async def update_config(
    config_id: str, payload: ConfigUpdate, user: User = Depends(require_permission("configs.write"))
) -> ConfigTemplate:
    try:
        update_payload = payload.model_dump(exclude_none=True)
        cfg = store.update_config(config_id, update_payload)
        store.add_audit(actor=user.username, action="update_config", target=config_id)
        return cfg
    except KeyError:
        raise HTTPException(status_code=404, detail="config not found")


@router.delete("/configs/{config_id}")
async def delete_config(config_id: str, user: User = Depends(require_permission("configs.write"))) -> dict[str, str]:
    store.delete_config(config_id)
    store.add_audit(actor=user.username, action="delete_config", target=config_id)
    return {"status": "deleted"}


@router.post("/configs/{config_id}/clone", response_model=ConfigTemplate)
async def clone_config(config_id: str, user: User = Depends(require_permission("configs.write"))) -> ConfigTemplate:
    cfg = store.get_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="config not found")
    cloned = store.create_config(
        name=f"{cfg.name} (copy)",
        description=cfg.description,
        config=cfg.config,
    )
    store.add_audit(actor=user.username, action="clone_config", target=config_id)
    return cloned


@router.post("/configs/validate", response_model=ValidationResult)
async def validate_config(
    payload: ConfigValidationRequest, user: User = Depends(require_permission("configs.read"))
) -> ValidationResult:
    return validate_config_payload(payload.config)
