"""
spice2svg — SPICE Netlist → SKiDL → SVG 转换工具

将标准 SPICE 网表解析为中间表示，生成 SKiDL Python 代码，
最终渲染为 SVG 原理图。
"""

__version__ = "0.1.0"

from .models import Circuit, Component, Net, Pin
from .parser import parse, parse_file
from .generator import generate_skidl_code
from .renderer import circuit_to_netlistsvg_json, circuit_to_json_string
from .recognizer import recognize_supernodes, ALL_PATTERNS, SuperNode
