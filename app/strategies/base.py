"""Abstract prediction strategy contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas import FlightRequest


@dataclass(frozen=True)
class StrategyResult:
    """Raw model output: the probability plus provenance. The surrounding
    :class:`~app.services.model_service.ModelService` derives the threshold,
    risk band, and latency, so strategies stay focused on scoring."""

    delay_probability: float
    model_version: str
    warnings: list[str] = field(default_factory=list)


class PredictionStrategy(ABC):
    """A swappable scoring backend. Implementations: XGBoost (production) and a
    heuristic fallback."""

    #: Short, stable identifier surfaced in responses/metrics.
    name: str = "abstract"

    @abstractmethod
    def load(self) -> None:
        """Prepare the strategy for serving. Raise on unrecoverable failure."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether the strategy is ready to score requests."""

    @abstractmethod
    def predict(self, flight: FlightRequest) -> StrategyResult:
        """Score a single flight."""

    @property
    def metadata(self) -> dict:
        """Optional model metadata for GET /stats. Empty by default."""
        return {}
