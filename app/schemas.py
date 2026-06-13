"""Request/response schemas with validation."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FlightRequest(BaseModel):
    airline: str = Field(..., examples=["AA"], description="IATA carrier code")
    origin: str = Field(..., examples=["JFK"], description="IATA origin airport code")
    destination: str = Field(..., examples=["LAX"], description="IATA destination airport code")
    month: int = Field(..., ge=1, le=12, examples=[7])
    day_of_week: int = Field(..., ge=1, le=7, description="1=Mon .. 7=Sun", examples=[5])
    dep_hour: int = Field(..., ge=0, le=23, description="Scheduled departure hour, 0-23", examples=[18])

    @field_validator("airline", "origin", "destination")
    @classmethod
    def _upper(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("must not be empty")
        return v
