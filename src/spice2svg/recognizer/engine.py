"""模式匹配引擎 — 基于约束的子图同构搜索。

对于每个 PatternDef, 引擎尝试将其角色 (Role) 分配给电路中的实际元件,
检查所有约束是否满足, 若满足则创建 SuperNode。

算法:
  1. 按优先级排序模式 (大优先级 → 多角色 → 先匹配)
  2. 对每个模式, 按角色逐一尝试候选元件 (回溯搜索)
  3. 每一步做早期约束剪枝
  4. 已分配给某个超节点的元件不再参与后续匹配 (贪心)
"""

from __future__ import annotations

from ..models import Circuit
from ..models.component import Component
from .pattern_def import (
    PatternDef, Role, Constraint, PinRef,
    SameNet, DiffNet, NetIs, NetIsNot,
)
from .supernode import SuperNode


# ---------------------------------------------------------------------------
# 电源网络分类 (与 json_converter 保持一致)
# ---------------------------------------------------------------------------

_GROUND_NAMES = {"0", "gnd", "gnd!", "vss", "vss!", "ground"}
_POS_SUPPLY_NAMES = {"vcc", "vdd", "vcc!", "vdd!", "v+", "avdd", "dvdd"}
_NEG_SUPPLY_NAMES = {"vee", "vee!", "v-", "avss", "dvss"}


def _classify_power(net_name: str) -> str | None:
    """返回 'ground' / 'pos_supply' / 'neg_supply' / None。"""
    lower = net_name.lower()
    if lower in _GROUND_NAMES:
        return "ground"
    if lower in _POS_SUPPLY_NAMES:
        return "pos_supply"
    if lower in _NEG_SUPPLY_NAMES:
        return "neg_supply"
    return None


def _is_any_power(net_name: str) -> bool:
    return _classify_power(net_name) is not None


# ---------------------------------------------------------------------------
# 极性匹配
# ---------------------------------------------------------------------------

def _matches_polarity(comp: Component, polarity: str, circuit: Circuit) -> bool:
    """检查元件是否满足极性要求。"""
    pol_upper = polarity.upper()

    # 优先查 .model 定义
    model = circuit.models.get(comp.value)
    if model:
        mtype = model.type.upper()
        if pol_upper in mtype:
            return True
        # 检查互斥极性
        opposites = {
            "NPN": ("PNP",), "PNP": ("NPN",),
            "NMOS": ("PMOS", "PFET"), "PMOS": ("NMOS", "NFET"),
        }
        for opp in opposites.get(pol_upper, ()):
            if opp in mtype:
                return False

    # 回退到 value 字符串
    val = (comp.value or "").upper()
    if pol_upper in val:
        return True
    opp_map = {
        "NPN": ["PNP"], "PNP": ["NPN"],
        "NMOS": ["PMOS", "PFET"], "PMOS": ["NMOS", "NFET"],
    }
    for opp in opp_map.get(pol_upper, []):
        if opp in val:
            return False

    # 默认: Q→NPN, M→NMOS
    defaults = {"Q": "NPN", "M": "NMOS"}
    return pol_upper == defaults.get(comp.type, "")


# ---------------------------------------------------------------------------
# 从 PinRef 获取网络名
# ---------------------------------------------------------------------------

def _get_net(pin_ref: PinRef, assignment: dict[str, Component]) -> str | None:
    """从角色分配中获取引脚对应的网络名。"""
    comp = assignment.get(pin_ref.role_id)
    if comp is None:
        return None
    if pin_ref.pin_index >= len(comp.pins):
        return None
    return comp.pins[pin_ref.pin_index].net_name


# ---------------------------------------------------------------------------
# 单个约束检查
# ---------------------------------------------------------------------------

def _check_constraint(
    constraint: Constraint,
    assignment: dict[str, Component],
) -> bool | None:
    """检查约束是否满足。

    Returns:
        True  — 满足
        False — 违反
        None  — 涉及的角色尚未分配, 无法判断
    """
    if isinstance(constraint, SameNet):
        net_a = _get_net(constraint.a, assignment)
        net_b = _get_net(constraint.b, assignment)
        if net_a is None or net_b is None:
            return None
        return net_a == net_b

    elif isinstance(constraint, DiffNet):
        net_a = _get_net(constraint.a, assignment)
        net_b = _get_net(constraint.b, assignment)
        if net_a is None or net_b is None:
            return None
        return net_a != net_b

    elif isinstance(constraint, NetIs):
        net = _get_net(constraint.pin, assignment)
        if net is None:
            return None
        pwr = _classify_power(net)
        if constraint.kind == "any_power":
            return pwr is not None
        return pwr == constraint.kind

    elif isinstance(constraint, NetIsNot):
        net = _get_net(constraint.pin, assignment)
        if net is None:
            return None
        pwr = _classify_power(net)
        if constraint.kind == "any_power":
            return pwr is None
        return pwr != constraint.kind

    return True


