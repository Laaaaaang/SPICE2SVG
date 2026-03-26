"""模拟电路常见模式库。

引脚索引约定 (0-based, 对应 SPICE 引脚顺序):
  BJT (Q):    0=C (Collector),  1=B (Base),    2=E (Emitter)
  MOSFET (M): 0=D (Drain),      1=G (Gate),    2=S (Source),  3=B (Body)
  JFET (J):   0=D (Drain),      1=G (Gate),    2=S (Source)
  二端元件:    0=pin1(+/A/1),    1=pin2(-/K/B/2)
"""

from __future__ import annotations

from .pattern_def import (
    PatternDef, Role, ExternalPort, pin,
    SameNet, DiffNet, NetIs, NetIsNot,
)


# ===================================================================
# 1. 差分对 (Differential Pairs)
# ===================================================================
#
# 拓扑: 两个相同类型晶体管, 共享 S/E, 不同 G/B, 不同 D/C
# 反交叉约束: G1≠D2 且 G2≠D1 (排除交叉耦合锁存器)
#
#        OUTP   OUTN
#         |       |
#       [QL]    [QR]
#         \     /
#          TAIL
# -------------------------------------------------------------------

DIFF_PAIR_NPN = PatternDef(
    name="diff_pair_npn",
    display_name="NPN 差分对",
    description="两个 NPN BJT, 共享 E, 不同 B/C, 非交叉耦合",
    roles=[
        Role("QL", "Q", "NPN"),
        Role("QR", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("QL", 2), pin("QR", 2)),   # 共享 E
        DiffNet(pin("QL", 1), pin("QR", 1)),   # 不同 B
        DiffNet(pin("QL", 0), pin("QR", 0)),   # 不同 C
        DiffNet(pin("QL", 1), pin("QR", 0)),   # 反交叉: B_L ≠ C_R
        DiffNet(pin("QR", 1), pin("QL", 0)),   # 反交叉: B_R ≠ C_L
    ],
    external_ports=[
        ExternalPort("INP",  pin("QL", 1), "input"),
        ExternalPort("INN",  pin("QR", 1), "input"),
        ExternalPort("OUTP", pin("QL", 0), "output"),
        ExternalPort("OUTN", pin("QR", 0), "output"),
        ExternalPort("TAIL", pin("QL", 2), "output"),
    ],
    skin_type="diff_pair_npn",
    priority=10,
)

DIFF_PAIR_PNP = PatternDef(
    name="diff_pair_pnp",
    display_name="PNP 差分对",
    description="两个 PNP BJT, 共享 E, 不同 B/C, 非交叉耦合",
    roles=[
        Role("QL", "Q", "PNP"),
        Role("QR", "Q", "PNP"),
    ],
    constraints=[
        SameNet(pin("QL", 2), pin("QR", 2)),
        DiffNet(pin("QL", 1), pin("QR", 1)),
        DiffNet(pin("QL", 0), pin("QR", 0)),
        DiffNet(pin("QL", 1), pin("QR", 0)),
        DiffNet(pin("QR", 1), pin("QL", 0)),
    ],
    external_ports=[
        ExternalPort("INP",  pin("QL", 1), "input"),
        ExternalPort("INN",  pin("QR", 1), "input"),
        ExternalPort("OUTP", pin("QL", 0), "output"),
        ExternalPort("OUTN", pin("QR", 0), "output"),
        ExternalPort("TAIL", pin("QL", 2), "input"),   # PNP tail 在上, input
    ],
    skin_type="diff_pair_pnp",
    priority=10,
)

DIFF_PAIR_NMOS = PatternDef(
    name="diff_pair_nmos",
    display_name="NMOS 差分对",
    description="两个 NMOS, 共享 S, 不同 G/D, 非交叉耦合",
    roles=[
        Role("ML", "M", "NMOS"),
        Role("MR", "M", "NMOS"),
    ],
    constraints=[
        SameNet(pin("ML", 2), pin("MR", 2)),   # 共享 S
        DiffNet(pin("ML", 1), pin("MR", 1)),   # 不同 G
        DiffNet(pin("ML", 0), pin("MR", 0)),   # 不同 D
        DiffNet(pin("ML", 1), pin("MR", 0)),   # 反交叉
        DiffNet(pin("MR", 1), pin("ML", 0)),
    ],
    external_ports=[
        ExternalPort("INP",  pin("ML", 1), "input"),
        ExternalPort("INN",  pin("MR", 1), "input"),
        ExternalPort("OUTP", pin("ML", 0), "output"),
        ExternalPort("OUTN", pin("MR", 0), "output"),
        ExternalPort("TAIL", pin("ML", 2), "output"),
    ],
    skin_type="diff_pair_nmos",
    priority=10,
)

