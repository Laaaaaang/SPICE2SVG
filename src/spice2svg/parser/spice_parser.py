"""SPICE 网表语法解析器。

将 tokenizer 输出的逻辑行流解析为 Circuit IR。
"""

from __future__ import annotations

from pathlib import Path

from ..models import Circuit, Component, ModelDef, Pin, SubCircuit, PIN_DEFS
from ..models.component import MIN_PINS
from .tokenizer import SpiceLine, tokenize
from .spice_dialect import get_dialect_config


class ParseError(Exception):
    """解析错误。"""
    def __init__(self, message: str, line_number: int = 0):
        self.line_number = line_number
        super().__init__(f"Line {line_number}: {message}" if line_number else message)


# ------------------------------------------------------------------ helpers ---

def _normalize_ground(node: str) -> str:
    """将 SPICE '0' 节点标准化为 'GND'。"""
    if node.lower() in ("0", "gnd", "gnd!"):
        return "GND"
    return node


def _parse_element_line(tokens: list[str], line_num: int) -> Component:
    """解析元件行，返回 Component。"""
    ref = tokens[0]
    elem_type = ref[0].upper()

    if elem_type == "X":
        return _parse_subcircuit_instance(tokens, line_num)

    pin_names = PIN_DEFS.get(elem_type, ["1", "2"])
    min_pins = MIN_PINS.get(elem_type, 2)

    if len(tokens) < min_pins + 2:
        raise ParseError(
            f"元件 {ref} 参数不足 (需要至少 {min_pins} 个节点 + 值)",
            line_num,
        )

    nodes = [_normalize_ground(tokens[i]) for i in range(1, min_pins + 1)]

    remaining = tokens[min_pins + 1:]
    value = ""
    properties: dict[str, str] = {}

    if remaining:
        if elem_type in ("D", "Q", "M", "J"):
            value = remaining[0]
            properties["model"] = remaining[0]
            for tok in remaining[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    properties[k.upper()] = v
        else:
            value = " ".join(remaining)
            parts = value.split()
            if len(parts) >= 2 and parts[0].upper() in ("DC", "AC"):
                properties["source_type"] = parts[0].upper()
                value = parts[1]

    pins = []
    for i, node in enumerate(nodes):
        pin_name = pin_names[i] if i < len(pin_names) else str(i + 1)
        pins.append(Pin(number=i + 1, name=pin_name, net_name=node))

    return Component(
        type=elem_type,
        ref=ref.upper(),
        value=value,
        pins=pins,
        properties=properties,
    )


def _parse_subcircuit_instance(tokens: list[str], line_num: int) -> Component:
    """解析子电路实例: X<name> <nodes…> <subckt>"""
    ref = tokens[0].upper()
    if len(tokens) < 3:
        raise ParseError(f"子电路实例 {ref} 参数不足", line_num)

    subckt_name = tokens[-1]
    nodes = [_normalize_ground(t) for t in tokens[1:-1]]

    pins = [
        Pin(number=i + 1, name=str(i + 1), net_name=node)
        for i, node in enumerate(nodes)
    ]
    return Component(
        type="X", ref=ref, value=subckt_name,
        pins=pins, properties={"subcircuit": subckt_name},
    )


def _parse_model(tokens: list[str]) -> ModelDef:
    """解析 .model 行。"""
    if len(tokens) < 3:
        return ModelDef(name="unknown", type="unknown")
    name = tokens[1]
    model_type = tokens[2].upper()
    params: dict[str, str] = {}
    rest = " ".join(tokens[3:]).replace("(", " ").replace(")", " ")
    for part in rest.split():
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.upper()] = v
    return ModelDef(name=name, type=model_type, params=params)


def _parse_param(tokens: list[str]) -> tuple[str, str]:
    """解析 .param 行。"""
    rest = " ".join(tokens[1:])
    if "=" in rest:
        k, v = rest.split("=", 1)
        return k.strip(), v.strip()
    if len(tokens) >= 3:
        return tokens[1], tokens[2]
    return tokens[1] if len(tokens) > 1 else "unknown", ""


# -------------------------------------------------------------- public API ---

def parse(text: str, *, name: str = "", dialect: str = "generic") -> Circuit:
    """解析 SPICE 网表文本，返回 Circuit IR。"""
    _config = get_dialect_config(dialect)
    lines = tokenize(text)

    circuit = Circuit(name=name)
    title_found = False
    in_subcircuit = False
    subckt_lines: list[SpiceLine] = []
    subckt_name = ""
    subckt_ports: list[str] = []

    for spice_line in lines:
        text_line = spice_line.text
        line_num = spice_line.line_number

        # title（第一行注释）
        if text_line.startswith("*") and not title_found:
            circuit.title = text_line.lstrip("* ").strip()
            title_found = True
            continue

        if text_line.startswith("*"):
            continue

        tokens = text_line.split()
        if not tokens:
            continue

        first = tokens[0].lower()

        # 子电路内部
        if in_subcircuit:
            if first == ".ends":
                subckt_text = "\n".join(sl.text for sl in subckt_lines)
                subckt_circuit = parse(subckt_text, name=subckt_name, dialect=dialect)
                circuit.subcircuits.append(SubCircuit(
                    name=subckt_name, ports=subckt_ports, circuit=subckt_circuit,
                ))
                in_subcircuit = False
                subckt_lines = []
                continue
            subckt_lines.append(spice_line)
            continue

        # 指令
        if first.startswith("."):
            if first == ".end":
                break
            elif first == ".subckt":
                in_subcircuit = True
                subckt_name = tokens[1] if len(tokens) > 1 else "unknown"
                subckt_ports = tokens[2:]
                subckt_lines = []
            elif first == ".model":
                model = _parse_model(tokens)
                circuit.models[model.name] = model
            elif first == ".param":
                k, v = _parse_param(tokens)
                circuit.params[k] = v
            continue

        # 元件行
        if tokens[0][0].upper() in "RCLDQMVIJEFGHXB":
            try:
                comp = _parse_element_line(tokens, line_num)
                circuit.add_component(comp)
            except ParseError as e:
                print(f"WARNING: {e}")

    circuit.build_nets()
    return circuit


def parse_file(filepath: str | Path, **kwargs) -> Circuit:
    """解析 SPICE 网表文件。"""
    path = Path(filepath)
    text = path.read_text(encoding="utf-8", errors="replace")
    if "name" not in kwargs:
        kwargs["name"] = path.stem
    return parse(text, **kwargs)
