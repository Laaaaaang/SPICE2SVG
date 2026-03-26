"""将 Circuit IR 转换为 netlistsvg analog 风格 JSON。

核心改进:
  - DOWN 布局: 命名引脚 (A/B, C/B/E, D/G/S, +/-)，与 analog skin 对应
  - RIGHT 布局: 信号从左往右流, 统一 port_directions 使各级正确分层
  - 电源符号: VCC/GND/VEE 作为独立单引脚 cell，每个连接点拆为独立实例
  - 有源器件极性: 自动检测 NPN/PNP, NMOS/PMOS
  - MOS body 引脚: 连到电源/地时隐式处理（不显示第 4 脚）
  - 电源电压源: VCC/VDD/VEE/VSS 电压源不画为器件
  - 差分对/电流镜对称: 自动检测并镜像布局
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..models import Circuit
from ..models.component import Component

# ---------------------------------------------------------------------------
# 引脚映射: SPICE pin number → skin pin name
# ---------------------------------------------------------------------------
_PIN_MAP: dict[str, dict[int, str]] = {
    "R":      {1: "A",  2: "B"},
    "C":      {1: "A",  2: "B"},
    "L":      {1: "A",  2: "B"},
    "V":      {1: "+",  2: "-"},
    "I":      {1: "+",  2: "-"},
    "D":      {1: "A",  2: "K"},
    "Q_NPN":  {1: "C",  2: "B",  3: "E"},
    "Q_PNP":  {1: "C",  2: "B",  3: "E"},
    "M_NMOS": {1: "D",  2: "G",  3: "S"},   # body(4) 隐式处理
    "M_PMOS": {1: "D",  2: "G",  3: "S"},
    "J":      {1: "D",  2: "G",  3: "S"},
    "E":      {1: "+",  2: "-",  3: "C+", 4: "C-"},
    "F":      {1: "+",  2: "-"},
    "G":      {1: "+",  2: "-",  3: "C+", 4: "C-"},
    "H":      {1: "+",  2: "-"},
    "B":      {1: "+",  2: "-"},
}

# skin 别名类型
_SKIN_TYPE: dict[str, str] = {
    "R":      "r_v",
    "C":      "c_v",
    "L":      "l_v",
    "V":      "v",
    "I":      "i",
    "D":      "d_v",
    "Q_NPN":  "q_npn",
    "Q_PNP":  "q_pnp",
    "M_NMOS": "nmos",
    "M_PMOS": "pmos",
    "B":      "v",        # 行为源共享电压源符号
    "J":      "nmos",     # JFET 共享 NMOS 符号
    # JFET 镜像
    "J_M":    "nmos_m",
    "J_ML":   "nmos_ml",
    # 镜像 (gate/base 在右侧)
    "Q_NPN_M":  "q_npn_m",
    "Q_PNP_M":  "q_pnp_m",
    "M_NMOS_M": "nmos_m",
    "M_PMOS_M": "pmos_m",
    # 镜像对左侧 (图形同普通, gate/base 非 lateral)
    "Q_NPN_ML":  "q_npn_ml",
    "Q_PNP_ML":  "q_pnp_ml",
    "M_NMOS_ML": "nmos_ml",
    "M_PMOS_ML": "pmos_ml",
    # 差分对右侧 (base/gate 在右, 无 s:dir 覆盖, 不干扰 ELK 排列)
    "Q_NPN_DFR":  "q_npn_dfr",
    "Q_PNP_DFR":  "q_pnp_dfr",
    "M_NMOS_DFR": "nmos_dfr",
    "M_PMOS_DFR": "pmos_dfr",
}

# ELK 端口方向 (DOWN 布局: "input"→上层, "output"→下层)
_PORT_DIR: dict[str, dict[str, str]] = {
    "R":      {"A": "input",  "B": "output"},
    "C":      {"A": "input",  "B": "output"},
    "L":      {"A": "input",  "B": "output"},
    "V":      {"+": "input",  "-": "output"},
    "I":      {"+": "input",  "-": "output"},
    "D":      {"A": "input",  "K": "output"},
    "Q_NPN":  {"C": "input",  "B": "input",  "E": "output"},
    "Q_PNP":  {"C": "output", "B": "input",  "E": "input"},
    "M_NMOS": {"D": "input",  "G": "input",  "S": "output"},
    "M_PMOS": {"D": "output", "G": "input",  "S": "input"},
    "B":      {"+": "input",  "-": "output"},
    "J":      {"D": "input",  "G": "input",  "S": "output"},
    # JFET 镜像
    "J_M":    {"D": "input",  "G": "input",  "S": "output"},
    "J_ML":   {"D": "input",  "G": "input",  "S": "output"},
    "E":      {"+": "input",  "-": "output", "C+": "input", "C-": "input"},
    "F":      {"+": "input",  "-": "output"},
    "G":      {"+": "input",  "-": "output", "C+": "input", "C-": "input"},
    "H":      {"+": "input",  "-": "output"},
    # 镜像型 — 端口方向不变（ELK 仍用 input/output 判断层级）
    "Q_NPN_M":  {"C": "input",  "B": "input",  "E": "output"},
    "Q_PNP_M":  {"C": "output", "B": "input",  "E": "input"},
    "M_NMOS_M": {"D": "input",  "G": "input",  "S": "output"},
    "M_PMOS_M": {"D": "output", "G": "input",  "S": "input"},
    # 镜像对左侧 — 端口方向同普通
    "Q_NPN_ML":  {"C": "input",  "B": "input",  "E": "output"},
    "Q_PNP_ML":  {"C": "output", "B": "input",  "E": "input"},
    "M_NMOS_ML": {"D": "input",  "G": "input",  "S": "output"},
    "M_PMOS_ML": {"D": "output", "G": "input",  "S": "input"},
    # 差分对右侧 — 端口方向同普通
    "Q_NPN_DFR":  {"C": "input",  "B": "input",  "E": "output"},
    "Q_PNP_DFR":  {"C": "output", "B": "input",  "E": "input"},
    "M_NMOS_DFR": {"D": "input",  "G": "input",  "S": "output"},
    "M_PMOS_DFR": {"D": "output", "G": "input",  "S": "input"},
}

# ---------------------------------------------------------------------------
# 电源网络名匹配
# ---------------------------------------------------------------------------
_GROUND_NAMES = {"0", "gnd", "gnd!", "vss", "vss!", "ground"}
_POS_SUPPLY_NAMES = {"vcc", "vdd", "vcc!", "vdd!", "v+", "avdd", "dvdd"}
_NEG_SUPPLY_NAMES = {"vee", "vee!", "v-", "avss", "dvss"}

# 被认定为电源的电压源 ref 前缀 (大写比较)
_POWER_V_PREFIXES = ("VCC", "VDD", "VEE", "VSS", "AVDD", "DVDD", "AVSS")


def _net_is_ground(name: str) -> bool:
    return name.lower() in _GROUND_NAMES


def _net_is_pos_supply(name: str) -> bool:
    return name.lower() in _POS_SUPPLY_NAMES


def _net_is_neg_supply(name: str) -> bool:
    return name.lower() in _NEG_SUPPLY_NAMES


def _net_is_power(name: str) -> bool:
    return _net_is_ground(name) or _net_is_pos_supply(name) or _net_is_neg_supply(name)


def _is_power_vsource(comp: Component) -> bool:
    """判断一个 V 型元件是否为电源电压源（而非信号源）。"""
    if comp.type != "V":
        return False
    ref_upper = comp.ref.upper()
    # 直接匹配: VCC, VDD, VEE, VSS …
    if any(ref_upper.startswith(pfx) for pfx in _POWER_V_PREFIXES):
        return True
    # 电压源的两个引脚之一是 GND/0，另一个是已知电源网络
    net_names = {p.net_name for p in comp.pins}
    has_gnd = any(_net_is_ground(n) for n in net_names)
    has_supply = any(_net_is_pos_supply(n) or _net_is_neg_supply(n)
                     for n in net_names)
    return has_gnd and has_supply


# ---------------------------------------------------------------------------
# 极性检测
# ---------------------------------------------------------------------------

def _resolve_skin_key(comp: Component, circuit: Circuit) -> str:
    """返回细化后的 skin key, 如 'Q_NPN', 'M_PMOS', 'R' 等。"""
    ctype = comp.type
    if ctype == "Q":
        return "Q_PNP" if _is_pnp(comp, circuit) else "Q_NPN"
    if ctype == "M":
        return "M_PMOS" if _is_pmos(comp, circuit) else "M_NMOS"
    return ctype


def _is_pnp(comp: Component, circuit: Circuit) -> bool:
    # 优先查 .model 定义（最可靠）
    model = circuit.models.get(comp.value)
    if model:
        mtype = model.type.upper()
        if "PNP" in mtype:
            return True
        if "NPN" in mtype:
            return False
    # 回退到 value 字符串猜测 — 先排除 NPN 再匹配 PNP
    # 防止 "QNPNPWR" 中的 "NPN" 子串被 "PNP" 误匹配
    val = comp.value.upper()
    if "NPN" in val:
        return False
    if "PNP" in val:
        return True
    return False


def _is_pmos(comp: Component, circuit: Circuit) -> bool:
    # 优先查 .model 定义（最可靠）
    model = circuit.models.get(comp.value)
    if model:
        mtype = model.type.upper()
        if "PMOS" in mtype or "PFET" in mtype:
            return True
        if "NMOS" in mtype or "NFET" in mtype:
            return False
    # 回退到 value 字符串猜测 — 先排除 NMOS 再匹配 PMOS
    val = comp.value.upper()
    if "NMOS" in val or "NFET" in val:
        return False
    if "PMOS" in val or "PFET" in val:
        return True
    return False


# ---------------------------------------------------------------------------
# 对称检测 — 差分对 / 电流镜
# ---------------------------------------------------------------------------

@dataclass
class SymmetricPair:
    """一对对称晶体管。"""
    left: str       # 左侧 ref (普通符号, gate/base 在左)
    right: str      # 右侧 ref (镜像符号, gate/base 在右)
    kind: str       # "diff_pair" | "current_mirror" | "complementary_pair"
    inward: bool = False  # diff_pair 专用: True = 基极/栅极向内 (left→_M, right→_ML)


def _detect_symmetric_pairs(
    components: list[Component],
    circuit: Circuit,
) -> list[SymmetricPair]:
    """检测差分对和电流镜。

    差分对: 相同类型、共享 S/E 节点、不同 G/B 和 D/C。
    电流镜: 相同类型、共享 G/B 和 S/E 节点、不同 D/C。
    """
    pairs: list[SymmetricPair] = []
    used: set[str] = set()

    # 按 (类型, 极性) 分组
    groups: dict[str, list[Component]] = {}
    for comp in components:
        if comp.type in ("M", "Q", "J"):
            key = _resolve_skin_key(comp, circuit)
            groups.setdefault(key, []).append(comp)

    for _key, comps in groups.items():
        if len(comps) < 2:
            continue

        # d/c 引脚=pin 0, g/b=pin 1, s/e=pin 2
        for i, c1 in enumerate(comps):
            if c1.ref in used:
                continue
            for c2 in comps[i + 1:]:
                if c2.ref in used:
                    continue
                if len(c1.pins) < 3 or len(c2.pins) < 3:
                    continue

                d1, g1, s1 = (c1.pins[0].net_name,
                              c1.pins[1].net_name,
                              c1.pins[2].net_name)
                d2, g2, s2 = (c2.pins[0].net_name,
                              c2.pins[1].net_name,
                              c2.pins[2].net_name)

                # ---- 差分对: 共 S/E, 不同 G/B 和 D/C ----
                if s1 == s2 and g1 != g2 and d1 != d2:
                    pairs.append(SymmetricPair(c1.ref, c2.ref, "diff_pair"))
                    used.update({c1.ref, c2.ref})
                    break

                # ---- 电流镜: 共 G/B + 共 S/E, 不同 D/C ----
                if g1 == g2 and s1 == s2 and d1 != d2:
                    # 二极管接法 (G=D) 的为左侧（参考管）
                    if g2 == d2:
                        pairs.append(SymmetricPair(c2.ref, c1.ref,
                                                   "current_mirror"))
                    else:
                        pairs.append(SymmetricPair(c1.ref, c2.ref,
                                                   "current_mirror"))
                    used.update({c1.ref, c2.ref})
                    break

    return pairs


def _reorder_components(
    components: list[Component],
    pairs: list[SymmetricPair],
) -> list[Component]:
    """重排序: 配对成员紧邻放置 (左先, 右后)。"""
    left_to_right = {p.left: p.right for p in pairs}
    right_to_left = {p.right: p.left for p in pairs}
    comp_map = {c.ref: c for c in components}

    ordered: list[Component] = []
    seen: set[str] = set()

    for comp in components:
        if comp.ref in seen:
            continue
        seen.add(comp.ref)

        if comp.ref in left_to_right:
            # 左侧成员 → 先加自己, 再加右侧
            ordered.append(comp)
            right_ref = left_to_right[comp.ref]
            ordered.append(comp_map[right_ref])
            seen.add(right_ref)
        elif comp.ref in right_to_left:
            # 右侧先遇到 → 先加左侧, 再加自己
            left_ref = right_to_left[comp.ref]
            ordered.append(comp_map[left_ref])
            seen.add(left_ref)
            ordered.append(comp)
        else:
            ordered.append(comp)

    return ordered


# ---------------------------------------------------------------------------
# 差分对基极方向优化 — 4 种配置 (左右 × 内外) 取交叉最少
# ---------------------------------------------------------------------------

def _count_wire_crossings(wires: list[tuple[float, float]]) -> int:
    """计算导线交叉数 (逆序对)。wire = (source_x, target_x)。"""
    n = len(wires)
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            si, ti = wires[i]
            sj, tj = wires[j]
            # 两条线的起点顺序与终点顺序相反 → 交叉
            if (si - sj) * (ti - tj) < 0:
                count += 1
    return count


def _optimize_diff_pairs(
    pairs: list[SymmetricPair],
    all_comps: list[Component],
    circuit: Circuit,
) -> list[SymmetricPair]:
    """预测 ELK 视觉排列, 调整差分对 left/right 使基极向外。

    ELK layered 算法会在同层内重排节点以最小化交叉。实测发现:
    collector/drain 网络外部连接数较多的那个晶体管会被 ELK 放到左侧。
    因此将该晶体管设为 SymmetricPair.left (获得普通 skin, base-left),
    另一个设为 right (获得 _DFR skin, base-right), 使基极自然向外。
    """
    comp_map = {c.ref: c for c in all_comps}

    def _ext_conn_count(net_name: str, exclude: set[str]) -> int:
        count = 0
        for comp in all_comps:
            if comp.ref in exclude:
                continue
            for pin in comp.pins:
                if pin.net_name == net_name:
                    count += 1
                    break
        return count

    result: list[SymmetricPair] = []
    for p in pairs:
        if p.kind != "diff_pair":
            result.append(p)
            continue

        c1 = comp_map.get(p.left)
        c2 = comp_map.get(p.right)
        if not c1 or not c2 or len(c1.pins) < 3 or len(c2.pins) < 3:
            result.append(p)
            continue

        exclude = {c1.ref, c2.ref}
        c1_ext = _ext_conn_count(c1.pins[0].net_name, exclude)
        c2_ext = _ext_conn_count(c2.pins[0].net_name, exclude)

        if c2_ext > c1_ext:
            # c2 的 C/D 外部连接更多 → ELK 会把 c2 放左边
            # 将 c2 设为 left (获得 base-left = 向外)
            result.append(SymmetricPair(c2.ref, c1.ref, "diff_pair"))
        else:
            # 保持原序 (c1 左, c2 右)
            result.append(SymmetricPair(c1.ref, c2.ref, "diff_pair"))

    return result


def _detect_complementary_pairs(
    components: list[Component],
    circuit: Circuit,
    pos_supply_nets: set[str],
    neg_supply_nets: set[str],
    ground_nets: set[str],
    already_used: set[str],
) -> list[SymmetricPair]:
    """检测互补推挽对 (NPN+PNP / NMOS+PMOS)。

    判据:
      - 一个 NPN 族, 一个 PNP 族 (或 NMOS/PMOS)
      - NPN.C/D → 正电源, PNP.C/D → 负电源或地
      - 两者 E/S 均不接电源 (接负载/输出)
    匹配: model 后缀优先, 否则按元件列表顺序贪心配对。
    """
    all_power = pos_supply_nets | neg_supply_nets | ground_nets

    npn_cands: list[Component] = []
    pnp_cands: list[Component] = []

    for comp in components:
        if comp.ref in already_used or comp.type not in ("Q", "M"):
            continue
        if len(comp.pins) < 3:
            continue
        skin_key = _resolve_skin_key(comp, circuit)
        c_net = comp.pins[0].net_name   # pin 0 = C/D
        e_net = comp.pins[2].net_name   # pin 2 = E/S
        is_npn = "NPN" in skin_key or "NMOS" in skin_key
        is_pnp = "PNP" in skin_key or "PMOS" in skin_key

        if is_npn and c_net in pos_supply_nets and e_net not in all_power:
            npn_cands.append(comp)
        elif is_pnp and (c_net in neg_supply_nets or c_net in ground_nets) \
                and e_net not in all_power:
            pnp_cands.append(comp)

    if not npn_cands or not pnp_cands:
        return []

    # ---------- 按 model 后缀 + 元件距离 打分配对 ----------
    def _suffix(comp: Component) -> str:
        val = (comp.value or "").upper()
        for pfx in ("NPN_", "PNP_", "NMOS_", "PMOS_",
                     "NPN", "PNP", "NMOS", "PMOS",
                     "QNPN", "QPNP"):
            if val.startswith(pfx):
                return val[len(pfx):]
        return val

    comp_idx = {c.ref: i for i, c in enumerate(components)}
    scores: list[tuple[int, int, int]] = []
    for ni, npn in enumerate(npn_cands):
        for pi, pnp in enumerate(pnp_cands):
            score = 0
            ns, ps = _suffix(npn), _suffix(pnp)
            if ns and ns == ps:
                score += 100
            score -= abs(comp_idx.get(npn.ref, 0)
                         - comp_idx.get(pnp.ref, 0))
            scores.append((score, ni, pi))

    scores.sort(reverse=True)
    pairs: list[SymmetricPair] = []
    used_n: set[int] = set()
    used_p: set[int] = set()
    for _score, ni, pi in scores:
        if ni in used_n or pi in used_p:
            continue
        pairs.append(SymmetricPair(
            npn_cands[ni].ref, pnp_cands[pi].ref, "complementary_pair"))
        used_n.add(ni)
        used_p.add(pi)

    return pairs


# ---------------------------------------------------------------------------
# 主转换
# ---------------------------------------------------------------------------

def circuit_to_netlistsvg_json(
    circuit: Circuit, *,
    direction: str = "DOWN",
) -> tuple[dict, list[tuple[str, str]]]:
    """将 Circuit IR 转换为 netlistsvg analog 兼容 JSON dict。

    Returns:
        (json_data, diff_pair_refs):
            json_data — netlistsvg 兼容的 JSON dict
            diff_pair_refs — 差分对列表 [(ref_a, ref_b), ...],
                用于 SVG 后处理时镜像右侧成员的晶体管符号
    """
    dir_table = _PORT_DIR

    # ---------- 1. 识别电源网络 / 电源电压源 ----------
    power_v_refs: set[str] = set()
    pos_supply_nets: set[str] = set()
    neg_supply_nets: set[str] = set()
    ground_nets: set[str] = set()

    for net_name in circuit.nets:
        if _net_is_ground(net_name):
            ground_nets.add(net_name)
        elif _net_is_pos_supply(net_name):
            pos_supply_nets.add(net_name)
        elif _net_is_neg_supply(net_name):
            neg_supply_nets.add(net_name)

    for comp in circuit.components:
        if _is_power_vsource(comp):
            power_v_refs.add(comp.ref)
            for pin in comp.pins:
                n = pin.net_name
                if not _net_is_ground(n):
                    nl = n.lower()
                    if nl in _POS_SUPPLY_NAMES or any(kw in nl for kw in ("vcc", "vdd")):
                        pos_supply_nets.add(n)
                    elif nl in _NEG_SUPPLY_NAMES or any(kw in nl for kw in ("vee",)):
                        neg_supply_nets.add(n)
                    else:
                        pos_supply_nets.add(n)

    all_power_nets = ground_nets | pos_supply_nets | neg_supply_nets

    # ---------- 2. 对称检测 ----------
    active_comps = [c for c in circuit.components
                    if c.ref not in power_v_refs]
    sym_pairs = _detect_symmetric_pairs(active_comps, circuit)

    # 差分对基极方向优化: 预测 ELK 视觉顺序, 调整 left/right
    sym_pairs = _optimize_diff_pairs(sym_pairs, active_comps, circuit)

    # 互补推挽对检测 (NPN+PNP / NMOS+PMOS, 两者 C/D→电源, E/S→负载)
    _used_in_pairs = {p.left for p in sym_pairs} | {p.right for p in sym_pairs}
    sym_pairs.extend(_detect_complementary_pairs(
        active_comps, circuit,
        pos_supply_nets, neg_supply_nets, ground_nets,
        _used_in_pairs))

    # 互补对不加 _ML/_M 后缀 (NPN 与 PNP 天然互补, 保持各自正常符号)
    # 差分对: 全部使用 normal skin (base-left), 由 SVG 后处理镜像右侧
    # 电流镜: left→_ML, right→_M (保持 s:dir 以消除层间约束)
    diff_pair_refs: list[tuple[str, str]] = []
    mirrored_refs: set[str] = set()
    mirror_left_refs: set[str] = set()
    for p in sym_pairs:
        if p.kind == "complementary_pair":
            continue
        if p.kind == "diff_pair":
            diff_pair_refs.append((p.left, p.right))
        else:
            # current_mirror: 保持 _ML/_M 以利用 s:dir="output"
            mirrored_refs.add(p.right)
            mirror_left_refs.add(p.left)

    # 电流镜成员 — 两侧的 gate 都视为 "output" 以消除 ELK 层间约束
    mirror_refs: set[str] = set()
    for p in sym_pairs:
        if p.kind == "current_mirror":
            mirror_refs.update({p.left, p.right})

    # 重排序 — 配对成员相邻
    active_comps = _reorder_components(active_comps, sym_pairs)

    # ---------- 3. 为常规网络分配 bit ----------
    net_bit: dict[str, int] = {}
    bit_counter = 2
    for net_name in circuit.nets:
        if net_name not in all_power_nets:
            net_bit[net_name] = bit_counter
            bit_counter += 1

    # ---------- 4. 构建 cells（两阶段: 先收集, 后组装） ----------
    # 每个器件产生一个 comp_cell 和若干 power_cells
    comp_entries: list[tuple[str, dict, list[tuple[str, dict]]]] = []
    # [(comp_ref, comp_cell, associated_power_cells), ...]
    pwr_idx = 0

    for comp in active_comps:
        skin_key = _resolve_skin_key(comp, circuit)
        if comp.ref in mirrored_refs:
            skin_key = skin_key + "_M"
        elif comp.ref in mirror_left_refs:
            skin_key = skin_key + "_ML"
        skin_type = _SKIN_TYPE.get(skin_key, skin_key.lower())
        # 剥离镜像/差分后缀回退到基础 key (Q_NPN_DFR → Q_NPN)
        base_key = skin_key
        for _sfx in ("_DFR", "_M", "_ML"):
            base_key = base_key.removesuffix(_sfx)
        pin_map = _PIN_MAP.get(skin_key, _PIN_MAP.get(
            base_key, _PIN_MAP.get(comp.type, {})))
        port_dirs = dir_table.get(skin_key, dir_table.get(
            base_key, dir_table.get(comp.type, {})))

        connections: dict[str, list[int]] = {}
        port_directions: dict[str, str] = {}
        my_pwr_cells: list[tuple[str, dict]] = []

        for pin in comp.pins:
            if comp.type == "M" and pin.number == 4:
                continue  # MOS body 引脚隐式省略

            skin_pin = pin_map.get(pin.number)
            if skin_pin is None:
                continue

            net_name = pin.net_name
            if net_name in all_power_nets:
                pwr_bit = bit_counter
                bit_counter += 1
                pwr_idx += 1

                if net_name in ground_nets:
                    pwr_type, pwr_label = "gnd", "GND"
                elif net_name in neg_supply_nets:
                    pwr_type, pwr_label = "vee", net_name.upper()
                else:
                    pwr_type, pwr_label = "vcc", net_name.upper()

                pwr_cell_name = f"{pwr_type}_{pwr_idx}"
                pwr_port_dir = "output" if pwr_type == "vcc" else "input"

                my_pwr_cells.append((pwr_cell_name, {
                    "type": pwr_type,
                    "port_directions": {"A": pwr_port_dir},
                    "connections": {"A": [pwr_bit]},
                    "attributes": {"name": pwr_label},
                }))
                connections[skin_pin] = [pwr_bit]
            else:
                bit = net_bit.get(net_name, 0)
                connections[skin_pin] = [bit]

            port_directions[skin_pin] = port_dirs.get(skin_pin, "input")

        # 二极管接法 / 电流镜修复: 统一 gate 方向避免 ELK 层级错乱
        if comp.type in ("M", "Q", "J"):
            drain_pin = "D" if comp.type in ("M", "J") else "C"
            gate_pin = "G" if comp.type in ("M", "J") else "B"
            source_pin = "S" if comp.type in ("M", "J") else "E"
            # 1) 二极管接法 (G=D): gate 方向改为与 drain 一致
            if (drain_pin in connections and gate_pin in connections
                    and connections[drain_pin] == connections[gate_pin]):
                port_directions[gate_pin] = port_directions.get(
                    drain_pin, "output")
            # 2) 电流镜成员: gate 方向也设为与 drain 一致, 打破层间依赖
            elif comp.ref in mirror_refs:
                if drain_pin in port_directions and gate_pin in port_directions:
                    port_directions[gate_pin] = port_directions[drain_pin]

            # 3) 倒置 PNP/PMOS: C/D→负电源 且 E/S→负载
            #    此时 E/S 功能上是输出端, 需翻转为 "output" 使信号自然向下流
            if "PNP" in skin_key or "PMOS" in skin_key:
                d_net = next(
                    (p.net_name for p in comp.pins
                     if pin_map.get(p.number) == drain_pin), "")
                s_net = next(
                    (p.net_name for p in comp.pins
                     if pin_map.get(p.number) == source_pin), "")
                d_to_neg = (d_net in neg_supply_nets or d_net in ground_nets)
                s_to_nonpower = (s_net != "" and s_net not in all_power_nets)
                if d_to_neg and s_to_nonpower:
                    port_directions[source_pin] = "output"

        comp_cell = {
            "type": skin_type,
            "attributes": {"value": comp.value, "ref": comp.ref},
            "connections": connections,
            "port_directions": port_directions,
        }
        comp_entries.append((comp.ref, comp_cell, my_pwr_cells))

    # ---- 组装 cells: 配对的 VCC/GND 先集中, 再器件对紧邻 ----
    paired_refs = {p.left for p in sym_pairs} | {p.right for p in sym_pairs}
    pair_left_set = {p.left for p in sym_pairs}

    cells: dict[str, Any] = {}
    emitted: set[str] = set()

    for ref, cell, pwr_cells in comp_entries:
        if ref in emitted:
            continue

        if ref in pair_left_set:
            # 找到右侧伙伴
            right_ref = next(p.right for p in sym_pairs if p.left == ref)
            right_entry = next(e for e in comp_entries if e[0] == right_ref)

            # 先输出配对双方的所有 VCC 电源 cell
            for pname, pcell in pwr_cells:
                if pcell["type"] == "vcc":
                    cells[pname] = pcell
            for pname, pcell in right_entry[2]:
                if pcell["type"] == "vcc":
                    cells[pname] = pcell

            # 然后左 → 右器件 (紧邻!)
            cells[ref] = cell
            cells[right_ref] = right_entry[1]

            # 最后 GND/VEE 电源 cell
            for pname, pcell in pwr_cells:
                if pcell["type"] != "vcc":
                    cells[pname] = pcell
            for pname, pcell in right_entry[2]:
                if pcell["type"] != "vcc":
                    cells[pname] = pcell

            emitted.update({ref, right_ref})
        elif ref in paired_refs:
            # 右侧成员 — 跳过, 已随左侧一起输出
            continue
        else:
            # 非配对器件: power cells → 器件
            for pname, pcell in pwr_cells:
                cells[pname] = pcell
            cells[ref] = cell
            emitted.add(ref)

    # ---------- 5. 构建 ports ----------
    ports: dict[str, Any] = {}
    cell_names = set(cells.keys())
    for net in circuit.port_nets():
        if net.name in all_power_nets:
            continue  # 电源网络已转为 VCC/GND cell，不再作为 port
        if net.name in cell_names:
            continue
        bit = net_bit.get(net.name, 0)
        direction = net.direction if net.direction != "inout" else "input"
        ports[net.name] = {"bits": [bit], "direction": direction}

    return {"modules": {"": {"cells": cells, "ports": ports}}}, diff_pair_refs


# ---------------------------------------------------------------------------
# 超节点模式: 将识别出的超节点折叠为单个 cell
# ---------------------------------------------------------------------------

def circuit_to_netlistsvg_json_with_supernodes(
    circuit: Circuit,
    supernodes: list,
    *,
    direction: str = "DOWN",
) -> tuple[dict, list[tuple[str, str]]]:
    """带超节点支持的 JSON 转换。

    与 circuit_to_netlistsvg_json 相同的逻辑, 但:
    1. 属于超节点的元件不再作为独立 cell 输出
    2. 每个超节点作为单个 cell 输出, 使用自定义 skin_type
    3. 超节点的内部网络不分配 bit 编号 (被吸收)

    Args:
        circuit: 电路 IR
        supernodes: 超节点列表 (来自 recognizer.recognize_supernodes)
        direction: 布局方向

    Returns:
        (json_data, diff_pair_refs) — 与 circuit_to_netlistsvg_json 相同格式
    """
    from ..recognizer.supernode import SuperNode

    if not supernodes:
        return circuit_to_netlistsvg_json(circuit, direction=direction)

    # 构建超节点成员查找表
    ref_to_supernode: dict[str, SuperNode] = {}
    for sn in supernodes:
        for ref in sn.component_refs:
            ref_to_supernode[ref] = sn

    # 收集所有内部网络 (不分配 bit)
    all_internal_nets: set[str] = set()
    for sn in supernodes:
        all_internal_nets.update(sn.internal_nets)

    # ---------- 1. 识别电源网络 (与原逻辑相同) ----------
    power_v_refs: set[str] = set()
    pos_supply_nets: set[str] = set()
    neg_supply_nets: set[str] = set()
    ground_nets: set[str] = set()

    for net_name in circuit.nets:
        if _net_is_ground(net_name):
            ground_nets.add(net_name)
        elif _net_is_pos_supply(net_name):
            pos_supply_nets.add(net_name)
        elif _net_is_neg_supply(net_name):
            neg_supply_nets.add(net_name)

    for comp in circuit.components:
        if _is_power_vsource(comp):
            power_v_refs.add(comp.ref)
            for p in comp.pins:
                n = p.net_name
                if not _net_is_ground(n):
                    nl = n.lower()
                    if nl in _POS_SUPPLY_NAMES or any(kw in nl for kw in ("vcc", "vdd")):
                        pos_supply_nets.add(n)
                    elif nl in _NEG_SUPPLY_NAMES or any(kw in nl for kw in ("vee",)):
                        neg_supply_nets.add(n)
                    else:
                        pos_supply_nets.add(n)

    all_power_nets = ground_nets | pos_supply_nets | neg_supply_nets

    # ---------- 2. 过滤出非超节点元件, 走原逻辑 ----------
    free_comps = [c for c in circuit.components
                  if c.ref not in power_v_refs and c.ref not in ref_to_supernode]

    # 对非超节点元件做对称检测 (差分对/电流镜)
    sym_pairs = _detect_symmetric_pairs(free_comps, circuit)
    sym_pairs = _optimize_diff_pairs(sym_pairs, free_comps, circuit)

    _used_in_pairs = {p.left for p in sym_pairs} | {p.right for p in sym_pairs}
    sym_pairs.extend(_detect_complementary_pairs(
        free_comps, circuit,
        pos_supply_nets, neg_supply_nets, ground_nets,
        _used_in_pairs))

    diff_pair_refs: list[tuple[str, str]] = []
    mirrored_refs: set[str] = set()
    mirror_left_refs: set[str] = set()
    mirror_refs: set[str] = set()
    for p in sym_pairs:
        if p.kind == "complementary_pair":
            continue
        if p.kind == "diff_pair":
            diff_pair_refs.append((p.left, p.right))
        else:
            mirrored_refs.add(p.right)
            mirror_left_refs.add(p.left)
    for p in sym_pairs:
        if p.kind == "current_mirror":
            mirror_refs.update({p.left, p.right})

    free_comps = _reorder_components(free_comps, sym_pairs)

    # ---------- 3. 分配 bit ----------
    net_bit: dict[str, int] = {}
    bit_counter = 2
    for net_name in circuit.nets:
        if net_name not in all_power_nets and net_name not in all_internal_nets:
            net_bit[net_name] = bit_counter
            bit_counter += 1

    # ---------- 4a. 构建超节点 cells ----------
    sn_cells: dict[str, dict] = {}
    pwr_idx = 0

    for sn in supernodes:
        connections: dict[str, list[int]] = {}
        port_directions: dict[str, str] = {}
        sn_pwr_cells: list[tuple[str, dict]] = []

        for port_name, (net_name, direction) in sn.external_ports.items():
            # 跳过自动生成的内部端口标记
            if port_name.startswith("_AUTO_") and net_name in all_internal_nets:
                continue

            # 跳过自动暴露的电源连接 — 它们是块的隐式内部布线,
            # skin 中没有对应端口, 暴露会导致 netlistsvg 报错
            if port_name.startswith("_AUTO_") and net_name in all_power_nets:
                continue

            if net_name in all_power_nets:
                pwr_bit = bit_counter
                bit_counter += 1
                pwr_idx += 1

                if net_name in ground_nets:
                    pwr_type, pwr_label = "gnd", "GND"
                elif net_name in neg_supply_nets:
                    pwr_type, pwr_label = "vee", net_name.upper()
                else:
                    pwr_type, pwr_label = "vcc", net_name.upper()

                pwr_cell_name = f"{pwr_type}_{pwr_idx}"
                pwr_port_dir = "output" if pwr_type == "vcc" else "input"

                sn_pwr_cells.append((pwr_cell_name, {
                    "type": pwr_type,
                    "port_directions": {"A": pwr_port_dir},
                    "connections": {"A": [pwr_bit]},
                    "attributes": {"name": pwr_label},
                }))
                # 使用清理后的端口名
                clean_name = port_name.removeprefix("_AUTO_")
                connections[clean_name] = [pwr_bit]
                # netlistsvg 只接受 "input"/"output"
                port_directions[clean_name] = direction if direction in ("input", "output") else "input"
            else:
                bit = net_bit.get(net_name, 0)
                clean_name = port_name.removeprefix("_AUTO_")
                connections[clean_name] = [bit]
                # netlistsvg 只接受 "input"/"output"
                port_directions[clean_name] = direction if direction in ("input", "output") else "input"

        sn_cell = {
            "type": sn.skin_type,
            "attributes": {
                "ref": sn.ref,
                "value": sn.display_name,
                "components": ",".join(sn.component_refs),
            },
            "connections": connections,
            "port_directions": port_directions,
        }

        # 输出电源 cells → 超节点 cell
        for pname, pcell in sn_pwr_cells:
            sn_cells[pname] = pcell
        sn_cells[sn.ref] = sn_cell

    # ---------- 4b. 构建非超节点元件 cells (与原逻辑相同) ----------
    comp_entries: list[tuple[str, dict, list[tuple[str, dict]]]] = []
    dir_table = _PORT_DIR

    for comp in free_comps:
        skin_key = _resolve_skin_key(comp, circuit)
        if comp.ref in mirrored_refs:
            skin_key = skin_key + "_M"
        elif comp.ref in mirror_left_refs:
            skin_key = skin_key + "_ML"
        skin_type = _SKIN_TYPE.get(skin_key, skin_key.lower())
        base_key = skin_key
        for _sfx in ("_DFR", "_M", "_ML"):
            base_key = base_key.removesuffix(_sfx)
        pin_map = _PIN_MAP.get(skin_key, _PIN_MAP.get(
            base_key, _PIN_MAP.get(comp.type, {})))
        port_dirs = dir_table.get(skin_key, dir_table.get(
            base_key, dir_table.get(comp.type, {})))

        connections: dict[str, list[int]] = {}
        port_directions: dict[str, str] = {}
        my_pwr_cells: list[tuple[str, dict]] = []

        for p in comp.pins:
            if comp.type == "M" and p.number == 4:
                continue
            skin_pin = pin_map.get(p.number)
            if skin_pin is None:
                continue
            net_name = p.net_name
            if net_name in all_power_nets:
                pwr_bit = bit_counter
                bit_counter += 1
                pwr_idx += 1
                if net_name in ground_nets:
                    pwr_type, pwr_label = "gnd", "GND"
                elif net_name in neg_supply_nets:
                    pwr_type, pwr_label = "vee", net_name.upper()
                else:
                    pwr_type, pwr_label = "vcc", net_name.upper()
                pwr_cell_name = f"{pwr_type}_{pwr_idx}"
                pwr_port_dir = "output" if pwr_type == "vcc" else "input"
                my_pwr_cells.append((pwr_cell_name, {
                    "type": pwr_type,
                    "port_directions": {"A": pwr_port_dir},
                    "connections": {"A": [pwr_bit]},
                    "attributes": {"name": pwr_label},
                }))
                connections[skin_pin] = [pwr_bit]
            else:
                bit = net_bit.get(net_name, 0)
                connections[skin_pin] = [bit]
            port_directions[skin_pin] = port_dirs.get(skin_pin, "input")

        # 二极管接法 / 电流镜修复
        if comp.type in ("M", "Q", "J"):
            drain_pin = "D" if comp.type in ("M", "J") else "C"
            gate_pin = "G" if comp.type in ("M", "J") else "B"
            source_pin = "S" if comp.type in ("M", "J") else "E"
            if (drain_pin in connections and gate_pin in connections
                    and connections[drain_pin] == connections[gate_pin]):
                port_directions[gate_pin] = port_directions.get(
                    drain_pin, "output")
            elif comp.ref in mirror_refs:
                if drain_pin in port_directions and gate_pin in port_directions:
                    port_directions[gate_pin] = port_directions[drain_pin]
            if "PNP" in skin_key or "PMOS" in skin_key:
                d_net = next(
                    (pp.net_name for pp in comp.pins
                     if pin_map.get(pp.number) == drain_pin), "")
                s_net = next(
                    (pp.net_name for pp in comp.pins
                     if pin_map.get(pp.number) == source_pin), "")
                d_to_neg = (d_net in neg_supply_nets or d_net in ground_nets)
                s_to_nonpower = (s_net != "" and s_net not in all_power_nets)
                if d_to_neg and s_to_nonpower:
                    port_directions[source_pin] = "output"

        comp_cell = {
            "type": skin_type,
            "attributes": {"value": comp.value, "ref": comp.ref},
            "connections": connections,
            "port_directions": port_directions,
        }
        comp_entries.append((comp.ref, comp_cell, my_pwr_cells))

    # ---- 组装非超节点 cells (与原逻辑相同) ----
    paired_refs = {p.left for p in sym_pairs} | {p.right for p in sym_pairs}
    pair_left_set = {p.left for p in sym_pairs}

    cells: dict[str, Any] = {}
    emitted: set[str] = set()

    # 先放超节点 cells
    cells.update(sn_cells)

    for ref, cell, pwr_cells in comp_entries:
        if ref in emitted:
            continue
        if ref in pair_left_set:
            right_ref = next(p.right for p in sym_pairs if p.left == ref)
            right_entry = next(e for e in comp_entries if e[0] == right_ref)
            for pname, pcell in pwr_cells:
                if pcell["type"] == "vcc":
                    cells[pname] = pcell
            for pname, pcell in right_entry[2]:
                if pcell["type"] == "vcc":
                    cells[pname] = pcell
            cells[ref] = cell
            cells[right_ref] = right_entry[1]
            for pname, pcell in pwr_cells:
                if pcell["type"] != "vcc":
                    cells[pname] = pcell
            for pname, pcell in right_entry[2]:
                if pcell["type"] != "vcc":
                    cells[pname] = pcell
            emitted.update({ref, right_ref})
        elif ref in paired_refs:
            continue
        else:
            for pname, pcell in pwr_cells:
                cells[pname] = pcell
            cells[ref] = cell
            emitted.add(ref)

    # ---------- 5. 构建 ports ----------
    ports: dict[str, Any] = {}
    cell_names = set(cells.keys())
    for net in circuit.port_nets():
        if net.name in all_power_nets:
            continue
        if net.name in cell_names:
            continue
        if net.name in all_internal_nets:
            continue
        bit = net_bit.get(net.name, 0)
        direction = net.direction if net.direction != "inout" else "input"
        ports[net.name] = {"bits": [bit], "direction": direction}

    return {"modules": {"": {"cells": cells, "ports": ports}}}, diff_pair_refs


def circuit_to_json_string(circuit: Circuit, indent: int = 2,
                           *, direction: str = "DOWN",
                           supernodes: list | None = None) -> str:
    if supernodes:
        data, _ = circuit_to_netlistsvg_json_with_supernodes(
            circuit, supernodes, direction=direction)
    else:
        data, _ = circuit_to_netlistsvg_json(circuit, direction=direction)
    return json.dumps(data, indent=indent, ensure_ascii=False)
