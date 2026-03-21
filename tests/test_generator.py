"""SKiDL 代码生成器测试。"""

import pytest
from spice2svg.parser import parse
from spice2svg.generator import generate_skidl_code


class TestGenerateSkidlCode:
    def test_basic_rc(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text, name="rc_test")
        code = generate_skidl_code(circuit)

        assert "from skidl import" in code
        assert "_make_template" in code
        assert "r_template" in code
        assert "c_template" in code
        assert 'Net("VIN")' in code
        assert 'Net("VOUT")' in code
        assert 'Net("GND")' in code
        assert "R1 = r_template(value='10k')" in code
        assert "C1 = c_template(value='10nF')" in code
        assert "R1[1] += net_VIN" in code
        assert "R1[2] += net_VOUT" in code
        assert "C1[1] += net_VOUT" in code
        assert "C1[2] += net_GND" in code
        assert "ERC()" in code
        assert "generate_netlist()" in code
        assert "generate_svg()" in code

    def test_net_directions(self):
        text = "R1 VIN VOUT 10k\n.end"
        circuit = parse(text)
        code = generate_skidl_code(circuit)
        assert 'netio = "i"' in code
        assert 'netio = "o"' in code

    def test_code_is_valid_python(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        code = generate_skidl_code(circuit)
        compile(code, "<test>", "exec")  # 语法检查

    def test_complex_circuit(self):
        text = """\
* CE Amp
.model 2N2222 NPN (BF=200)
VCC VCC 0 12
RB VIN BASE 100k
RC VCC VOUT 4.7k
RE EMITTER 0 1k
Q1 VOUT BASE EMITTER 2N2222
.end
"""
        circuit = parse(text)
        code = generate_skidl_code(circuit)
        assert "q_template" in code
        assert "v_template" in code
        assert "r_template" in code
        compile(code, "<test>", "exec")

    def test_mosfet_circuit(self):
        text = """\
.model NMOD NMOS (VTO=0.7)
VDD VDD 0 5
M1 VOUT VIN VDD VDD NMOD W=1u L=0.18u
.end
"""
        circuit = parse(text)
        code = generate_skidl_code(circuit)
        assert "m_template" in code
        compile(code, "<test>", "exec")
