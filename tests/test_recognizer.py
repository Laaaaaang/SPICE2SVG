"""超节点识别器测试。"""

import json
import pytest
from spice2svg.parser import parse, parse_file
from spice2svg.recognizer import recognize_supernodes, ALL_PATTERNS, SuperNode
from spice2svg.recognizer.pattern_def import (
    PatternDef, Role, ExternalPort, pin,
    SameNet, DiffNet, NetIs, NetIsNot,
)
from spice2svg.renderer.json_converter import (
    circuit_to_json_string,
    circuit_to_netlistsvg_json_with_supernodes,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _recognize(spice_text: str, patterns=None):
    """解析 SPICE 文本并运行超节点识别。"""
    circuit = parse(spice_text)
    return circuit, recognize_supernodes(circuit, patterns or ALL_PATTERNS)


# ---------------------------------------------------------------------------
# 差分对识别
# ---------------------------------------------------------------------------

class TestDiffPair:
    """差分对识别测试。"""

    NPN_DIFF_PAIR = """\
Q1 C1 INP TAIL NPN_MOD
Q2 C2 INN TAIL NPN_MOD
ITAIL TAIL 0 DC 1m
.model NPN_MOD NPN
.end
"""

    def test_npn_diff_pair_recognized(self):
        circuit, sn = _recognize(self.NPN_DIFF_PAIR)
        dp = [s for s in sn if "diff_pair" in s.pattern_name]
        assert len(dp) == 1
        assert set(dp[0].component_refs) == {"Q1", "Q2"}

    def test_diff_pair_external_ports(self):
        _, sn = _recognize(self.NPN_DIFF_PAIR)
        dp = [s for s in sn if "diff_pair" in s.pattern_name][0]
        assert "INP" in dp.external_ports
        assert "INN" in dp.external_ports
        assert "OUTP" in dp.external_ports
        assert "OUTN" in dp.external_ports
        assert "TAIL" in dp.external_ports
        assert dp.external_ports["INP"][0] == "INP"
        assert dp.external_ports["INN"][0] == "INN"

    def test_cross_coupled_not_diff_pair(self):
        """交叉耦合对不应被识别为差分对。"""
        text = """\
Q1 OUTP OUTN TAIL NPN_MOD
Q2 OUTN OUTP TAIL NPN_MOD
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        dp = [s for s in sn if "diff_pair" in s.pattern_name]
        assert len(dp) == 0
        # 应该被识别为交叉耦合
        xc = [s for s in sn if "cross_coupled" in s.pattern_name]
        assert len(xc) == 1

    def test_pnp_diff_pair(self):
        text = """\
Q3 C2P IN2P TAIL2 PNP_MOD
Q4 C2N IN2N TAIL2 PNP_MOD
.model PNP_MOD PNP
.end
"""
        _, sn = _recognize(text)
        dp = [s for s in sn if s.pattern_name == "diff_pair_pnp"]
        assert len(dp) == 1


# ---------------------------------------------------------------------------
# 电流镜识别
# ---------------------------------------------------------------------------

class TestCurrentMirror:
    def test_npn_mirror(self):
        text = """\
Q1 NET_B NET_B 0 NPN_MOD
Q2 OUT NET_B 0 NPN_MOD
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        cm = [s for s in sn if "current_mirror" in s.pattern_name]
        assert len(cm) == 1
        assert cm[0].role_mapping.get("QREF") == "Q1"  # 二极管接法为参考管

    def test_pmos_mirror(self):
        text = """\
M1 NET_G NET_G VDD VDD PMOS_MOD
M2 OUT NET_G VDD VDD PMOS_MOD
.model PMOS_MOD PMOS
.end
"""
        _, sn = _recognize(text)
        cm = [s for s in sn if "current_mirror" in s.pattern_name]
        assert len(cm) == 1


# ---------------------------------------------------------------------------
# Vbe 乘法器识别
# ---------------------------------------------------------------------------

class TestVbeMultiplier:
    def test_vbe_multiplier(self):
        text = """\
QBIAS BUP NB BDN NPN_MOD
RB1 BUP NB 2.7k
RB2 NB BDN 1k
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        vbe = [s for s in sn if "vbe_multiplier" in s.pattern_name]
        assert len(vbe) == 1
        assert set(vbe[0].component_refs) == {"QBIAS", "RB1", "RB2"}
        # NB 应该是内部网络
        assert "NB" in vbe[0].internal_nets

    def test_vbe_external_ports(self):
        text = """\
QBIAS BUP NB BDN NPN_MOD
RB1 BUP NB 2.7k
RB2 NB BDN 1k
CEXT BUP BDN 100p
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        vbe = [s for s in sn if "vbe_multiplier" in s.pattern_name][0]
        assert vbe.external_ports["TOP"][0] == "BUP"
        assert vbe.external_ports["BOT"][0] == "BDN"


# ---------------------------------------------------------------------------
# 推挽识别
# ---------------------------------------------------------------------------

class TestPushPull:
    def test_push_pull_bjt(self):
        text = """\
QOUTU VCC BOUTU EOUTU NPN_OUT
QOUTL VEE BOUTL EOUTL PNP_OUT
REU EOUTU OUT 0.22
REL EOUTL OUT 0.22
.model NPN_OUT NPN
.model PNP_OUT PNP
.end
"""
        _, sn = _recognize(text)
        pp = [s for s in sn if "push_pull" in s.pattern_name]
        assert len(pp) == 1


# ---------------------------------------------------------------------------
# Cascode 识别
# ---------------------------------------------------------------------------

class TestCascode:
    def test_npn_cascode(self):
        text = """\
Q1 MID IN1 GND NPN_MOD
Q2 OUT VBIAS MID NPN_MOD
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        cas = [s for s in sn if "cascode" in s.pattern_name]
        assert len(cas) == 1
        assert cas[0].role_mapping.get("Q_LO") == "Q1"
        assert cas[0].role_mapping.get("Q_HI") == "Q2"


# ---------------------------------------------------------------------------
# Darlington 识别
# ---------------------------------------------------------------------------

class TestDarlington:
    def test_darlington_npn(self):
        text = """\
Q1 VCC IN MID NPN_MOD
Q2 VCC MID OUT NPN_MOD
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        drl = [s for s in sn if "darlington" in s.pattern_name]
        assert len(drl) == 1


# ---------------------------------------------------------------------------
# 贪心匹配 — 同一元件不会被多个超节点重复使用
# ---------------------------------------------------------------------------

class TestGreedy:
    def test_no_double_assignment(self):
        """每个元件只属于一个超节点。"""
        text = """\
Q1 C1 IN1 TAIL NPN_MOD
Q2 C2 IN2 TAIL NPN_MOD
Q3 C3 IN3 TAIL NPN_MOD
.model NPN_MOD NPN
.end
"""
        _, sn = _recognize(text)
        all_refs = []
        for s in sn:
            all_refs.extend(s.component_refs)
        # 没有重复
        assert len(all_refs) == len(set(all_refs))


# ---------------------------------------------------------------------------
# JSON 集成
# ---------------------------------------------------------------------------

class TestJsonIntegration:
    def test_supernode_in_json(self):
        text = """\
Q1 C1 INP TAIL NPN_MOD
Q2 C2 INN TAIL NPN_MOD
R1 VCC C1 10k
R2 VCC C2 10k
.model NPN_MOD NPN
.end
"""
        circuit = parse(text)
        sn = recognize_supernodes(circuit, ALL_PATTERNS)
        assert len(sn) >= 1

        json_str = circuit_to_json_string(circuit, supernodes=sn)
        data = json.loads(json_str)
        cells = data["modules"][""]["cells"]

        # 超节点 cell 存在
        sn_cells = [c for c in cells.values()
                     if c["type"].startswith("diff_pair")]
        assert len(sn_cells) == 1

        # Q1, Q2 不再作为独立 cell
        assert "Q1" not in cells
        assert "Q2" not in cells

        # 超节点 cell 有正确的端口
        dp_cell = sn_cells[0]
        assert "INP" in dp_cell["connections"]
        assert "INN" in dp_cell["connections"]
        assert "OUTP" in dp_cell["connections"]
        assert "OUTN" in dp_cell["connections"]

    def test_no_supernodes_same_as_original(self):
        """supernodes=None 时行为与原始相同。"""
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        json_with = circuit_to_json_string(circuit, supernodes=None)
        json_without = circuit_to_json_string(circuit)
        assert json_with == json_without

    def test_internal_nets_absorbed(self):
        """Vbe 乘法器的内部网络 NB 不应出现在 JSON 的 port 中。"""
        text = """\
QBIAS BUP NB BDN NPN_MOD
RB1 BUP NB 2.7k
RB2 NB BDN 1k
.model NPN_MOD NPN
.end
"""
        circuit = parse(text)
        sn = recognize_supernodes(circuit, ALL_PATTERNS)
        json_str = circuit_to_json_string(circuit, supernodes=sn)
        data = json.loads(json_str)
        ports = data["modules"][""]["ports"]
        # NB 是内部网络, 不应出现在 ports 中
        assert "NB" not in ports


# ---------------------------------------------------------------------------
# 端到端: 用 5.cir 测试
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_5cir_recognition(self):
        """5.cir 应识别出差分对、Vbe乘法器、推挽。"""
        circuit = parse_file("examples/5.cir")
        sn = recognize_supernodes(circuit, ALL_PATTERNS)
        names = {s.pattern_name for s in sn}
        assert "diff_pair_npn" in names
        assert "diff_pair_pnp" in names
        assert "vbe_multiplier" in names
        assert "push_pull_bjt" in names

    def test_2cir_recognition(self):
        """2.cir 应识别出 NMOS 差分对和 PMOS 电流镜。"""
        circuit = parse_file("examples/2.cir")
        sn = recognize_supernodes(circuit, ALL_PATTERNS)
        names = {s.pattern_name for s in sn}
        assert "diff_pair_nmos" in names
        assert "current_mirror_pmos" in names

    def test_1cir_active_load(self):
        """1.cir 应识别出差分对+有源负载 (4管)。"""
        circuit = parse_file("examples/1.cir")
        sn = recognize_supernodes(circuit, ALL_PATTERNS)
        names = {s.pattern_name for s in sn}
        assert "diff_pair_active_load_npn" in names
