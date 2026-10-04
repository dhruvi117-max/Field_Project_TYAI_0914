# Evaluation and robustness plan

The SKU-110K test-split detector evaluation has now been completed; the
staged-shelf operational tests below still need physical ground truth and must
not be fabricated.

| Experiment | Procedure | Measure | Passing criterion |
| --- | --- | --- | --- |
| Baseline detector evaluation | Existing YOLO11n 20-epoch, 640 px run on SKU-110K test split | mAP50-95 0.5346; mAP50 0.8913; precision 0.8867; recall 0.8192; inference 5.057 ms/image | Completed 4 Oct 2026; one corrupt test image was skipped by Ultralytics |
| Restock logic | Create known planogram slots; remove one/two facings from staged shelf | Alert precision and recall | Correct alert for every below-minimum SKU; no alert for stock at/above minimum |
| Angle robustness | Capture front, 15° left and 15° right images | Detection count error by angle | State measured degradation and a practical camera-placement limit |
| Light robustness | Normal lighting and lower lighting | mAP proxy / manual count error | Document threshold or require retake where confidence drops |
| OCR failure | Blur/glare one label | False SKU assignment rate | Unreadable label is marked for review, never guessed |
| Security/privacy | Test oversize file, wrong type, missing API key when configured | HTTP response and logs | 413/415/401 as appropriate; no secret in repository |

For a small staged-shelf ground truth, calculate:

```text
count error = |observed facings - ground-truth facings|
restock precision = correct restock alerts / all restock alerts
restock recall = correct restock alerts / all real below-minimum cases
latency = audit completion time - upload submission time
```

