"""SVG 渲染器 / JSON 转换器测试。"""

import json
import pytest
from spice2svg.parser import parse
from spice2svg.renderer import circuit_to_netlistsvg_json, circuit_to_json_string


class TestJsonConverter:
    def test_basic_structure(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        assert "modules" in data
        assert "" in data["modules"]
        assert "cells" in data["modules"][""]
        assert "ports" in data["modules"][""]

    def test_cells_content(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        cells = data["modules"][""]["cells"]
        assert "R1" in cells
        assert "C1" in cells
        assert cells["R1"]["type"] == "R_2_"
        assert cells["R1"]["attributes"]["value"] == "10k"

    def test_shared_net_bits(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        cells = data["modules"][""]["cells"]
        r1_vout = cells["R1"]["connections"]["2"][0]
        c1_vout = cells["C1"]["connections"]["1"][0]  # pin.number = 1
        assert r1_vout == c1_vout

    def test_ports(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        ports = data["modules"][""]["ports"]
        assert "VIN" in ports
        assert ports["VIN"]["direction"] == "input"
        assert "GND" not in ports

    def test_json_string_valid(self):
        text = "R1 VIN VOUT 10k\n.end"
        circuit = parse(text)
        data = json.loads(circuit_to_json_string(circuit))
        assert "modules" in data

    def test_series_resistors(self):
        text = "R1 A B 10k\nR2 B C 20k\n.end"
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        cells = data["modules"][""]["cells"]
        assert cells["R1"]["connections"]["2"][0] == cells["R2"]["connections"]["1"][0]  # net B shared

    def test_complex_json(self):
        text = """\
VCC VCC 0 12
RB VIN BASE 100k
RC VCC VOUT 4.7k
Q1 VOUT BASE EMITTER 2N2222
RE EMITTER 0 1k
.end
"""
        circuit = parse(text)
        data, _ = circuit_to_netlistsvg_json(circuit)
        cells = data["modules"][""]["cells"]
        assert len(cells) == 5
