"""Model entry point (compatibility shim).

The model logic now lives behind the Strategy pattern in ``app/strategies`` and
is orchestrated by :class:`~app.services.model_service.ModelService`. This module
keeps the historical ``app.model.model`` singleton and ``ModelNotLoadedError``
import path stable for the API and tests.
"""
from __future__ import annotations

from app.services.model_service import ModelService
from app.strategies.errors import ModelNotLoadedError

# Process-wide singleton shared across requests (loaded once at startup).
model = ModelService()

__all__ = ["model", "ModelService", "ModelNotLoadedError"]