DIFF_PAIR_PMOS = PatternDef(
    name="diff_pair_pmos",
    display_name="PMOS 差分对",
    description="两个 PMOS, 共享 S, 不同 G/D, 非交叉耦合",
    roles=[
        Role("ML", "M", "PMOS"),
        Role("MR", "M", "PMOS"),
    ],
    constraints=[
        SameNet(pin("ML", 2), pin("MR", 2)),
        DiffNet(pin("ML", 1), pin("MR", 1)),
        DiffNet(pin("ML", 0), pin("MR", 0)),
        DiffNet(pin("ML", 1), pin("MR", 0)),
        DiffNet(pin("MR", 1), pin("ML", 0)),
    ],
    external_ports=[
        ExternalPort("INP",  pin("ML", 1), "input"),
        ExternalPort("INN",  pin("MR", 1), "input"),
        ExternalPort("OUTP", pin("ML", 0), "output"),
        ExternalPort("OUTN", pin("MR", 0), "output"),
        ExternalPort("TAIL", pin("ML", 2), "input"),
    ],
    skin_type="diff_pair_pmos",
    priority=10,
)


# ===================================================================
# 2. 电流镜 (Current Mirrors)
# ===================================================================
#
# 拓扑: 两个相同类型晶体管, 共享 G/B + S/E, 不同 D/C,
#        其中参考管二极管接法 (G=D 或 B=C)
#
#       IN      OUT
#        |       |
#      [QREF]  [QMIR]
#        \     /
#         RAIL
# -------------------------------------------------------------------

CURRENT_MIRROR_NPN = PatternDef(
    name="current_mirror_npn",
    display_name="NPN 电流镜",
    description="两个 NPN, 共享 B+E, 参考管 B=C (二极管接法)",
    roles=[
        Role("QREF", "Q", "NPN"),
        Role("QMIR", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("QREF", 1), pin("QMIR", 1)),   # 共享 B
        SameNet(pin("QREF", 2), pin("QMIR", 2)),   # 共享 E
        DiffNet(pin("QREF", 0), pin("QMIR", 0)),   # 不同 C
        SameNet(pin("QREF", 0), pin("QREF", 1)),   # 参考管: C=B
    ],
    external_ports=[
        ExternalPort("IN",   pin("QREF", 0), "input"),
        ExternalPort("OUT",  pin("QMIR", 0), "output"),
        ExternalPort("RAIL", pin("QREF", 2), "output"),
    ],
    skin_type="current_mirror_npn",
    priority=10,
)

CURRENT_MIRROR_PNP = PatternDef(
    name="current_mirror_pnp",
    display_name="PNP 电流镜",
    description="两个 PNP, 共享 B+E, 参考管 B=C",
    roles=[
        Role("QREF", "Q", "PNP"),
        Role("QMIR", "Q", "PNP"),
    ],
    constraints=[
        SameNet(pin("QREF", 1), pin("QMIR", 1)),
        SameNet(pin("QREF", 2), pin("QMIR", 2)),
        DiffNet(pin("QREF", 0), pin("QMIR", 0)),
        SameNet(pin("QREF", 0), pin("QREF", 1)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("QREF", 0), "input"),
        ExternalPort("OUT",  pin("QMIR", 0), "output"),
        ExternalPort("RAIL", pin("QREF", 2), "input"),
    ],
    skin_type="current_mirror_pnp",
    priority=10,
)

CURRENT_MIRROR_NMOS = PatternDef(
    name="current_mirror_nmos",
    display_name="NMOS 电流镜",
    description="两个 NMOS, 共享 G+S, 参考管 G=D",
    roles=[
        Role("MREF", "M", "NMOS"),
        Role("MMIR", "M", "NMOS"),
    ],
    constraints=[
        SameNet(pin("MREF", 1), pin("MMIR", 1)),   # 共享 G
        SameNet(pin("MREF", 2), pin("MMIR", 2)),   # 共享 S
        DiffNet(pin("MREF", 0), pin("MMIR", 0)),   # 不同 D
        SameNet(pin("MREF", 0), pin("MREF", 1)),   # 参考管: D=G
    ],
    external_ports=[
        ExternalPort("IN",   pin("MREF", 0), "input"),
        ExternalPort("OUT",  pin("MMIR", 0), "output"),
        ExternalPort("RAIL", pin("MREF", 2), "output"),
    ],
    skin_type="current_mirror_nmos",
    priority=10,
)

