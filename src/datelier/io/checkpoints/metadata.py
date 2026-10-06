"""Preserve primitive hierarchy and tensor headers without loading tensor storage."""

from collections.abc import Mapping
from typing import cast

from datelier.inspection.checkpoints.types import TensorInfo
from datelier.inspection.objects.types import (
    NodePath,
    ObjectChild,
    ObjectNode,
    node_label,
)
from datelier.io.checkpoints.runtime import TensorValue, require_torch


def checkpoint_tree(
    value: object, *, max_nodes: int = 200_000, max_depth: int = 128
) -> tuple[ObjectNode, tuple[TensorInfo, ...]]:
    runtime = require_torch()
    tensors: list[TensorInfo] = []
    ancestors: dict[int, NodePath] = {}
    nodes = 0

    def visit(value: object, path: NodePath) -> ObjectNode:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes or len(path) > max_depth:
            raise ValueError(
                "Checkpoint metadata exceeds its configured node/depth limits"
            )
        if runtime.is_tensor(value):
            tensor = cast(TensorValue, value)
            shape = tuple(tensor.shape)
            dtype, layout = str(tensor.dtype), str(tensor.layout)
            dense = layout == "torch.strided" and not tensor.is_quantized
            info = TensorInfo(
                path,
                node_label(path),
                shape,
                dtype,
                layout,
                tuple(tensor.stride()) if dense else (),
                tensor.storage_offset() if dense else 0,
                tensor.element_size() * _size(shape),
                "" if dense else "This tensor layout is available as metadata only.",
            )
            tensors.append(info)
            return ObjectNode("tensor", f"{shape} · {dtype} · {layout}")
        if value is None or isinstance(value, (str, int, float, bool, bytes)):
            return ObjectNode(type(value).__name__, value)
        if id(value) in ancestors:
            return ObjectNode("reference", node_label(ancestors[id(value)]))
        ancestors[id(value)] = path
        try:
            if isinstance(value, Mapping):
                mapped = cast(Mapping[object, object], value)
                if any(type(key) not in (str, int) for key in mapped):
                    raise ValueError(
                        "Checkpoint dictionary keys must be strings or integers"
                    )
                return ObjectNode(
                    "object",
                    children=tuple(
                        ObjectChild(key, visit(item, (*path, key)))
                        for key, item in cast(
                            Mapping[str | int, object], mapped
                        ).items()
                    ),
                )
            if isinstance(value, (list, tuple)):
                return ObjectNode(
                    "array",
                    children=tuple(
                        ObjectChild(i, visit(item, (*path, i)))
                        for i, item in enumerate(
                            cast(list[object] | tuple[object, ...], value)
                        )
                    ),
                )
            raise ValueError(
                f"Unsupported checkpoint metadata type: {type(value).__name__}"
            )
        finally:
            ancestors.pop(id(value))

    return visit(value, ()), tuple(tensors)


def _size(shape: tuple[int, ...]) -> int:
    result = 1
    for size in shape:
        result *= size
    return result
