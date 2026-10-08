"""Request and response contracts. These are shown automatically in /docs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProductIn(BaseModel):
    # The UI deliberately hides this technical key.  The API accepts it for
    # backwards compatibility, but generates one from the product name when absent.
    sku: str | None = Field(default=None, min_length=1, max_length=80, examples=["COLA-500-ML"])
    name: str = Field(min_length=1, max_length=120, examples=["Cola 500 ml"])
    ocr_aliases: list[str] = Field(default_factory=list, description="Words likely to appear on packaging")
    image_url: HttpUrl | None = None


class PlanogramSlot(BaseModel):
    row: int = Field(ge=1, le=30)
    # Product name is what a store user sees. sku remains an internal stable key
    # so old planograms and audit evidence continue to work.
    product_name: str | None = Field(default=None, min_length=1, max_length=120)
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    expected_facings: int = Field(ge=0, le=100)
    minimum_facings: int = Field(ge=0, le=100)


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
