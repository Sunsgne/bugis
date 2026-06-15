"""SDN / vendor fabric controller CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.controller import Controller
from app.models.enums import ControllerType
from app.models.user import User
from app.schemas.controller import (
    ControllerCreate,
    ControllerOut,
    ControllerUpdate,
)

router = APIRouter()


@router.get("", response_model=list[ControllerOut])
def list_controllers(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return db.execute(select(Controller).order_by(Controller.id)).scalars().all()


@router.post("", response_model=ControllerOut, status_code=201)
def create_controller(
    payload: ControllerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    if payload.type == ControllerType.BUGIS:
        raise HTTPException(
            status_code=400,
            detail="Bugis SDN 控制器为平台内置组件，启动时自动注册，无需手动添加",
        )
    controller = Controller(**payload.model_dump())
    db.add(controller)
    db.commit()
    db.refresh(controller)
    return controller


@router.patch("/{controller_id}", response_model=ControllerOut)
def update_controller(
    controller_id: int,
    payload: ControllerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    controller = db.get(Controller, controller_id)
    if not controller:
        raise HTTPException(status_code=404, detail="controller not found")
    if controller.type == ControllerType.BUGIS:
        raise HTTPException(
            status_code=400,
            detail="内置 Bugis SDN 控制器不可修改",
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(controller, k, v)
    db.commit()
    db.refresh(controller)
    return controller


@router.delete("/{controller_id}", status_code=204)
def delete_controller(
    controller_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    controller = db.get(Controller, controller_id)
    if not controller:
        raise HTTPException(status_code=404, detail="controller not found")
    if controller.type == ControllerType.BUGIS:
        raise HTTPException(
            status_code=400,
            detail="内置 Bugis SDN 控制器不可删除",
        )
    db.delete(controller)
    db.commit()