CURRENT_MIRROR_PMOS = PatternDef(
    name="current_mirror_pmos",
    display_name="PMOS 电流镜",
    description="两个 PMOS, 共享 G+S, 参考管 G=D",
    roles=[
        Role("MREF", "M", "PMOS"),
        Role("MMIR", "M", "PMOS"),
    ],
    constraints=[
        SameNet(pin("MREF", 1), pin("MMIR", 1)),
        SameNet(pin("MREF", 2), pin("MMIR", 2)),
        DiffNet(pin("MREF", 0), pin("MMIR", 0)),
        SameNet(pin("MREF", 0), pin("MREF", 1)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("MREF", 0), "input"),
        ExternalPort("OUT",  pin("MMIR", 0), "output"),
        ExternalPort("RAIL", pin("MREF", 2), "input"),
    ],
    skin_type="current_mirror_pmos",
    priority=10,
)


# ===================================================================
# 3. 交叉耦合对 (Cross-Coupled Pairs / Latches)
# ===================================================================
#
# 拓扑: 两个相同类型晶体管, 共享 S/E,
#        但 G1=D2 且 G2=D1 (交叉耦合)
# -------------------------------------------------------------------

CROSS_COUPLED_NPN = PatternDef(
    name="cross_coupled_npn",
    display_name="NPN 交叉耦合对",
    description="两个 NPN BJT, 共享 E, B1=C2 且 B2=C1",
    roles=[
        Role("Q1", "Q", "NPN"),
        Role("Q2", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("Q1", 2), pin("Q2", 2)),   # 共享 E
        SameNet(pin("Q1", 1), pin("Q2", 0)),   # B1 = C2
        SameNet(pin("Q2", 1), pin("Q1", 0)),   # B2 = C1
    ],
    external_ports=[
        ExternalPort("OUTP", pin("Q1", 0), "output"),
        ExternalPort("OUTN", pin("Q2", 0), "output"),
        ExternalPort("TAIL", pin("Q1", 2), "output"),
    ],
    skin_type="cross_coupled_npn",
    priority=15,   # 比差分对优先级高, 避免被误识别为差分对
)

CROSS_COUPLED_NMOS = PatternDef(
    name="cross_coupled_nmos",
    display_name="NMOS 交叉耦合对",
    description="两个 NMOS, 共享 S, G1=D2 且 G2=D1",
    roles=[
        Role("M1", "M", "NMOS"),
        Role("M2", "M", "NMOS"),
    ],
    constraints=[
        SameNet(pin("M1", 2), pin("M2", 2)),
        SameNet(pin("M1", 1), pin("M2", 0)),
        SameNet(pin("M2", 1), pin("M1", 0)),
    ],
    external_ports=[
        ExternalPort("OUTP", pin("M1", 0), "output"),
        ExternalPort("OUTN", pin("M2", 0), "output"),
        ExternalPort("TAIL", pin("M1", 2), "output"),
    ],
    skin_type="cross_coupled_nmos",
    priority=15,
)


# ===================================================================
# 4. 共射/共栅级联 — Cascode
# ===================================================================
#
# 拓扑: Q_LOW 的 C/D 连 Q_HIGH 的 E/S, Q_HIGH 的 G/B 接偏置
#
#          OUT
#           |
#        [Q_HI]  ← B/G = BIAS
#           |
#        [Q_LO]  ← B/G = IN
#           |
#          RAIL
# -------------------------------------------------------------------

CASCODE_NPN = PatternDef(
    name="cascode_npn",
    display_name="NPN Cascode",
    description="NPN 共射-共基级联: Q_LO.C = Q_HI.E",
    roles=[
        Role("Q_LO", "Q", "NPN"),
        Role("Q_HI", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("Q_LO", 0), pin("Q_HI", 2)),   # C_LO = E_HI
        DiffNet(pin("Q_LO", 1), pin("Q_HI", 1)),   # 不同 B
        DiffNet(pin("Q_LO", 0), pin("Q_HI", 0)),   # C_LO ≠ C_HI
        DiffNet(pin("Q_LO", 2), pin("Q_HI", 2)),   # E_LO ≠ E_HI
    ],
    external_ports=[
        ExternalPort("IN",   pin("Q_LO", 1), "input"),
        ExternalPort("BIAS", pin("Q_HI", 1), "input"),
        ExternalPort("OUT",  pin("Q_HI", 0), "output"),
        ExternalPort("RAIL", pin("Q_LO", 2), "output"),
    ],
    skin_type="cascode_npn",
    priority=8,
)