# ---------------------------------------------------------------------------
# 回溯搜索
# ---------------------------------------------------------------------------

def _find_matches(
    circuit: Circuit,
    pattern: PatternDef,
    used: set[str],
) -> list[dict[str, Component]]:
    """找到模式在电路中的所有有效匹配。

    使用回溯搜索 + 早期约束剪枝。对于小模式 (2-6 元件) 效率很高。
    """
    # 构建每个角色的候选列表
    required_roles: list[Role] = []
    optional_roles: list[Role] = []
    candidates: dict[str, list[Component]] = {}

    for role in pattern.roles:
        cands = []
        for comp in circuit.components:
            if comp.ref in used:
                continue
            if comp.type != role.comp_type:
                continue
            if role.polarity and not _matches_polarity(comp, role.polarity, circuit):
                continue
            # 确保引脚数足够 (至少满足模式中引用到的最大引脚索引)
            max_pin = _max_pin_index_for_role(role.id, pattern)
            if max_pin is not None and len(comp.pins) <= max_pin:
                continue
            cands.append(comp)

        candidates[role.id] = cands
        if role.optional:
            optional_roles.append(role)
        else:
            if not cands:
                return []  # 必需角色无候选 → 模式不可能匹配
            required_roles.append(role)

    # 按候选数从少到多排序 (MRV 启发式, 减少搜索空间)
    required_roles.sort(key=lambda r: len(candidates[r.id]))
    all_roles = required_roles + optional_roles

    results: list[dict[str, Component]] = []
    assignment: dict[str, Component] = {}
    assigned_refs: set[str] = set()

    # 预分组: 哪些约束涉及哪些角色
    constraints_by_role: dict[str, list[Constraint]] = {}
    for c in pattern.constraints:
        involved = _constraint_roles(c)
        for r in involved:
            constraints_by_role.setdefault(r, []).append(c)

    def _early_check() -> bool:
        """检查当前已分配角色涉及的所有约束。"""
        checked: set[int] = set()
        for role_id in assignment:
            for c in constraints_by_role.get(role_id, []):
                c_id = id(c)
                if c_id in checked:
                    continue
                checked.add(c_id)
                result = _check_constraint(c, assignment)
                if result is False:
                    return False
        return True

    def backtrack(idx: int) -> None:
        if idx == len(all_roles):
            # 所有角色已分配, 最终检查
            if _early_check():
                results.append(dict(assignment))
            return

        role = all_roles[idx]
        cands = candidates.get(role.id, [])

        for comp in cands:
            if comp.ref in assigned_refs:
                continue
            assignment[role.id] = comp
            assigned_refs.add(comp.ref)

            if _early_check():
                backtrack(idx + 1)

            del assignment[role.id]
            assigned_refs.discard(comp.ref)

        # 可选角色: 也尝试不填
        if role.optional:
            backtrack(idx + 1)

    backtrack(0)
    return results


def _max_pin_index_for_role(role_id: str, pattern: PatternDef) -> int | None:
    """找到模式中对某角色引用到的最大引脚索引。"""
    max_idx: int | None = None
    for c in pattern.constraints:
        for pr in _constraint_pin_refs(c):
            if pr.role_id == role_id:
                if max_idx is None or pr.pin_index > max_idx:
                    max_idx = pr.pin_index
    for p in pattern.external_ports:
        if p.source.role_id == role_id:
            if max_idx is None or p.source.pin_index > max_idx:
                max_idx = p.source.pin_index
    return max_idx


def _constraint_roles(c: Constraint) -> set[str]:
    """返回约束涉及的角色 ID 集合。"""
    if isinstance(c, (SameNet, DiffNet)):
        return {c.a.role_id, c.b.role_id}
    elif isinstance(c, (NetIs, NetIsNot)):
        return {c.pin.role_id}
    return set()


def _constraint_pin_refs(c: Constraint) -> list[PinRef]:
    """返回约束涉及的所有 PinRef。"""
    if isinstance(c, (SameNet, DiffNet)):
        return [c.a, c.b]
    elif isinstance(c, (NetIs, NetIsNot)):
        return [c.pin]
    return []


# ---------------------------------------------------------------------------
# 内部/外部网络分类
# ---------------------------------------------------------------------------

