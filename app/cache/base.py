"""Cache contract and no-op implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


def cache_key(route: str, carrier: str, dep_hour: int) -> str:
    """Canonical key for a repeat lookup: route + carrier + time-of-day."""
    return f"pred:{route}:{carrier}:{dep_hour}"


class AbstractCache(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[dict]:
        ...

    @abstractmethod
    def set(self, key: str, value: dict) -> None:
        ...

    def healthy(self) -> bool:
        return True


class NullCache(AbstractCache):
    """Used when no Redis URL is configured — every lookup misses."""

    def get(self, key: str) -> Optional[dict]:
        return None

    def set(self, key: str, value: dict) -> None:
        return None
