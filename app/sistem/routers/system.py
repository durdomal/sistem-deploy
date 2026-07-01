from fastapi import APIRouter

from sistem.routers._stub import not_implemented

router = APIRouter()


@router.post("/events")
def events():
    """Приём событий от бриджей / n8n. Sprint 1 — реальная логика."""
    not_implemented(sprint=1)