def _classify_nets(
    match: dict[str, Component],
    pattern: PatternDef,
    circuit: Circuit,
    supernode_refs: set[str],
) -> tuple[dict[str, tuple[str, str]], set[str]]:
    """区分超节点的外部端口和内部网络。

    Returns:
        (external_ports, internal_nets):
            external_ports: 端口名 → (网络名, 方向)
            internal_nets: 纯内部网络名集合
    """
    # 1. 根据模式定义获取命名的外部端口
    ext_ports: dict[str, tuple[str, str]] = {}
    ext_net_names: set[str] = set()

    for port in pattern.external_ports:
        comp = match.get(port.source.role_id)
        if comp and port.source.pin_index < len(comp.pins):
            net_name = comp.pins[port.source.pin_index].net_name
            ext_ports[port.name] = (net_name, port.direction)
            ext_net_names.add(net_name)

    # 2. 收集超节点成员的所有网络
    all_nets: set[str] = set()
    for comp in match.values():
        for pin_obj in comp.pins:
            all_nets.add(pin_obj.net_name)

    # 3. 找出与外部元件共享的网络 (未在命名端口中但连接了外部元件)
    auto_port_idx = 0
    for net_name in all_nets:
        if net_name in ext_net_names:
            continue
        # 检查此网络是否连接了超节点外部的元件
        net = circuit.nets.get(net_name)
        if net:
            has_external = any(
                conn.component_ref not in supernode_refs
                for conn in net.connections
            )
            if has_external or _is_any_power(net_name):
                # 自动暴露为端口
                auto_port_idx += 1
                port_name = f"_AUTO_{net_name}"
                direction = "input" if _is_any_power(net_name) else "inout"
                ext_ports[port_name] = (net_name, direction)
                ext_net_names.add(net_name)

    # 4. 剩余的就是纯内部网络
    internal = all_nets - ext_net_names

    return ext_ports, internal


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def recognize_supernodes(
    circuit: Circuit,
    patterns: list[PatternDef],
    *,
    greedy: bool = True,
) -> list[SuperNode]:
    """在电路中识别所有可匹配的超节点。

    Args:
        circuit: 输入电路 IR
        patterns: 模式定义列表
        greedy: 贪心模式 (已匹配的元件不再参与后续匹配)

    Returns:
        识别出的超节点列表
    """
    # 按优先级降序、角色数降序排序 (大模式/高优先级先匹配)
    sorted_patterns = sorted(
        patterns,
        key=lambda p: (-p.priority, -len(p.roles)),
    )

    used: set[str] = set()
    supernodes: list[SuperNode] = []
    counters: dict[str, int] = {}

    for pattern in sorted_patterns:
        matches = _find_matches(circuit, pattern, used)

        for match in matches:
            # 检查是否有元件已被使用 (可能被同批次的其他匹配占用)
            match_refs = {comp.ref for comp in match.values()}
            if greedy and match_refs & used:
                continue

            # 分类网络
            ext_ports, internal_nets = _classify_nets(
                match, pattern, circuit, match_refs,
            )

            # 生成引用名 (按缩写计数, 避免不同模式名但相同缩写冲突)
            abbr = _abbreviate(pattern.name)
            counters[abbr] = counters.get(abbr, 0) + 1
            ref = f"{abbr}_{counters[abbr]}"

            sn = SuperNode(
                pattern_name=pattern.name,
                skin_type=pattern.skin_type,
                display_name=pattern.display_name,
                ref=ref,
                component_refs=sorted(match_refs),
                external_ports=ext_ports,
                internal_nets=internal_nets,
                role_mapping={role_id: comp.ref for role_id, comp in match.items()},
            )
            supernodes.append(sn)

            if greedy:
                used.update(match_refs)

    return supernodes


def _abbreviate(name: str) -> str:
    """从模式名生成缩写, 如 'diff_pair_npn' → 'DP'。"""
    _abbr = {
        "diff_pair_npn": "DP", "diff_pair_pnp": "DP",
        "diff_pair_nmos": "DP", "diff_pair_pmos": "DP",
        "current_mirror_npn": "CM", "current_mirror_pnp": "CM",
        "current_mirror_nmos": "CM", "current_mirror_pmos": "CM",
        "cascode_npn": "CAS", "cascode_pnp": "CAS",
        "cascode_nmos": "CAS", "cascode_pmos": "CAS",
        "darlington_npn": "DRL", "darlington_pnp": "DRL",
        "sziklai_pair": "SZK",
        "vbe_multiplier": "VBE",
        "push_pull_bjt": "PP", "push_pull_mos": "PP",
        "diff_pair_active_load_npn": "DPAL",
        "diff_pair_active_load_pnp": "DPAL",
        "wilson_mirror_npn": "WM", "wilson_mirror_pnp": "WM",
        "cross_coupled_npn": "XC", "cross_coupled_pnp": "XC",
        "cross_coupled_nmos": "XC", "cross_coupled_pmos": "XC",
    }
    return _abbr.get(name, name.upper()[:3])
