"""超节点模式定义的核心数据结构。

每种可识别的电路模式 (差分对、电流镜 …) 用 PatternDef 声明式定义:
  - 角色 (Role): 模式中的元件槽位
  - 约束 (Constraint): 引脚间的连接/不连接/电源要求
  - 外部端口 (ExternalPort): 超节点暴露给外部的连接点
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# 引脚引用
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PinRef:
    """引用某个角色 (role) 的某个引脚。

    Attributes:
        role_id: 角色 ID (与 Role.id 对应)
        pin_index: 引脚索引, 0-based, 按 SPICE 引脚顺序
                   例如 BJT: 0=C, 1=B, 2=E; MOSFET: 0=D, 1=G, 2=S, 3=B
    """
    role_id: str
    pin_index: int


# ---------------------------------------------------------------------------
# 约束类型
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SameNet:
    """两个引脚必须连到同一个网络。"""
    a: PinRef
    b: PinRef


@dataclass(frozen=True)
class DiffNet:
    """两个引脚必须连到不同的网络。"""
    a: PinRef
    b: PinRef


@dataclass(frozen=True)
class NetIs:
    """某引脚必须连到特定类型的电源/地网络。"""
    pin: PinRef
    kind: Literal["ground", "pos_supply", "neg_supply", "any_power"]


@dataclass(frozen=True)
class NetIsNot:
    """某引脚必须 *不* 连到特定类型的电源/地网络。"""
    pin: PinRef
    kind: Literal["ground", "pos_supply", "neg_supply", "any_power"]


# 所有约束类型的联合
Constraint = SameNet | DiffNet | NetIs | NetIsNot


# ---------------------------------------------------------------------------
# 角色
# ---------------------------------------------------------------------------

@dataclass
class Role:
    """模式中的元件槽位。

    Attributes:
        id: 在模式内唯一的标识符, 例如 "QL", "QR", "ITAIL"
        comp_type: 要求的 SPICE 元件类型 ("Q", "M", "R", "C", "I", ...)
        polarity: 可选的极性要求 ("NPN", "PNP", "NMOS", "PMOS")
        optional: 如果为 True, 即使找不到匹配元件, 模式仍可成立
    """
    id: str
    comp_type: str
    polarity: str | None = None
    optional: bool = False


# ---------------------------------------------------------------------------
# 外部端口
# ---------------------------------------------------------------------------

@dataclass
class ExternalPort:
    """超节点暴露给外部电路的一个端口。

    Attributes:
        name: 端口名, 例如 "INP", "INN", "OUTP", "OUTN", "TAIL"
        source: 该端口来自哪个角色的哪个引脚
        direction: ELK 布局方向 ("input" / "output" / "inout")
    """
    name: str
    source: PinRef
    direction: str = "inout"


# ---------------------------------------------------------------------------
# 模式定义
# ---------------------------------------------------------------------------

@dataclass
class PatternDef:
    """一种可识别电路模式的完整声明。

    Attributes:
        name: 模式唯一标识, 例如 "diff_pair_npn"
        display_name: 可读名称, 例如 "NPN 差分对"
        description: 描述文字
        roles: 组成模式的元件角色列表
        constraints: 所有约束 (连接、不连接、电源)
        external_ports: 暴露给外部的端口列表
        skin_type: 用于 netlistsvg 渲染的 skin 类型名
        priority: 匹配优先级 (越大越优先, 相同优先级按角色数降序)
    """
    name: str
    display_name: str
    description: str
    roles: list[Role]
    constraints: list[Constraint]
    external_ports: list[ExternalPort]
    skin_type: str
    priority: int = 0


# ---------------------------------------------------------------------------
# 便捷构造
# ---------------------------------------------------------------------------

def pin(role_id: str, pin_index: int) -> PinRef:
    """快速创建 PinRef 的缩写。"""
    return PinRef(role_id, pin_index)
