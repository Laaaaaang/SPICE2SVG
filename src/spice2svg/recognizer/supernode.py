"""超节点数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SuperNode:
    """被识别出的电路构建块 (超节点)。

    一个超节点包含若干原始元件, 内部连接关系固定,
    仅通过 external_ports 与外部电路交互。

    Attributes:
        pattern_name: 匹配的模式名, 例如 "diff_pair_npn"
        skin_type: 用于 JSON cell.type, 对应 skin SVG 条目
        display_name: 可读名称
        ref: 自动生成的引用名, 例如 "DP_1"
        component_refs: 包含的原始元件 ref 列表
        external_ports: 端口名 → (网络名, ELK方向)
        internal_nets: 仅在超节点内部使用的网络名集合 (不暴露给外部)
        role_mapping: 角色ID → 元件ref (用于调试)
    """
    pattern_name: str
    skin_type: str
    display_name: str
    ref: str
    component_refs: list[str]
    external_ports: dict[str, tuple[str, str]]   # port_name → (net_name, direction)
    internal_nets: set[str] = field(default_factory=set)
    role_mapping: dict[str, str] = field(default_factory=dict)  # role_id → comp_ref

    @property
    def component_count(self) -> int:
        return len(self.component_refs)

    def is_member(self, ref: str) -> bool:
        """判断某元件是否属于此超节点。"""
        return ref in self.component_refs

    def port_net(self, port_name: str) -> str | None:
        """根据端口名获取网络名。"""
        entry = self.external_ports.get(port_name)
        return entry[0] if entry else None

    def __repr__(self) -> str:
        members = ", ".join(self.component_refs)
        ports = ", ".join(f"{k}={v[0]}" for k, v in self.external_ports.items())
        return f"SuperNode({self.ref}: {self.pattern_name} [{members}] ports=[{ports}])"
