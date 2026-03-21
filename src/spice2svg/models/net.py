"""网络（节点）模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

# 常见地节点名
GROUND_NAMES = {"0", "gnd", "gnd!", "vss", "vss!"}
# 常见电源节点名
POWER_NAMES = {"vcc", "vdd", "vee", "v+", "v-", "vdd!", "vcc!"}


@dataclass
class NetConnection:
    """网络上的一个连接点。"""
    component_ref: str
    pin_num: int

    def __repr__(self) -> str:
        return f"{self.component_ref}.{self.pin_num}"


@dataclass
class Net:
    """电路网络 / 节点。"""
    name: str
    connections: list[NetConnection] = field(default_factory=list)
    is_ground: bool = False
    is_power: bool = False
    direction: str = "inout"  # "input" | "output" | "inout"

    @property
    def connection_count(self) -> int:
        return len(self.connections)

    @property
    def is_boundary(self) -> bool:
        """只连接到一个元件引脚的网络。"""
        return self.connection_count <= 1

    def add_connection(self, component_ref: str, pin_num: int) -> None:
        self.connections.append(NetConnection(component_ref, pin_num))

    def __repr__(self) -> str:
        conns = ", ".join(str(c) for c in self.connections)
        return f"Net({self.name!r} [{conns}])"


def classify_net(name: str) -> tuple[bool, bool, str]:
    """根据网络名推断类型和方向。

    Returns:
        (is_ground, is_power, direction)
    """
    lower = name.lower()

    if lower in GROUND_NAMES:
        return True, False, "inout"

    if lower in POWER_NAMES:
        return False, True, "input"

    # 名称启发式
    if any(kw in lower for kw in ("in", "clk", "clock", "rst", "reset", "en", "enable")):
        return False, False, "input"

    if any(kw in lower for kw in ("out",)):
        return False, False, "output"

    return False, False, "inout"
