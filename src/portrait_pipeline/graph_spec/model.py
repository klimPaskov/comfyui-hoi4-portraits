from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Link:
    node_id: int
    slot: int = 0


@dataclass
class NodeSpec:
    node_id: int
    class_type: str
    group: str
    title: str
    inputs: dict[str, Any] = field(default_factory=dict)
    input_types: dict[str, str] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    output_types: list[str] = field(default_factory=list)
    pos: tuple[int, int] = (0, 0)
    size: tuple[int, int] = (260, 120)
    widgets: list[Any] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)


@dataclass
class GraphSpec:
    workflow_id: str
    profile: str
    nodes: list[NodeSpec]
    groups: list[str]
    metadata: dict[str, Any]

    def node(self, node_id: int) -> NodeSpec:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

