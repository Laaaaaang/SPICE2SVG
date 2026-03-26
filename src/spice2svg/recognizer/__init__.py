"""电路模式识别器 — 将常见子电路识别为超节点。

用法:
    from spice2svg.recognizer import recognize_supernodes, ALL_PATTERNS

    supernodes = recognize_supernodes(circuit, ALL_PATTERNS)
"""

from .engine import recognize_supernodes
from .supernode import SuperNode
from .pattern_def import PatternDef
from .patterns import ALL_PATTERNS

__all__ = [
    "recognize_supernodes",
    "SuperNode",
    "PatternDef",
    "ALL_PATTERNS",
]
