from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models import DataSource, User
from ..services import store
from ..services.auth import get_current_user

router = APIRouter(tags=["data_sources"])


class DataSourceCreate(BaseModel):
    name: str
    type: str
    path: str | None = None
    symbol: str | None = None
    description: str | None = None


@router.get("/data-sources", response_model=list[DataSource])
async def list_data_sources(user: User = Depends(get_current_user)) -> list[DataSource]:
    return list(store.data_sources.values())


@router.post("/data-sources", response_model=DataSource)
async def create_data_source(payload: DataSourceCreate, user: User = Depends(get_current_user)) -> DataSource:
    ds = store.create_data_source(
        name=payload.name,
        source_type=payload.type,
        path=payload.path,
        symbol=payload.symbol,
        description=payload.description,
    )
    store.add_audit(actor=user.username, action="create_data_source", target=ds.id)
    return ds


@router.get("/data-sources/{source_id}", response_model=DataSource)
async def get_data_source(source_id: str, user: User = Depends(get_current_user)) -> DataSource:
    ds = store.data_sources.get(source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="data source not found")
    return ds


@router.put("/data-sources/{source_id}", response_model=DataSource)
async def update_data_source(source_id: str, payload: dict[str, Any], user: User = Depends(get_current_user)) -> DataSource:
    try:
        ds = store.update_data_source(source_id, payload)
        store.add_audit(actor=user.username, action="update_data_source", target=source_id)
        return ds
    except KeyError:
        raise HTTPException(status_code=404, detail="data source not found")


@router.delete("/data-sources/{source_id}")
async def delete_data_source(source_id: str, user: User = Depends(get_current_user)) -> dict[str, str]:
    store.delete_data_source(source_id)
    store.add_audit(actor=user.username, action="delete_data_source", target=source_id)
    return {"status": "deleted"}


@router.post("/data-sources/{source_id}/probe", response_model=DataSource)
async def probe_data_source(source_id: str, user: User = Depends(get_current_user)) -> DataSource:
    ds = store.data_sources.get(source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="data source not found")

    if ds.path:
        path_exists = Path(ds.path).exists()
        ds = store.update_data_source(
            source_id,
            {
                "healthy": path_exists,
            },
        )
    else:
        ds = store.update_data_source(source_id, {"healthy": True})
    store.add_audit(actor=user.username, action="probe_data_source", target=source_id, detail=str(ds.healthy))
    return ds
