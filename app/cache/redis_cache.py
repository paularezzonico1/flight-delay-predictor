"""Redis-backed cache.

Caches the prediction response for a (route, carrier, time-of-day) key with a
TTL. Backed by a Redis container running on the EC2 instance (not managed
ElastiCache — see README) to keep ongoing cost down. All Redis errors are
swallowed: the cache is an optimisation, never a hard dependency.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import redis

from app.cache.base import AbstractCache
from app.config import settings

logger = logging.getLogger(__name__)


class RedisCache(AbstractCache):
    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[dict]:
        try:
            raw = self._client.get(key)
        except redis.RedisError:
            logger.warning("Redis GET failed for %s", key, exc_info=True)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: dict) -> None:
        try:
            self._client.set(key, json.dumps(value), ex=self._ttl)
        except redis.RedisError:
            logger.warning("Redis SET failed for %s", key, exc_info=True)

    def healthy(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False
