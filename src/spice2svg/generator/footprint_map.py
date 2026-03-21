"""SPICE 元件类型 → KiCad 封装的默认映射。"""

DEFAULT_FOOTPRINTS: dict[str, str] = {
    "R": "Resistor_SMD:R_0805_2012Metric",
    "C": "Capacitor_SMD:C_0805_2012Metric",
    "L": "Inductor_SMD:L_0805_2012Metric",
    "D": "Diode_SMD:D_SOD-123",
    "Q": "Package_TO_SOT_SMD:SOT-23",
    "M": "Package_TO_SOT_SMD:SOT-23",
    "J": "Package_TO_SOT_SMD:SOT-23",
    "V": "TestPoint:TestPoint_Pad_D1.0mm",
    "I": "TestPoint:TestPoint_Pad_D1.0mm",
    "X": "Package_DIP:DIP-8_W7.62mm",
}

COMPONENT_DESCRIPTIONS: dict[str, str] = {
    "R": "resistor",
    "C": "capacitor",
    "L": "inductor",
    "D": "diode",
    "Q": "transistor (BJT)",
    "M": "transistor (MOSFET)",
    "J": "transistor (JFET)",
    "V": "voltage source",
    "I": "current source",
    "X": "subcircuit",
}


def get_footprint(component_type: str, custom_map: dict[str, str] | None = None) -> str:
    if custom_map and component_type in custom_map:
        return custom_map[component_type]
    return DEFAULT_FOOTPRINTS.get(component_type, "Package_DIP:DIP-8_W7.62mm")


def get_description(component_type: str) -> str:
    return COMPONENT_DESCRIPTIONS.get(component_type, "component")
