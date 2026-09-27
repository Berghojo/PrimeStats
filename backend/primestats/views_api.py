"""Gespeicherte Ansichten: welche Panels ein Konto auf den Scouting-Seiten sehen will."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from .deps import CurrentUser, Service
from .schemas import ViewIn, ViewOut, ViewUpdate

router = APIRouter(prefix="/api/me/views")

#: Obergrenze je Konto
MAX_VIEWS = 20
KIND = "scout"


@router.get("", response_model=list[ViewOut])
def list_views(service: Service, user: CurrentUser):
    return service.store.list_views(user.id, KIND)


@router.post("", response_model=ViewOut, status_code=status.HTTP_201_CREATED)
def create_view(body: ViewIn, service: Service, user: CurrentUser):
    if len(service.store.list_views(user.id, KIND)) >= MAX_VIEWS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_VIEWS} Ansichten – bitte eine löschen.")
    return service.store.create_view(user.id, KIND, body.name, list(dict.fromkeys(body.panels)), body.is_default)


@router.patch("/{view_id}", response_model=ViewOut)
def update_view(view_id: int, body: ViewUpdate, service: Service, user: CurrentUser):
    panels = list(dict.fromkeys(body.panels)) if body.panels is not None else None
    view = service.store.update_view(user.id, view_id, name=body.name, panels=panels, is_default=body.is_default)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ansicht nicht gefunden.")
    return view


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_view(view_id: int, service: Service, user: CurrentUser):
    if not service.store.delete_view(user.id, view_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ansicht nicht gefunden.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
