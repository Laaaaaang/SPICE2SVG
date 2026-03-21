"""SPICE 方言配置。

不同仿真器 (ngspice, LTspice, HSPICE …) 在语法细节上有差异，
本模块提供统一的配置层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Dialect(Enum):
    GENERIC = "generic"
    NGSPICE = "ngspice"
    LTSPICE = "ltspice"
    HSPICE  = "hspice"
    PSPICE  = "pspice"


@dataclass
class DialectConfig:
    name: Dialect = Dialect.GENERIC
    ground_names: set[str] = field(default_factory=lambda: {"0", "gnd"})
    comment_chars: set[str] = field(default_factory=lambda: {"*"})
    inline_comment_chars: set[str] = field(default_factory=lambda: {";"})
    case_sensitive: bool = False


DIALECT_CONFIGS: dict[Dialect, DialectConfig] = {
    Dialect.GENERIC: DialectConfig(),
    Dialect.NGSPICE: DialectConfig(name=Dialect.NGSPICE, ground_names={"0", "gnd"}),
    Dialect.LTSPICE: DialectConfig(name=Dialect.LTSPICE, ground_names={"0"}, inline_comment_chars={";"} ),
    Dialect.HSPICE:  DialectConfig(name=Dialect.HSPICE,  ground_names={"0", "gnd!"}, inline_comment_chars={";", "$"}),
    Dialect.PSPICE:  DialectConfig(name=Dialect.PSPICE,  ground_names={"0"}, inline_comment_chars={";"}),
}


def get_dialect_config(dialect: str | Dialect = Dialect.GENERIC) -> DialectConfig:
    if isinstance(dialect, str):
        try:
            dialect = Dialect(dialect.lower())
        except ValueError:
            dialect = Dialect.GENERIC
    return DIALECT_CONFIGS.get(dialect, DIALECT_CONFIGS[Dialect.GENERIC])
