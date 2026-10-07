"""Isolated PyYAML SafeLoader boundary with duplicate-key detection."""

from typing import cast

import yaml
from yaml.nodes import MappingNode


class UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[object, object]:
        self.flatten_mapping(node)
        result: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = cast(object, self.construct_object(key_node, deep=deep))
            if not isinstance(key, (str, int)):
                raise ValueError(
                    "Manifest YAML keys require strings or integer class IDs"
                )
            if key in result:
                raise ValueError(f"Duplicate YAML key {key!r}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def decode_manifest(text: str) -> object:
    try:
        return cast(object, yaml.load(text, Loader=UniqueSafeLoader))
    except yaml.YAMLError as error:
        raise ValueError(f"Cannot parse manifest YAML: {error}") from error
