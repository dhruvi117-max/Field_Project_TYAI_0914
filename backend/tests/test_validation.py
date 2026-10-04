from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from app.routers.api import validate_image_contents
from app.schemas import PlanogramIn


def valid_png(width: int = 12, height: int = 9) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_image_validation_returns_decoded_dimensions() -> None:
    assert validate_image_contents(valid_png()) == (12, 9)


def test_image_validation_rejects_non_image_bytes() -> None:
    with pytest.raises(HTTPException) as raised:
        validate_image_contents(b"not-an-image")
    assert raised.value.status_code == 415


def test_planogram_rejects_empty_slots() -> None:
    with pytest.raises(ValueError):
        PlanogramIn(store_id="demo", shelf_id="shelf", name="Invalid", slots=[])