CASCODE_PNP = PatternDef(
    name="cascode_pnp",
    display_name="PNP Cascode",
    description="PNP 共射-共基级联: Q_LO.C = Q_HI.E",
    roles=[
        Role("Q_LO", "Q", "PNP"),
        Role("Q_HI", "Q", "PNP"),
    ],
    constraints=[
        SameNet(pin("Q_LO", 0), pin("Q_HI", 2)),
        DiffNet(pin("Q_LO", 1), pin("Q_HI", 1)),
        DiffNet(pin("Q_LO", 0), pin("Q_HI", 0)),
        DiffNet(pin("Q_LO", 2), pin("Q_HI", 2)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("Q_LO", 1), "input"),
        ExternalPort("BIAS", pin("Q_HI", 1), "input"),
        ExternalPort("OUT",  pin("Q_HI", 0), "output"),
        ExternalPort("RAIL", pin("Q_LO", 2), "input"),
    ],
    skin_type="cascode_pnp",
    priority=8,
)

CASCODE_NMOS = PatternDef(
    name="cascode_nmos",
    display_name="NMOS Cascode",
    description="NMOS 共源-共栅级联: M_LO.D = M_HI.S",
    roles=[
        Role("M_LO", "M", "NMOS"),
        Role("M_HI", "M", "NMOS"),
    ],
    constraints=[
        SameNet(pin("M_LO", 0), pin("M_HI", 2)),   # D_LO = S_HI
        DiffNet(pin("M_LO", 1), pin("M_HI", 1)),
        DiffNet(pin("M_LO", 0), pin("M_HI", 0)),
        DiffNet(pin("M_LO", 2), pin("M_HI", 2)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("M_LO", 1), "input"),
        ExternalPort("BIAS", pin("M_HI", 1), "input"),
        ExternalPort("OUT",  pin("M_HI", 0), "output"),
        ExternalPort("RAIL", pin("M_LO", 2), "output"),
    ],
    skin_type="cascode_nmos",
    priority=8,
)

CASCODE_PMOS = PatternDef(
    name="cascode_pmos",
    display_name="PMOS Cascode",
    description="PMOS 共源-共栅级联: M_LO.D = M_HI.S",
    roles=[
        Role("M_LO", "M", "PMOS"),
        Role("M_HI", "M", "PMOS"),
    ],
    constraints=[
        SameNet(pin("M_LO", 0), pin("M_HI", 2)),
        DiffNet(pin("M_LO", 1), pin("M_HI", 1)),
        DiffNet(pin("M_LO", 0), pin("M_HI", 0)),
        DiffNet(pin("M_LO", 2), pin("M_HI", 2)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("M_LO", 1), "input"),
        ExternalPort("BIAS", pin("M_HI", 1), "input"),
        ExternalPort("OUT",  pin("M_HI", 0), "output"),
        ExternalPort("RAIL", pin("M_LO", 2), "input"),
    ],
    skin_type="cascode_pmos",
    priority=8,
)


# ===================================================================
# 5. Darlington 对
# ===================================================================
#
# 拓扑: Q1.E = Q2.B, 共享 C 节点
#
#          C (shared)
#          |
#        [Q1]  ← B = IN
#          |E
#        [Q2]  ← B = Q1.E
#          |E
#         OUT
# -------------------------------------------------------------------

DARLINGTON_NPN = PatternDef(
    name="darlington_npn",
    display_name="NPN Darlington",
    description="NPN Darlington: Q1.E=Q2.B, Q1.C=Q2.C",
    roles=[
        Role("Q1", "Q", "NPN"),
        Role("Q2", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("Q1", 2), pin("Q2", 1)),   # E1 = B2
        SameNet(pin("Q1", 0), pin("Q2", 0)),   # 共享 C
    ],
    external_ports=[
        ExternalPort("IN",  pin("Q1", 1), "input"),
        ExternalPort("C",   pin("Q1", 0), "input"),
        ExternalPort("OUT", pin("Q2", 2), "output"),
    ],
    skin_type="darlington_npn",
    priority=8,
)

DARLINGTON_PNP = PatternDef(
    name="darlington_pnp",
    display_name="PNP Darlington",
    description="PNP Darlington: Q1.E=Q2.B, Q1.C=Q2.C",
    roles=[
        Role("Q1", "Q", "PNP"),
        Role("Q2", "Q", "PNP"),
    ],
    constraints=[
        SameNet(pin("Q1", 2), pin("Q2", 1)),
        SameNet(pin("Q1", 0), pin("Q2", 0)),
    ],
    external_ports=[
        ExternalPort("IN",  pin("Q1", 1), "input"),
        ExternalPort("C",   pin("Q1", 0), "output"),
        ExternalPort("OUT", pin("Q2", 2), "input"),
    ],
    skin_type="darlington_pnp",
    priority=8,
)


