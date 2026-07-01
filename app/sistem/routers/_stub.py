"""Общая заглушка для Sprint 0 — все роутеры возвращают 501."""
from fastapi import HTTPException


def not_implemented(sprint: int) -> None:
    raise HTTPException(status_code=501, detail=f"Not implemented yet — landing in Sprint {sprint}")
