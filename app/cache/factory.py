"""Cache selection: Redis when configured, otherwise a no-op cache."""
from __future__ import annotations

import logging

from app.cache.base import AbstractCache, NullCache
from app.cache.redis_cache import RedisCache
from app.config import settings

logger = logging.getLogger(__name__)


def build_cache() -> AbstractCache:
    if not settings.redis_url:
        logger.info("Using NullCache (no FDP_REDIS_URL configured).")
        return NullCache()
    logger.info("Using RedisCache (ttl=%ss).", settings.cache_ttl_seconds)
    return RedisCache(settings.redis_url, settings.cache_ttl_seconds)