# ===================================================================
# 6. Sziklai 对 (互补 Darlington)
# ===================================================================
#
# 拓扑: NPN.E → PNP.B, NPN.C = PNP.E (或反过来)
# -------------------------------------------------------------------

SZIKLAI_NPN_PNP = PatternDef(
    name="sziklai_pair",
    display_name="Sziklai 互补对",
    description="NPN→PNP: Q_NPN.E=Q_PNP.B, Q_NPN.C=Q_PNP.E",
    roles=[
        Role("Q_NPN", "Q", "NPN"),
        Role("Q_PNP", "Q", "PNP"),
    ],
    constraints=[
        SameNet(pin("Q_NPN", 2), pin("Q_PNP", 1)),   # E_NPN = B_PNP
        SameNet(pin("Q_NPN", 0), pin("Q_PNP", 2)),   # C_NPN = E_PNP
    ],
    external_ports=[
        ExternalPort("IN",  pin("Q_NPN", 1), "input"),
        ExternalPort("C",   pin("Q_NPN", 0), "output"),
        ExternalPort("OUT", pin("Q_PNP", 0), "output"),
    ],
    skin_type="sziklai_pair",
    priority=8,
)


# ===================================================================
# 7. Vbe 乘法器 (Vbe Multiplier)
# ===================================================================
#
# 拓扑: Q.C→TOP, Q.E→BOT, R1: TOP↔Q.B, R2: Q.B↔BOT
#
#        TOP ─── R1 ─── NB ─── R2 ─── BOT
#         |              |              |
#         └──── Q.C     Q.B       Q.E ──┘
# -------------------------------------------------------------------

VBE_MULTIPLIER = PatternDef(
    name="vbe_multiplier",
    display_name="Vbe 乘法器",
    description="一个 BJT + 两个电阻: R1(C↔B), R2(B↔E)",
    roles=[
        Role("Q", "Q"),           # NPN 或 PNP 均可
        Role("R1", "R"),          # C-B 之间的电阻
        Role("R2", "R"),          # B-E 之间的电阻
    ],
    constraints=[
        # R1 的一端连 Q.C, 另一端连 Q.B
        # R1: pin0=一端, pin1=另一端 → 需要 (R1.0=Q.C 且 R1.1=Q.B) 或 (R1.0=Q.B 且 R1.1=Q.C)
        # 简单处理: 只检查 R1 的两端分别连接 Q.C 和 Q.B 的网络
        # 由于电阻无极性, 我们需要灵活处理

        # 方案: 用 SameNet 约束, 但电阻引脚顺序不确定
        # 这里假设 R1.0 连 Q.C (top), R1.1 连 Q.B (mid)
        SameNet(pin("R1", 0), pin("Q", 0)),   # R1.A = Q.C
        SameNet(pin("R1", 1), pin("Q", 1)),   # R1.B = Q.B
        SameNet(pin("R2", 0), pin("Q", 1)),   # R2.A = Q.B
        SameNet(pin("R2", 1), pin("Q", 2)),   # R2.B = Q.E
    ],
    external_ports=[
        ExternalPort("TOP", pin("Q", 0), "input"),
        ExternalPort("BOT", pin("Q", 2), "output"),
    ],
    skin_type="vbe_multiplier",
    priority=12,   # 较高优先级 (3个元件)
)

# Vbe 乘法器 — 电阻极性翻转的变体
# 因为 SPICE 中电阻 R N1 N2 的引脚顺序取决于网表书写顺序
VBE_MULTIPLIER_V2 = PatternDef(
    name="vbe_multiplier",       # 同名, 匹配时都算 vbe_multiplier
    display_name="Vbe 乘法器",
    description="Vbe 乘法器 (R1 引脚翻转)",
    roles=[
        Role("Q", "Q"),
        Role("R1", "R"),
        Role("R2", "R"),
    ],
    constraints=[
        SameNet(pin("R1", 1), pin("Q", 0)),   # R1.B = Q.C  (翻转)
        SameNet(pin("R1", 0), pin("Q", 1)),   # R1.A = Q.B
        SameNet(pin("R2", 0), pin("Q", 1)),   # R2.A = Q.B
        SameNet(pin("R2", 1), pin("Q", 2)),   # R2.B = Q.E
    ],
    external_ports=[
        ExternalPort("TOP", pin("Q", 0), "input"),
        ExternalPort("BOT", pin("Q", 2), "output"),
    ],
    skin_type="vbe_multiplier",
    priority=12,
)

