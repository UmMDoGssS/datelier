"""Explicit conversions to original, continuous pixel-edge boxes; never clamp."""

from math import isfinite

from datelier.inspection.annotations.types import BoxCoordinates, BoxRecord, PixelBox
from datelier.inspection.images.geometry import oriented_point


def pixel_box(record: BoxRecord, width: int, height: int) -> PixelBox:
    """Convert source boxes to continuous original-image pixel edges.

    VOC uses one-based inclusive extrema; COCO uses x/y/width/height; YOLO uses
    normalized center/size. Preserve out-of-bounds coordinates with diagnostics
    and reject nonfinite or nonpositive geometry.
    """

    if min(width, height) < 1:
        raise ValueError("Annotation conversion requires positive source dimensions")
    a, b, c, d = record.original
    if not all(isfinite(value) for value in record.original):
        raise ValueError("Box coordinates must be finite")
    match record.coordinates:
        case BoxCoordinates.VOC:
            if c < a or d < b:
                raise ValueError("VOC maxima must not precede minima")
            xyxy = a - 1, b - 1, c, d
        case BoxCoordinates.EDGES:
            xyxy = a, b, c, d
        case BoxCoordinates.COCO:
            xyxy = a, b, a + c, b + d
        case BoxCoordinates.YOLO:
            xyxy = (
                (a - c / 2) * width,
                (b - d / 2) * height,
                (a + c / 2) * width,
                (b + d / 2) * height,
            )
    x1, y1, x2, y2 = xyxy
    if not all(isfinite(value) for value in xyxy) or x1 >= x2 or y1 >= y2:
        raise ValueError("Box must have finite, positive width and height")
    diagnostics = list(record.diagnostics)
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        diagnostics.append(
            "Box extends outside the original image; coordinates retained"
        )
    if record.coordinates == BoxCoordinates.YOLO and any(
        value < 0 or value > 1 for value in record.original
    ):
        diagnostics.append("YOLO coordinates lie outside normalized 0–1 bounds")
    return PixelBox(record, xyxy, tuple(diagnostics))


def oriented_box(
    box: PixelBox, width: int, height: int, orientation: int
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box.xyxy
    corners = tuple(
        oriented_point(x, y, width, height, orientation)
        for x, y in ((x1, y1), (x1, y2), (x2, y1), (x2, y2))
    )
    xs, ys = zip(*corners, strict=True)
    return min(xs), min(ys), max(xs), max(ys)
