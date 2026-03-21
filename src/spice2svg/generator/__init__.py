"""SKiDL 代码生成器。"""

from .skidl_generator import generate_skidl_code
from .footprint_map import get_footprint, get_description, DEFAULT_FOOTPRINTS

__all__ = [
    "DEFAULT_FOOTPRINTS", "generate_skidl_code",
    "get_description", "get_footprint",
]