VBE_MULTIPLIER_V3 = PatternDef(
    name="vbe_multiplier",
    display_name="Vbe 乘法器",
    description="Vbe 乘法器 (R2 引脚翻转)",
    roles=[
        Role("Q", "Q"),
        Role("R1", "R"),
        Role("R2", "R"),
    ],
    constraints=[
        SameNet(pin("R1", 0), pin("Q", 0)),
        SameNet(pin("R1", 1), pin("Q", 1)),
        SameNet(pin("R2", 1), pin("Q", 1)),   # R2.B = Q.B  (翻转)
        SameNet(pin("R2", 0), pin("Q", 2)),   # R2.A = Q.E
    ],
    external_ports=[
        ExternalPort("TOP", pin("Q", 0), "input"),
        ExternalPort("BOT", pin("Q", 2), "output"),
    ],
    skin_type="vbe_multiplier",
    priority=12,
)

VBE_MULTIPLIER_V4 = PatternDef(
    name="vbe_multiplier",
    display_name="Vbe 乘法器",
    description="Vbe 乘法器 (R1+R2 均翻转)",
    roles=[
        Role("Q", "Q"),
        Role("R1", "R"),
        Role("R2", "R"),
    ],
    constraints=[
        SameNet(pin("R1", 1), pin("Q", 0)),
        SameNet(pin("R1", 0), pin("Q", 1)),
        SameNet(pin("R2", 1), pin("Q", 1)),
        SameNet(pin("R2", 0), pin("Q", 2)),
    ],
    external_ports=[
        ExternalPort("TOP", pin("Q", 0), "input"),
        ExternalPort("BOT", pin("Q", 2), "output"),
    ],
    skin_type="vbe_multiplier",
    priority=12,
)


# ===================================================================
# 8. 互补推挽输出 (Push-Pull)
# ===================================================================
#
# 拓扑: NPN.C→正电源, PNP.C→负电源/地, E 不接电源 (接负载)
#
#        VCC
#         |
#       [Q_N]  ← NPN
#         |E
#        OUT
#         |E
#       [Q_P]  ← PNP
#         |
#        VEE/GND
# -------------------------------------------------------------------

PUSH_PULL_BJT = PatternDef(
    name="push_pull_bjt",
    display_name="BJT 推挽输出",
    description="NPN+PNP 互补: NPN.C→VCC, PNP.C→VEE/GND, E→负载",
    roles=[
        Role("Q_N", "Q", "NPN"),
        Role("Q_P", "Q", "PNP"),
    ],
    constraints=[
        NetIs(pin("Q_N", 0), "pos_supply"),       # NPN.C → VCC
        NetIs(pin("Q_P", 0), "any_power"),         # PNP.C → VEE/GND (某电源)
        NetIsNot(pin("Q_N", 2), "any_power"),     # NPN.E 不接电源
        NetIsNot(pin("Q_P", 2), "any_power"),     # PNP.E 不接电源
        DiffNet(pin("Q_N", 0), pin("Q_P", 0)),   # NPN.C ≠ PNP.C (不同电源)
    ],
    external_ports=[
        ExternalPort("IN_HI",  pin("Q_N", 1), "input"),
        ExternalPort("IN_LO",  pin("Q_P", 1), "input"),
        ExternalPort("OUT_HI", pin("Q_N", 2), "output"),
        ExternalPort("OUT_LO", pin("Q_P", 2), "output"),
        ExternalPort("SUPPLY_HI", pin("Q_N", 0), "input"),   # NPN.C → VCC
        ExternalPort("SUPPLY_LO", pin("Q_P", 0), "output"),  # PNP.C → VEE/GND
    ],
    skin_type="push_pull_bjt",
    priority=5,
)

PUSH_PULL_MOS = PatternDef(
    name="push_pull_mos",
    display_name="MOS 推挽输出",
    description="NMOS+PMOS 互补: NMOS.D→VCC(via), PMOS.D→VSS",
    roles=[
        Role("M_N", "M", "NMOS"),
        Role("M_P", "M", "PMOS"),
    ],
    constraints=[
        NetIsNot(pin("M_N", 2), "any_power"),     # NMOS.S 不接电源
        NetIsNot(pin("M_P", 2), "any_power"),     # PMOS.S 不接电源
    ],
    external_ports=[
        ExternalPort("IN_HI",  pin("M_N", 1), "input"),
        ExternalPort("IN_LO",  pin("M_P", 1), "input"),
        ExternalPort("OUT_HI", pin("M_N", 2), "output"),
        ExternalPort("OUT_LO", pin("M_P", 2), "output"),
        ExternalPort("SUPPLY_HI", pin("M_N", 0), "input"),   # NMOS.D → VDD
        ExternalPort("SUPPLY_LO", pin("M_P", 0), "output"),  # PMOS.D → VSS
    ],
    skin_type="push_pull_mos",
    priority=5,
)


