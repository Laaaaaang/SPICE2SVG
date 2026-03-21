"""SVG 渲染主逻辑。

两条路径:
- 完整路径: 执行生成的 SKiDL .py → 自动产生 SVG
- 快捷路径: IR → JSON → netlistsvg → SVG
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from ..models import Circuit
from .json_converter import circuit_to_netlistsvg_json
from .skin import get_skin_path, get_default_skin_path


def _detect_skin_direction(skin_path: str | Path | None) -> str:
    """从 skin SVG 文件中检测 ELK 布局方向 (DOWN/RIGHT/...)。"""
    if not skin_path:
        return "DOWN"
    try:
        content = Path(skin_path).read_text(encoding="utf-8")
        m = re.search(r'org\.eclipse\.elk\.direction="(\w+)"', content)
        if m:
            return m.group(1).upper()
    except Exception:
        pass
    return "DOWN"


def _find_netlistsvg() -> str | None:
    """在 PATH 和常见位置中查找 netlistsvg。"""
    found = shutil.which("netlistsvg")
    if found:
        return found
    # nodejs_wheel (pip install nodejs-wheel netlistsvg) 安装位置
    try:
        import importlib.util
        spec = importlib.util.find_spec("nodejs_wheel")
        if spec and spec.submodule_search_locations:
            for loc in spec.submodule_search_locations:
                for name in ("netlistsvg.cmd", "netlistsvg"):
                    candidate = Path(loc) / name
                    if candidate.exists():
                        return str(candidate)
    except Exception:
        pass
    return None


def render_svg_via_skidl(skidl_code: str, output_dir: Path) -> Path:
    """执行 SKiDL 代码生成 SVG（完整路径）。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    py_file = output_dir / "circuit.py"
    py_file.write_text(skidl_code, encoding="utf-8")

    result = subprocess.run(
        ["python", str(py_file)],
        cwd=str(output_dir),
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SKiDL 执行失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    svg_candidates = list(output_dir.glob("*.svg"))
    if svg_candidates:
        return svg_candidates[0]
    raise FileNotFoundError("SKiDL 未生成 SVG 文件")


def render_svg_direct(circuit: Circuit, output_path: Path,
                      skin: str | None = None) -> Path:
    """IR → JSON → netlistsvg → SVG（快捷路径）。"""
    netlistsvg = _find_netlistsvg()
    if not netlistsvg:
        raise RuntimeError(
            "netlistsvg 未安装或不在 PATH 中。请运行: npm install -g netlistsvg"
        )

    # 确定皮肤文件
    skin_file: str | None = None
    if skin:
        sp = get_skin_path(skin)
        if sp:
            skin_file = str(sp)
        elif Path(skin).exists():
            skin_file = skin
    if not skin_file:
        default = get_default_skin_path()
        if default:
            skin_file = str(default)

    # 从 skin 文件检测布局方向, 传给 converter
    direction = _detect_skin_direction(skin_file)

    json_data = circuit_to_netlistsvg_json(circuit, direction=direction)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    cmd: list[str] = [netlistsvg, str(json_path), "-o", str(output_path)]
    if skin_file:
        cmd.extend(["--skin", skin_file])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"netlistsvg 执行失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    if not output_path.exists():
        raise FileNotFoundError(f"netlistsvg 未生成 SVG: {output_path}")
    return output_path
