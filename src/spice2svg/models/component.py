"""电路元件模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

# SPICE 元件类型 → 引脚名称列表
PIN_DEFS: dict[str, list[str]] = {
    "R": ["1", "2"],
    "C": ["1", "2"],
    "L": ["1", "2"],
    "D": ["A", "K"],
    "V": ["+", "-"],
    "I": ["+", "-"],
    "Q": ["C", "B", "E"],
    "M": ["D", "G", "S", "B"],
    "J": ["D", "G", "S"],
    "E": ["+", "-", "C+", "C-"],
    "F": ["+", "-"],
    "G": ["+", "-", "C+", "C-"],
    "H": ["+", "-"],
    "B": ["+", "-"],
}

# 每种元件的最少节点数
MIN_PINS: dict[str, int] = {
    "R": 2, "C": 2, "L": 2, "D": 2, "V": 2, "I": 2,
    "Q": 3, "M": 4, "J": 3, "E": 4, "F": 2, "G": 4, "H": 2, "B": 2,
}


@dataclass
class Pin:
    """元件引脚。"""
    number: int
    name: str
    net_name: str = ""

    def __repr__(self) -> str:
        return f"Pin({self.number}, {self.name!r}, net={self.net_name!r})"


@dataclass
class Component:
    """电路元件。"""
    type: str           # "R", "C", "L", "D", "Q", "M", "V", "I", "X"
    ref: str            # "R1", "C2", "Q1"
    value: str = ""     # "10k", "100nF", "2N2222"
    pins: list[Pin] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def pin_by_number(self, num: int) -> Pin | None:
        for p in self.pins:
            if p.number == num:
                return p
        return None

    def net_names(self) -> list[str]:
        """返回此元件连接的所有网络名。"""
        return [p.net_name for p in self.pins]

    def __repr__(self) -> str:
        nets = ", ".join(p.net_name for p in self.pins)
        return f"Component({self.ref}: {self.type} = {self.value!r} [{nets}])"
