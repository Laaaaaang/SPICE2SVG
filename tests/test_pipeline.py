"""端到端集成测试。"""

import json
import pytest
from spice2svg.parser import parse
from spice2svg.generator import generate_skidl_code
from spice2svg.renderer import circuit_to_json_string


# ---- 测试电路 ----

RC_LOWPASS = """\
* RC Low-Pass Filter
R1 VIN VOUT 10k
C1 VOUT 0 10nF
.end
"""

VOLTAGE_DIVIDER = """\
* Voltage Divider
R1 VIN VOUT 10k
R2 VOUT 0 10k
.end
"""

RLC_BANDPASS = """\
* RLC Band-Pass Filter
R1 VIN N001 1k
L1 N001 VOUT 10mH
C1 N001 0 100nF
.end
"""

CE_AMP = """\
* Common Emitter Amplifier
.model 2N2222 NPN (BF=200 IS=1e-14)
VCC VCC 0 12
RB VIN BASE 100k
RC VCC VOUT 4.7k
RE EMITTER 0 1k
Q1 VOUT BASE EMITTER 2N2222
.end
"""

CMOS_INV = """\
* CMOS Inverter
.model PMOD PMOS (VTO=-0.7 KP=50u)
.model NMOD NMOS (VTO=0.7 KP=110u)
VDD VDD 0 5
M1 VOUT VIN VDD VDD PMOD W=2u L=0.18u
M2 VOUT VIN 0 0 NMOD W=1u L=0.18u
.end
"""

CIRCUITS = [
    ("rc_lowpass",       RC_LOWPASS,       2, 3),
    ("voltage_divider",  VOLTAGE_DIVIDER,  2, 3),
    ("rlc_bandpass",     RLC_BANDPASS,     3, 4),
    ("ce_amp",           CE_AMP,           5, 6),
    ("cmos_inv",         CMOS_INV,         3, 4),
]


class TestEndToEnd:
    @pytest.fixture(params=CIRCUITS, ids=lambda p: p[0])
    def cdata(self, request):
        return request.param

    def test_parse(self, cdata):
        name, text, n_comp, n_net = cdata
        circuit = parse(text, name=name)
        assert len(circuit.components) == n_comp
        assert len(circuit.nets) == n_net

    def test_codegen_compiles(self, cdata):
        name, text, *_ = cdata
        code = generate_skidl_code(parse(text, name=name))
        compile(code, f"<{name}>", "exec")

    def test_json_valid(self, cdata):
        name, text, *_ = cdata
        data = json.loads(circuit_to_json_string(parse(text, name=name)))
        assert len(data["modules"][""]["cells"]) > 0

    def test_full_chain(self, cdata):
        name, text, n_comp, _ = cdata
        circuit = parse(text, name=name)
        assert len(circuit.components) == n_comp

        code = generate_skidl_code(circuit)
        compile(code, f"<{name}>", "exec")

        data = json.loads(circuit_to_json_string(circuit))
        assert len(data["modules"][""]["cells"]) == n_comp

        assert name in circuit.summary()
