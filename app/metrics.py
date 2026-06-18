"""CloudWatch custom-metrics emitter.

Publishes application-level metrics (prediction latency, cache hits/misses,
active strategy) to a CloudWatch namespace. Disabled — a pure no-op — when
``FDP_CLOUDWATCH_NAMESPACE`` is empty or boto3 has no credentials, so it never
interferes with local runs or tests.

Metrics are buffered and flushed in small batches to limit PutMetricData calls.
"""
from __future__ import annotations

import logging
import threading
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

_FLUSH_THRESHOLD = 20


class CloudWatchMetrics:
    def __init__(self, namespace: str, region: str) -> None:
        self._namespace = namespace
        self._buffer: List[dict] = []
        self._lock = threading.Lock()
        self._client = None
        if namespace:
            try:
                import boto3

                self._client = boto3.client("cloudwatch", region_name=region)
            except Exception as exc:  # noqa: BLE001 - never fail app startup over metrics.
                logger.warning("CloudWatch metrics disabled (boto3 init failed): %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def record_prediction(self, latency_ms: float, cache_hit: bool, strategy: str) -> None:
        if not self.enabled:
            return
        dims = [{"Name": "Strategy", "Value": strategy}]
        self._put("PredictionLatency", latency_ms, "Milliseconds", dims)
        self._put("CacheHit", 1.0 if cache_hit else 0.0, "Count", dims)
        self._put("CacheMiss", 0.0 if cache_hit else 1.0, "Count", dims)

    def _put(self, name: str, value: float, unit: str, dimensions: list) -> None:
        datum = {"MetricName": name, "Value": value, "Unit": unit, "Dimensions": dimensions}
        with self._lock:
            self._buffer.append(datum)
            if len(self._buffer) >= _FLUSH_THRESHOLD:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer or self._client is None:
            return
        batch, self._buffer = self._buffer, []
        try:
            self._client.put_metric_data(Namespace=self._namespace, MetricData=batch)
        except Exception:  # noqa: BLE001
            logger.warning("CloudWatch PutMetricData failed for %d datapoints", len(batch),
                           exc_info=True)


metrics = CloudWatchMetrics(settings.cloudwatch_namespace, settings.aws_region)
