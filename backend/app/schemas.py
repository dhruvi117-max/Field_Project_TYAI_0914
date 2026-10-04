"""Request and response contracts. These are shown automatically in /docs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=80, examples=["COLA-500-ML"])
    name: str = Field(min_length=1, max_length=120, examples=["Cola 500 ml"])
    ocr_aliases: list[str] = Field(default_factory=list, description="Words likely to appear on packaging")
    image_url: HttpUrl | None = None


class PlanogramSlot(BaseModel):
    row: int = Field(ge=1, le=30)
    sku: str
    expected_facings: int = Field(ge=0, le=100)
    minimum_facings: int = Field(ge=0, le=100)
    position_hint: str | None = Field(default=None, max_length=120)


class PlanogramIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=80)
    shelf_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    slots: list[PlanogramSlot] = Field(min_length=1, max_length=300)


class OverrideIn(BaseModel):
    detection_id: str
    corrected_sku: str | None = None
    action: Literal["confirm", "correct", "remove"]
    reason: str = Field(min_length=3, max_length=300)
    reviewer: str = Field(min_length=2, max_length=80)


class AlertActionIn(BaseModel):
    action: Literal["acknowledge", "resolve"]
    actor: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=300)


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["connected", "disconnected"]
    model_ready: bool
    timestamp: datetime

