"""Lazy YOLO + OCR inference. The app never invents detections when weights are missing."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from ..core import get_settings

LOGGER = logging.getLogger(__name__)


class ModelNotReadyError(RuntimeError):
    """Raised when an audit is requested before trained weights are available."""


@dataclass
class Detection:
    detection_id: str
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    resolved_sku: str | None = None
    resolution_source: str | None = None
    excluded: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["width"] = round(self.x2 - self.x1, 1)
        data["height"] = round(self.y2 - self.y1, 1)
        return data


class ShelfInferenceEngine:
    def __init__(self) -> None:
        self._model = None
        self._ocr_reader = None

    @property
    def weights_path(self) -> Path:
        return Path(get_settings().model_weights_path).expanduser().resolve()

    @property
    def is_ready(self) -> bool:
        return self.weights_path.is_file()

    def _load_model(self):
        if not self.is_ready:
            raise ModelNotReadyError(
                f"Model weights were not found at {self.weights_path}. "
                "Run the documented training command, then copy best.pt to models/shelf_yolo.pt."
            )
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as error:
                raise ModelNotReadyError("Ultralytics is not installed. Run pip install -r requirements.txt.") from error
            self._model = YOLO(str(self.weights_path))
        return self._model

    def _read_packaging_text(self, image, x1: int, y1: int, x2: int, y2: int) -> tuple[str | None, float | None]:
        """OCR is best-effort; a failed read leaves the detection unresolved for review."""
        crop = image[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
        if crop.size == 0:
            return None, None
        try:
            if self._ocr_reader is None:
                import easyocr

                self._ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            # paragraph=True can return strings rather than (box, text, score)
            # tuples in some EasyOCR versions. Keep individual results so the
            # confidence-aware catalogue matching has a stable contract.
            results = self._ocr_reader.readtext(crop, detail=1, paragraph=False)
            if not results:
                return None, None
            readable = [
                (str(result[1]).strip(), float(result[2]))
                for result in results
                if isinstance(result, (list, tuple)) and len(result) >= 3 and str(result[1]).strip()
            ]
            if not readable:
                return None, None
            text = " ".join(value for value, _ in readable[:4])
            confidence = max(score for _, score in readable)
            return text or None, round(confidence, 3)
        except Exception as error:  # OCR must not prevent a completed object-detection audit.
            LOGGER.warning("OCR failed for one crop: %s", error)
            return None, None

    def _predict_sync(self, image_path: Path) -> tuple[list[dict], int, int]:
        try:
            import cv2
        except ImportError as error:
            raise ModelNotReadyError("OpenCV is not installed. Run pip install -r requirements.txt.") from error

        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError("The uploaded file could not be decoded as an image.")
        image_height, image_width = image.shape[:2]
        result = self._load_model().predict(
            source=str(image_path),
            conf=get_settings().min_detection_confidence,
            verbose=False,
        )[0]
        names = result.names
        detections: list[dict] = []
        for box in result.boxes:
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            class_id = int(box.cls[0].item())
            label = str(names.get(class_id, class_id)) if isinstance(names, dict) else str(names[class_id])
            text, text_confidence = self._read_packaging_text(
                image, round(x1), round(y1), round(x2), round(y2)
            )
            detections.append(
                Detection(
                    detection_id=str(uuid.uuid4()),
                    label=label,
                    confidence=round(float(box.conf[0].item()), 3),
                    x1=round(x1, 1),
                    y1=round(y1, 1),
                    x2=round(x2, 1),
                    y2=round(y2, 1),
                    ocr_text=text,
                    ocr_confidence=text_confidence,
                ).to_dict()
            )
        return detections, image_width, image_height

    async def predict(self, image_path: Path) -> tuple[list[dict], int, int]:
        # Ultralytics and EasyOCR are synchronous and computationally expensive.
        return await asyncio.to_thread(self._predict_sync, image_path)

    @staticmethod
    def _render_annotated_image_sync(image_path: Path, detections: list[dict], output_path: Path) -> None:
        """Draw a transparent, presentation-friendly record of the actual model output."""
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError("The uploaded file could not be decoded for annotation.")
        image_height, image_width = image.shape[:2]
        line_width = max(1, round(min(image_height, image_width) / 900))
        font_scale = max(0.32, min(0.55, min(image_height, image_width) / 1800))
        for index, detection in enumerate(detections, start=1):
            confidence = float(detection["confidence"])
            # BGR colours: mint/high, amber/medium, rose/low confidence.
            color = (194, 231, 110) if confidence >= 0.75 else (131, 199, 255) if confidence >= 0.5 else (184, 145, 255)
            x1, y1, x2, y2 = (round(detection[key]) for key in ("x1", "y1", "x2", "y2"))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, line_width, cv2.LINE_AA)
            label = f"{index}  {confidence:.0%}"
            (label_width, label_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, line_width)
            label_y = max(label_height + baseline + 3, y1)
            cv2.rectangle(image, (x1, label_y - label_height - baseline - 5), (x1 + label_width + 7, label_y + 2), color, -1)
            cv2.putText(image, label, (x1 + 3, label_y - baseline - 1), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (24, 16, 47), line_width, cv2.LINE_AA)

        banner = f"AI shelf audit  |  {len(detections)} detected product facings"
        cv2.rectangle(image, (0, 0), (image_width, max(38, round(image_height * 0.045))), (24, 16, 47), -1)
        cv2.putText(image, banner, (14, max(25, round(image_height * 0.030))), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (246, 242, 255), 2, cv2.LINE_AA)
        if not cv2.imwrite(str(output_path), image):
            raise ValueError("The annotated audit image could not be saved.")

    async def render_annotated_image(self, image_path: Path, detections: list[dict], output_path: Path) -> None:
        """Keep image rendering off the API event loop, just like model inference."""
        await asyncio.to_thread(self._render_annotated_image_sync, image_path, detections, output_path)


inference_engine = ShelfInferenceEngine()
