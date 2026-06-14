"""Notification channel CRUD & test endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_operator
from app.core.database import get_db
from app.models.notification import NotificationChannel
from app.models.user import User
from app.schemas.notification import ChannelCreate, ChannelOut, ChannelUpdate
from app.services import notify

router = APIRouter()


@router.get("", response_model=list[ChannelOut])
def list_channels(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(
        select(NotificationChannel).order_by(NotificationChannel.id)
    ).scalars().all()


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    channel = NotificationChannel(**payload.model_dump())
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    channel = db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="channel not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(channel, k, v)
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    channel = db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="channel not found")
    db.delete(channel)
    db.commit()


@router.post("/{channel_id}/test")
def test_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_operator),
):
    channel = db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="channel not found")
    result = notify.test_channel(db, channel)
    db.commit()
    return result
