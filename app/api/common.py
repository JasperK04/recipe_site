from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ApiError(Exception):
    """Domain error raised by shared API helpers."""

    message: str
    status_code: int = 400
    payload: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message
