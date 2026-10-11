"""Public io annotations readers API."""

from datelier.io.annotations.readers.coco import read_coco as read_coco
from datelier.io.annotations.readers.ultralytics import (
    read_ultralytics as read_ultralytics,
)
from datelier.io.annotations.readers.voc import read_voc as read_voc
from datelier.io.annotations.readers.yolo import read_yolo as read_yolo