# ===================================================================
# 9. Wilson 电流镜
# ===================================================================
#
# 拓扑: 3 个晶体管
#   Q1 (二极管接法) + Q2 (镜像) + Q3 (cascode/feedback)
#   Q3.E = Q1.C = Q2.C 的连接点, Q3.C = 输出
#   Q1.B = Q2.B = Q3.C
#
#          IN ──→ Q1.C=Q1.B ──→ Q2.B
#                     |              |
#                   Q3.E           Q2.C
#                     |
#                   Q3.C → OUT
#                     |
#                   Q3.B ← Q2.C? (这个拓扑比较复杂, 简化处理)
# -------------------------------------------------------------------

WILSON_MIRROR_NPN = PatternDef(
    name="wilson_mirror_npn",
    display_name="NPN Wilson 电流镜",
    description="3-NPN Wilson: Q1二极管+Q2镜像+Q3反馈",
    roles=[
        Role("Q1", "Q", "NPN"),   # 二极管接法
        Role("Q2", "Q", "NPN"),   # 镜像管
        Role("Q3", "Q", "NPN"),   # 反馈管
    ],
    constraints=[
        # Q1 二极管接法
        SameNet(pin("Q1", 0), pin("Q1", 1)),   # C1 = B1
        # Q1.B = Q2.B (共享基极)
        SameNet(pin("Q1", 1), pin("Q2", 1)),
        # Q3.E = Q2.C (反馈连接)
        SameNet(pin("Q3", 2), pin("Q2", 0)),
        # Q3.B 连到输入侧 (Q1.C 所在网络)
        SameNet(pin("Q3", 1), pin("Q1", 0)),
        # Q1.E = Q2.E (共享 emitter rail)
        SameNet(pin("Q1", 2), pin("Q2", 2)),
    ],
    external_ports=[
        ExternalPort("IN",   pin("Q3", 2), "input"),    # 其实是 Q2.C = Q3.E
        ExternalPort("OUT",  pin("Q3", 0), "output"),
        ExternalPort("RAIL", pin("Q1", 2), "output"),
    ],
    skin_type="wilson_mirror_npn",
    priority=15,   # 3个元件, 高优先级
)


# ===================================================================
# 10. 差分对 + 有源负载 (4 晶体管)
# ===================================================================
#
# 拓扑: NPN 差分对 + PNP 电流镜负载
#   Q1.C=Q3.C (OUTP), Q2.C=Q4.C (OUTN)
#   Q3.B=Q4.B=Q3.C (mirror, 二极管接法)
#   Q3.E=Q4.E=VCC
#   Q1.E=Q2.E=TAIL
# -------------------------------------------------------------------

DIFF_PAIR_ACTIVE_LOAD_NPN = PatternDef(
    name="diff_pair_active_load_npn",
    display_name="NPN 差分对+有源负载",
    description="NPN 差分对 + PNP 电流镜负载 (4管)",
    roles=[
        Role("QL", "Q", "NPN"),    # 差分对左
        Role("QR", "Q", "NPN"),    # 差分对右
        Role("QML", "Q", "PNP"),   # 镜像负载左 (二极管接法)
        Role("QMR", "Q", "PNP"),   # 镜像负载右
    ],
    constraints=[
        # 差分对约束
        SameNet(pin("QL", 2), pin("QR", 2)),     # 共享 E
        DiffNet(pin("QL", 1), pin("QR", 1)),     # 不同 B
        DiffNet(pin("QL", 0), pin("QR", 0)),     # 不同 C
        DiffNet(pin("QL", 1), pin("QR", 0)),     # 反交叉
        DiffNet(pin("QR", 1), pin("QL", 0)),
        # 电流镜约束
        SameNet(pin("QML", 1), pin("QMR", 1)),   # 共享 B
        SameNet(pin("QML", 2), pin("QMR", 2)),   # 共享 E
        SameNet(pin("QML", 0), pin("QML", 1)),   # QML 二极管接法
        # 负载连接
        SameNet(pin("QL", 0), pin("QML", 0)),    # QL.C = QML.C
        SameNet(pin("QR", 0), pin("QMR", 0)),    # QR.C = QMR.C
    ],
    external_ports=[
        ExternalPort("INP",  pin("QL", 1), "input"),
        ExternalPort("INN",  pin("QR", 1), "input"),
        ExternalPort("OUT",  pin("QR", 0), "output"),     # 输出取镜像侧
        ExternalPort("TAIL", pin("QL", 2), "output"),
        ExternalPort("VCC",  pin("QML", 2), "input"),
        ExternalPort("MIRR", pin("QL", 0), "output"),     # 镜像参考节点 (QL.C=QML.C=QML.B)
    ],
    skin_type="diff_pair_active_load_npn",
    priority=20,   # 4 管, 最高优先级
)

