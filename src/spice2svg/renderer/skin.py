"""SVG 皮肤管理。"""

from __future__ import annotations

from pathlib import Path

SKINS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "skins"


def get_default_skin_path() -> Path | None:
    default = SKINS_DIR / "default.svg"
    return default if default.exists() else None


def get_skin_path(name: str) -> Path | None:
    path = SKINS_DIR / name
    if not path.suffix:
        path = path.with_suffix(".svg")
    return path if path.exists() else None


def list_skins() -> list[str]:
    if not SKINS_DIR.exists():
        return []
    return [p.name for p in SKINS_DIR.glob("*.svg")]
