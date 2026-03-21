"""中间表示模型测试。"""

import pytest
from spice2svg.models import Circuit, Component, Pin, Net, NetConnection, classify_net


class TestPin:
    def test_create(self):
        p = Pin(number=1, name="A", net_name="VIN")
        assert p.number == 1
        assert p.name == "A"
        assert p.net_name == "VIN"


class TestComponent:
    def test_create(self):
        c = Component(
            type="R", ref="R1", value="10k",
            pins=[Pin(1, "1", "VIN"), Pin(2, "2", "VOUT")],
        )
        assert c.type == "R"
        assert c.pin_count == 2
        assert c.net_names() == ["VIN", "VOUT"]

    def test_pin_by_number(self):
        c = Component(
            type="R", ref="R1", value="10k",
            pins=[Pin(1, "1", "A"), Pin(2, "2", "B")],
        )
        assert c.pin_by_number(1).net_name == "A"
        assert c.pin_by_number(2).net_name == "B"
        assert c.pin_by_number(3) is None


class TestNet:
    def test_add_connection(self):
        net = Net(name="VIN")
        net.add_connection("R1", 1)
        assert net.connection_count == 1
        assert net.is_boundary

    def test_boundary(self):
        net = Net(name="VOUT")
        net.add_connection("R1", 2)
        assert net.is_boundary
        net.add_connection("C1", 1)
        assert not net.is_boundary


class TestClassifyNet:
    def test_ground(self):
        is_gnd, is_pwr, _ = classify_net("0")
        assert is_gnd and not is_pwr

    def test_power(self):
        is_gnd, is_pwr, d = classify_net("VCC")
        assert not is_gnd and is_pwr and d == "input"

    def test_input(self):
        _, _, d = classify_net("VIN")
        assert d == "input"

    def test_output(self):
        _, _, d = classify_net("VOUT")
        assert d == "output"

    def test_generic(self):
        _, _, d = classify_net("N001")
        assert d == "inout"


class TestCircuit:
    def _make_rc(self) -> Circuit:
        c = Circuit(name="test")
        c.add_component(Component(
            type="R", ref="R1", value="10k",
            pins=[Pin(1, "1", "VIN"), Pin(2, "2", "VOUT")],
        ))
        c.add_component(Component(
            type="C", ref="C1", value="10nF",
            pins=[Pin(1, "1", "VOUT"), Pin(2, "2", "GND")],
        ))
        c.build_nets()
        return c

    def test_build_nets(self):
        c = self._make_rc()
        assert "VIN" in c.nets
        assert "VOUT" in c.nets
        assert "GND" in c.nets

    def test_port_nets(self):
        c = self._make_rc()
        port_names = {p.name for p in c.port_nets()}
        assert "VIN" in port_names
        assert "VOUT" in port_names

    def test_component_types(self):
        assert self._make_rc().component_types() == {"R", "C"}

    def test_get_component(self):
        c = self._make_rc()
        assert c.get_component("R1") is not None
        assert c.get_component("X99") is None

    def test_summary(self):
        s = self._make_rc().summary()
        assert "test" in s