DIFF_PAIR_ACTIVE_LOAD_PNP = PatternDef(
    name="diff_pair_active_load_pnp",
    display_name="PNP 差分对+有源负载",
    description="PNP 差分对 + NPN 电流镜负载 (4管)",
    roles=[
        Role("QL", "Q", "PNP"),
        Role("QR", "Q", "PNP"),
        Role("QML", "Q", "NPN"),   # 镜像负载
        Role("QMR", "Q", "NPN"),
    ],
    constraints=[
        SameNet(pin("QL", 2), pin("QR", 2)),
        DiffNet(pin("QL", 1), pin("QR", 1)),
        DiffNet(pin("QL", 0), pin("QR", 0)),
        DiffNet(pin("QL", 1), pin("QR", 0)),
        DiffNet(pin("QR", 1), pin("QL", 0)),
        SameNet(pin("QML", 1), pin("QMR", 1)),
        SameNet(pin("QML", 2), pin("QMR", 2)),
        SameNet(pin("QML", 0), pin("QML", 1)),
        SameNet(pin("QL", 0), pin("QML", 0)),
        SameNet(pin("QR", 0), pin("QMR", 0)),
    ],
    external_ports=[
        ExternalPort("INP",  pin("QL", 1), "input"),
        ExternalPort("INN",  pin("QR", 1), "input"),
        ExternalPort("OUT",  pin("QR", 0), "output"),
        ExternalPort("TAIL", pin("QL", 2), "input"),
        ExternalPort("VSS",  pin("QML", 2), "output"),
        ExternalPort("MIRR", pin("QL", 0), "output"),     # 镜像参考节点 (QL.C=QML.C=QML.B)
    ],
    skin_type="diff_pair_active_load_pnp",
    priority=20,
)


# ===================================================================
# 11. 射极跟随器 + 电流源 (Emitter Follower with Bias)
# ===================================================================
#
# 拓扑: Q.C→电源, Q.B=信号, Q.E→输出+电流源
# 这个太简单, 先不做 (容易误匹配)
# ===================================================================


# ===================================================================
# 汇总所有模式
# ===================================================================

ALL_PATTERNS: list[PatternDef] = [
    # 大模式优先 (4管)
    DIFF_PAIR_ACTIVE_LOAD_NPN,
    DIFF_PAIR_ACTIVE_LOAD_PNP,

    # Wilson (3管)
    WILSON_MIRROR_NPN,

    # Vbe 乘法器 (3个元件, 多种引脚排列)
    VBE_MULTIPLIER,
    VBE_MULTIPLIER_V2,
    VBE_MULTIPLIER_V3,
    VBE_MULTIPLIER_V4,

    # 交叉耦合 (比差分对优先级高)
    CROSS_COUPLED_NPN,
    CROSS_COUPLED_NMOS,

    # 差分对
    DIFF_PAIR_NPN,
    DIFF_PAIR_PNP,
    DIFF_PAIR_NMOS,
    DIFF_PAIR_PMOS,

    # 电流镜
    CURRENT_MIRROR_NPN,
    CURRENT_MIRROR_PNP,
    CURRENT_MIRROR_NMOS,
    CURRENT_MIRROR_PMOS,

    # Cascode
    CASCODE_NPN,
    CASCODE_PNP,
    CASCODE_NMOS,
    CASCODE_PMOS,

    # Darlington
    DARLINGTON_NPN,
    DARLINGTON_PNP,

    # Sziklai
    SZIKLAI_NPN_PNP,

    # 推挽
    PUSH_PULL_BJT,
    PUSH_PULL_MOS,
]

# 方便用户按名称选择模式子集
PATTERN_BY_NAME: dict[str, list[PatternDef]] = {}
for _p in ALL_PATTERNS:
    PATTERN_BY_NAME.setdefault(_p.name, []).append(_p)
