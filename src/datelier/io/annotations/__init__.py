"""Local VOC, YOLO, COCO, and Ultralytics annotation adapters.

Readers preserve source coordinates, classes, confidence, and diagnostics.
Association with file/view row IDs is separate and explicit. Manifest paths are
resolved locally; download/training directives are never executed. YOLO's
optional confidence column requires an explicit setting.
"""

from datelier.io.annotations.loading import load_annotations as load_annotations
