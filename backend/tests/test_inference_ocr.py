import numpy as np

from app.services.inference import ShelfInferenceEngine


class FakeReader:
    def readtext(self, _crop, detail, paragraph):
        assert detail == 1
        assert paragraph is False
        return [([], "Rin", 0.91), ([], "Detergent", 0.72)]


def test_ocr_reader_uses_stable_tuple_results() -> None:
    engine = ShelfInferenceEngine()
    engine._ocr_reader = FakeReader()
    image = np.zeros((40, 40, 3), dtype=np.uint8)

    text, confidence = engine._read_packaging_text(image, 0, 0, 40, 40)

    assert text == "Rin Detergent"
    assert confidence == 0.91
