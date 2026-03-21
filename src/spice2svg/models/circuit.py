"""电路顶层容器模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .component import Component
from .net import Net, classify_net


@dataclass
class ModelDef:
    """SPICE .model 定义。"""
    name: str
    type: str  # NPN, PNP, NMOS, PMOS, D …
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class SubCircuit:
    """子电路定义。"""
    name: str
    ports: list[str] = field(default_factory=list)
    circuit: Circuit | None = None


@dataclass
class Circuit:
    """电路 IR 顶层容器。"""
    name: str = ""
    title: str = ""
    components: list[Component] = field(default_factory=list)
    nets: dict[str, Net] = field(default_factory=dict)
    subcircuits: list[SubCircuit] = field(default_factory=list)
    models: dict[str, ModelDef] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)

    # ---- 构建 ----

    def add_component(self, comp: Component) -> None:
        self.components.append(comp)

    def build_nets(self) -> None:
        """根据元件引脚信息构建 Net 对象。"""
        self.nets.clear()
        for comp in self.components:
            for pin in comp.pins:
                net_name = pin.net_name
                if net_name not in self.nets:
                    is_gnd, is_pwr, direction = classify_net(net_name)
                    self.nets[net_name] = Net(
                        name=net_name,
                        is_ground=is_gnd,
                        is_power=is_pwr,
                        direction=direction,
                    )
                self.nets[net_name].add_connection(comp.ref, pin.number)

    # ---- 查询 ----

    def get_component(self, ref: str) -> Component | None:
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    def get_net(self, name: str) -> Net | None:
        return self.nets.get(name)

    def ground_nets(self) -> list[Net]:
        return [n for n in self.nets.values() if n.is_ground]

    def power_nets(self) -> list[Net]:
        return [n for n in self.nets.values() if n.is_power]

    def port_nets(self) -> list[Net]:
        """返回应暴露为外部端口的网络。

        规则:
        1. 不是地网络
        2. 是边界网络（单连接），或名称匹配 input/output 模式
        """
        ports: list[Net] = []
        for net in self.nets.values():
            if net.is_ground:
                continue
            if net.is_boundary or net.direction in ("input", "output"):
                ports.append(net)
        return ports

    def component_types(self) -> set[str]:
        return {c.type for c in self.components}

    def validate(self) -> list[str]:
        """验证 IR，返回警告列表。"""
        warnings: list[str] = []
        for net in self.nets.values():
            if net.connection_count == 0:
                warnings.append(f"网络 {net.name!r} 没有任何连接")
            elif net.connection_count == 1 and not net.is_ground:
                warnings.append(f"网络 {net.name!r} 只有一个连接（悬空？）")
        for comp in self.components:
            if not comp.pins:
                warnings.append(f"元件 {comp.ref} 没有引脚定义")
        return warnings

    def summary(self) -> str:
        lines = [f"Circuit: {self.name or '(unnamed)'}"]
        if self.title:
            lines.append(f"  Title: {self.title}")
        lines.append(f"  Components: {len(self.components)}")
        lines.append(f"  Nets: {len(self.nets)}")
        if self.models:
            lines.append(f"  Models: {', '.join(self.models.keys())}")
        if self.subcircuits:
            lines.append(f"  Subcircuits: {', '.join(s.name for s in self.subcircuits)}")
        return "\n".join(lines)
