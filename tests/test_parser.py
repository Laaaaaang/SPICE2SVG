"""SPICE 解析器测试。"""

import pytest
from spice2svg.parser import parse


class TestParseBasic:
    def test_rc_lowpass(self):
        text = """\
* RC Low-Pass Filter
R1 VIN VOUT 10k
C1 VOUT 0 10nF
.end
"""
        circuit = parse(text, name="rc_lowpass")
        assert circuit.name == "rc_lowpass"
        assert len(circuit.components) == 2
        assert circuit.components[0].ref == "R1"
        assert circuit.components[0].type == "R"
        assert circuit.components[0].value == "10k"
        assert circuit.components[1].ref == "C1"
        assert circuit.components[1].value == "10nF"

    def test_nets_built(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        assert "VIN" in circuit.nets
        assert "VOUT" in circuit.nets
        assert "GND" in circuit.nets  # "0" → "GND"

    def test_ground_normalized(self):
        text = "R1 A 0 10k\n.end"
        circuit = parse(text)
        assert circuit.components[0].pins[1].net_name == "GND"

    def test_net_connections(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        assert circuit.nets["VOUT"].connection_count == 2

    def test_title_extracted(self):
        text = "* My Great Circuit\nR1 A B 10k\n.end"
        circuit = parse(text)
        assert "My Great Circuit" in circuit.title


class TestParseModels:
    def test_model_parsing(self):
        text = ".model 2N2222 NPN (BF=200 IS=1e-14)\nQ1 C B E 2N2222\n.end"
        circuit = parse(text)
        assert "2N2222" in circuit.models
        assert circuit.models["2N2222"].type == "NPN"
        assert circuit.models["2N2222"].params.get("BF") == "200"

    def test_bjt_parsing(self):
        text = "Q1 C B E 2N2222\n.end"
        circuit = parse(text)
        q1 = circuit.components[0]
        assert q1.type == "Q"
        assert q1.pin_count == 3
        assert q1.pins[0].net_name == "C"
        assert q1.pins[1].net_name == "B"
        assert q1.pins[2].net_name == "E"

    def test_mosfet_parsing(self):
        text = "M1 VOUT VIN VDD VDD PMOD W=2u L=0.18u\n.end"
        circuit = parse(text)
        m1 = circuit.components[0]
        assert m1.type == "M"
        assert m1.pin_count == 4
        assert m1.value == "PMOD"
        assert m1.properties.get("W") == "2u"
        assert m1.properties.get("L") == "0.18u"


class TestParseVoltageSource:
    def test_simple_source(self):
        text = "VCC VCC 0 12\n.end"
        circuit = parse(text)
        vcc = circuit.components[0]
        assert vcc.type == "V"
        assert vcc.ref == "VCC"
        assert vcc.pins[0].net_name == "VCC"
        assert vcc.pins[1].net_name == "GND"

    def test_dc_source(self):
        text = "V1 VCC 0 DC 5\n.end"
        circuit = parse(text)
        v1 = circuit.components[0]
        assert v1.value == "5"
        assert v1.properties.get("source_type") == "DC"


class TestParseDiode:
    def test_diode(self):
        text = "D1 A K 1N4148\n.end"
        circuit = parse(text)
        d1 = circuit.components[0]
        assert d1.type == "D"
        assert d1.pin_count == 2
        assert d1.pins[0].name == "A"
        assert d1.pins[1].name == "K"


class TestParseComplex:
    def test_common_emitter(self):
        text = """\
* Common Emitter Amplifier
.model 2N2222 NPN (BF=200 IS=1e-14)
VCC VCC 0 12
RB VIN BASE 100k
RC VCC VOUT 4.7k
RE EMITTER 0 1k
Q1 VOUT BASE EMITTER 2N2222
.end
"""
        circuit = parse(text, name="ce_amp")
        assert len(circuit.components) == 5
        assert len(circuit.models) == 1
        assert {c.type for c in circuit.components} == {"V", "R", "Q"}

    def test_cmos_inverter(self):
        text = """\
* CMOS Inverter
.model PMOD PMOS (VTO=-0.7 KP=50u)
.model NMOD NMOS (VTO=0.7 KP=110u)
VDD VDD 0 5
M1 VOUT VIN VDD VDD PMOD W=2u L=0.18u
M2 VOUT VIN 0 0 NMOD W=1u L=0.18u
.end
"""
        circuit = parse(text)
        assert len(circuit.components) == 3
        assert len(circuit.models) == 2
        m1 = circuit.get_component("M1")
        assert m1 is not None
        assert m1.pin_count == 4

    def test_voltage_divider(self):
        text = "R1 VIN VOUT 10k\nR2 VOUT 0 10k\n.end"
        circuit = parse(text)
        assert len(circuit.components) == 2
        assert circuit.nets["VOUT"].connection_count == 2

    def test_rlc_bandpass(self):
        text = """\
R1 VIN N001 1k
L1 N001 VOUT 10mH
C1 N001 0 100nF
.end
"""
        circuit = parse(text)
        assert len(circuit.components) == 3
        assert "L" in circuit.component_types()
        assert circuit.nets["N001"].connection_count == 3


class TestValidation:
    def test_single_connection_warning(self):
        text = "R1 VIN VOUT 10k\n.end"
        circuit = parse(text)
        warnings = circuit.validate()
        assert any("VIN" in w for w in warnings)
