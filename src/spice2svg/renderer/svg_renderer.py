"""SVG 渲染主逻辑。

路径:
- 完整路径: 执行生成的 SKiDL .py → 自动产生 SVG
- 快捷路径: IR → JSON → netlistsvg → SVG → 差分对后处理
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


# ---------------------------------------------------------------------------
# 差分对 SVG 后处理所需数据
# ---------------------------------------------------------------------------
# 各类晶体管 skin 的正常方向 (base/gate-left) pin 坐标
_TRANSISTOR_PINS: dict[str, dict] = {
    "q_npn": {"width": 32, "pins": {"C": (22, 2), "B": (0, 16), "E": (23, 29)}},
    "q_pnp": {"width": 32, "pins": {"C": (22, 2), "B": (0, 16), "E": (23, 29)}},
    "nmos":  {"width": 32, "pins": {"D": (24, 0), "G": (0, 20), "S": (24, 40)}},
    "pmos":  {"width": 32, "pins": {"S": (24, 0), "G": (0, 20), "D": (24, 40)}},
}

# normal → mirror 图形替换 (path d 属性, class 类别)
_MIRROR_GRAPHICS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "q_npn": {
        "normal": [
            ("M0,16 H12 M12,6 V26",   "detail"),
            ("m12,10 11,-8",           "detail"),
            ("m12,21 11,8",            "detail"),
            ("m23,29 -6,-1 3,-5 z",   "fill"),
        ],
        "mirror": [
            ("M0,16 H20 M20,6 V26",   "detail"),
            ("m20,10 -11,-8",          "detail"),
            ("m20,21 -11,8",           "detail"),
            ("m9,29 6,-1 -3,-5 z",    "fill"),
        ],
    },
    "q_pnp": {
        "normal": [
            ("M0,16 H12 M12,6 V26",   "detail"),
            ("m12,10 11,-8",           "detail"),
            ("m12,21 11,8",            "detail"),
            ("m14,9 6,-1 -3,-5 z",    "fill"),
        ],
        "mirror": [
            ("M0,16 H20 M20,6 V26",   "detail"),
            ("m20,10 -11,-8",          "detail"),
            ("m20,21 -11,8",           "detail"),
            ("m18,9 -6,-1 3,-5 z",    "fill"),
        ],
    },
    "nmos": {
        "normal": [
            ("M0,20 H8",                                 "detail"),
            ("M10,6 V34",                                 "detail"),
            ("M14,6 V14 M14,18 V22 M14,26 V34",          "detail"),
            ("M14,20 H24",                                "detail"),
            ("m18,17 6,3 -6,3 z",                        "fill"),
        ],
        "mirror": [
            ("M32,20 H24",                               "detail"),
            ("M22,6 V34",                                 "detail"),
            ("M18,6 V14 M18,18 V22 M18,26 V34",          "detail"),
            ("M18,20 H8",                                 "detail"),
            ("m14,17 -6,3 6,3 z",                        "fill"),
        ],
    },
    "pmos": {
        "normal": [
            ("M0,20 H6",                                 "detail"),
            ("M10,6 V34",                                 "detail"),
            ("M14,6 V34",                                 "detail"),
            ("M24,20 H14",                                "detail"),
            ("m20,17 -6,3 6,3 z",                        "fill"),
        ],
        "mirror": [
            ("M32,20 H26",                               "detail"),
            ("M22,6 V34",                                 "detail"),
            ("M18,6 V34",                                 "detail"),
            ("M8,20 H18",                                 "detail"),
            ("m12,17 6,3 -6,3 z",                        "fill"),
        ],
    },
}

# PMOS 额外元素: 反相小圆从左侧移到右侧
_PMOS_BUBBLE_NORMAL = ("M0,20 H6", "detail")  # 已包含在 normal 中
_PMOS_BUBBLE_MIRROR = ("M32,20 H26", "detail")
# PMOS 反相气泡圆心: normal cx=8 → mirror cx=24
_PMOS_CIRCLE_CX_NORMAL = 8
_PMOS_CIRCLE_CX_MIRROR = 24

# NMOS/PMOS 额外的 connect 类路径
_NMOS_CONNECT_NORMAL = [
    ("M14,10 H24 V0",  "connect"),
    ("M14,30 H24 V40", "connect"),
]
_NMOS_CONNECT_MIRROR = [
    ("M18,10 H8 V0",   "connect"),
    ("M18,30 H8 V40",  "connect"),
]
_PMOS_CONNECT_NORMAL = [
    ("M14,10 H24 V0",  "connect"),
    ("M14,30 H24 V40", "connect"),
]
_PMOS_CONNECT_MIRROR = [
    ("M18,10 H8 V0",   "connect"),
    ("M18,30 H8 V40",  "connect"),
]


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
    # 常见全局安装位置 (conda base)
    for base in [
        Path(r"D:\ANANCONDA\Lib\site-packages\nodejs_wheel"),
        Path.home() / "AppData" / "Roaming" / "npm",
    ]:
        for name in ("netlistsvg.cmd", "netlistsvg"):
            candidate = base / name
            if candidate.exists():
                return str(candidate)
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


def _skin_to_lookup(skin_type: str) -> str | None:
    """将 SVG 中的 skin type 名映射到 _TRANSISTOR_PINS 的查找 key。"""
    for key in ("npn", "pnp", "nmos", "pmos"):
        if key in skin_type:
            prefix = "q_" if key in ("npn", "pnp") else ""
            return f"{prefix}{key}"
    return None


def _mirror_diff_pairs_in_svg(
    svg_text: str,
    diff_pair_refs: list[tuple[str, str]],
) -> str:
    """SVG 后处理: 将差分对右侧成员的晶体管符号水平镜像, 使基极/栅极向外。

    所有差分对成员在 JSON 中使用相同的 normal skin (base/gate-left)。
    渲染后, 右侧成员通过此函数被镜像为 base/gate-right, 并添加
    桥接线段保持连线连续性。

    Args:
        svg_text: netlistsvg 生成的 SVG 文本
        diff_pair_refs: 差分对列表, 每项 (ref_a, ref_b)
    """
    if not diff_pair_refs:
        return svg_text

    # ---- 解析 cell 位置 ----
    cell_info: dict[str, dict] = {}
    for m in re.finditer(
        r'<g\s+s:type="(\w+)"\s+s:width="(\d+)"\s+s:height="(\d+)"\s+'
        r'transform="translate\((\d+),(\d+)\)"\s+id="cell_(\w+)"',
        svg_text,
    ):
        cell_info[m.group(6)] = {
            "x": int(m.group(4)),
            "y": int(m.group(5)),
            "type": m.group(1),
            "width": int(m.group(2)),
        }

    # ---- 确定右侧成员 ----
    refs_to_mirror: set[str] = set()
    for ref_a, ref_b in diff_pair_refs:
        if ref_a not in cell_info or ref_b not in cell_info:
            continue
        if cell_info[ref_a]["x"] > cell_info[ref_b]["x"]:
            refs_to_mirror.add(ref_a)
        else:
            refs_to_mirror.add(ref_b)

    if not refs_to_mirror:
        return svg_text

    # ---- 修改连线端点 + 添加桥接线 ----
    new_bridge_lines: list[str] = []

    for ref in refs_to_mirror:
        info = cell_info[ref]
        cx, cy = info["x"], info["y"]
        width = info["width"]

        lookup = _skin_to_lookup(info["type"])
        if not lookup or lookup not in _TRANSISTOR_PINS:
            continue

        pin_data = _TRANSISTOR_PINS[lookup]

        for pin_name, (orig_px, orig_py) in pin_data["pins"].items():
            new_px = width - orig_px
            if orig_px == new_px:
                continue

            # BJT 基极: 镜像图形从 x=0 延伸到竖条, 外部连线无需移动
            if pin_name == "B" and lookup in ("q_npn", "q_pnp"):
                continue

            orig_gx = cx + orig_px
            new_gx = cx + new_px
            gy = cy + orig_py
            is_lateral = pin_name in ("B", "G")

            # 找到连接到 pin 的第一条 line
            pat = re.compile(
                r'<line x1="(\d+)" x2="(\d+)" '
                r'y1="(\d+)" y2="(\d+)" '
                r'class="(net_\d+)"/?>'
            )

            for m in pat.finditer(svg_text):
                x1 = int(m.group(1))
                x2 = int(m.group(2))
                y1 = int(m.group(3))
                y2 = int(m.group(4))
                net = m.group(5)

                ep = 0
                if x1 == orig_gx and y1 == gy:
                    ep = 1
                elif x2 == orig_gx and y2 == gy:
                    ep = 2
                else:
                    continue

                was_vertical = (x1 == x2)

                if is_lateral or not was_vertical:
                    # 横向 pin (B/G) 或非垂直线: 直接移动端点
                    if ep == 1:
                        new_line = (
                            f'<line x1="{new_gx}" x2="{x2}" '
                            f'y1="{gy}" y2="{y2}" class="{net}"/>'
                        )
                    else:
                        new_line = (
                            f'<line x1="{x1}" x2="{new_gx}" '
                            f'y1="{y1}" y2="{gy}" class="{net}"/>'
                        )
                    svg_text = svg_text[:m.start()] + new_line + svg_text[m.end():]
                else:
                    # 垂直线: 整体水平偏移到新 pin x 位置
                    far_y = y2 if ep == 1 else y1
                    new_line = (
                        f'<line x1="{new_gx}" x2="{new_gx}" '
                        f'y1="{y1}" y2="{y2}" class="{net}"/>'
                    )
                    svg_text = svg_text[:m.start()] + new_line + svg_text[m.end():]

                    # 级联: 将远端相邻的水平线段端点也偏移过来
                    adj_match = None
                    for m2 in pat.finditer(svg_text):
                        x1b = int(m2.group(1))
                        x2b = int(m2.group(2))
                        y1b = int(m2.group(3))
                        y2b = int(m2.group(4))
                        net2 = m2.group(5)
                        if net2 != net:
                            continue
                        # 只级联水平线 (y1==y2), 避免连锁修改垂直线
                        if y1b != y2b:
                            continue
                        ep2 = 0
                        if x1b == orig_gx and y1b == far_y:
                            ep2 = 1
                        elif x2b == orig_gx and y2b == far_y:
                            ep2 = 2
                        if ep2:
                            adj_match = (m2, ep2, x1b, x2b, y1b, y2b, net2)
                            break

                    if adj_match:
                        m2, ep2, x1b, x2b, y1b, y2b, net2 = adj_match
                        if ep2 == 1:
                            adj_line = (
                                f'<line x1="{new_gx}" x2="{x2b}" '
                                f'y1="{y1b}" y2="{y2b}" class="{net2}"/>'
                            )
                        else:
                            adj_line = (
                                f'<line x1="{x1b}" x2="{new_gx}" '
                                f'y1="{y1b}" y2="{y2b}" class="{net2}"/>'
                            )
                        svg_text = (svg_text[:m2.start()] + adj_line
                                    + svg_text[m2.end():])
                    else:
                        # 远端无水平线: 在远端添加短桥接
                        lo = min(new_gx, orig_gx)
                        hi = max(new_gx, orig_gx)
                        new_bridge_lines.append(
                            f'  <line x1="{lo}" x2="{hi}" '
                            f'y1="{far_y}" y2="{far_y}" class="{net}"/>'
                        )

                break  # 每个 pin 只处理第一条匹配的 line

    # 插入远端桥接线段 (如有)
    if new_bridge_lines:
        bridge_block = "\n".join(new_bridge_lines)
        svg_text = svg_text.replace("</svg>", f"{bridge_block}\n</svg>")

    # ---- 替换 cell 内图形 ----
    for ref in refs_to_mirror:
        info = cell_info[ref]
        lookup = _skin_to_lookup(info["type"])
        if not lookup:
            continue

        cell_class = f"cell_{ref}"

        # 主要图形 (detail / fill 类路径)
        gfx = _MIRROR_GRAPHICS.get(lookup)
        if gfx:
            for (norm_d, norm_cls), (mirr_d, _) in zip(
                gfx["normal"], gfx["mirror"]
            ):
                if norm_cls == "detail":
                    old = f'<path d="{norm_d}" class="detail {cell_class}"'
                    new = f'<path d="{mirr_d}" class="detail {cell_class}"'
                else:  # fill (arrow)
                    old = (
                        f'<path d="{norm_d}" style="fill:#000" '
                        f'class="{cell_class}"'
                    )
                    new = (
                        f'<path d="{mirr_d}" style="fill:#000" '
                        f'class="{cell_class}"'
                    )
                svg_text = svg_text.replace(old, new, 1)

        # NMOS/PMOS connect 类路径
        if lookup == "nmos":
            for (norm_d, _), (mirr_d, _) in zip(
                _NMOS_CONNECT_NORMAL, _NMOS_CONNECT_MIRROR
            ):
                old = f'<path d="{norm_d}" class="connect {cell_class}"'
                new = f'<path d="{mirr_d}" class="connect {cell_class}"'
                svg_text = svg_text.replace(old, new, 1)

        elif lookup == "pmos":
            for (norm_d, _), (mirr_d, _) in zip(
                _PMOS_CONNECT_NORMAL, _PMOS_CONNECT_MIRROR
            ):
                old = f'<path d="{norm_d}" class="connect {cell_class}"'
                new = f'<path d="{mirr_d}" class="connect {cell_class}"'
                svg_text = svg_text.replace(old, new, 1)

            # PMOS 反相气泡圆心
            old_circle = (
                f'<circle cx="{_PMOS_CIRCLE_CX_NORMAL}" cy="20" r="2" '
                f'class="symbol {cell_class}"'
            )
            new_circle = (
                f'<circle cx="{_PMOS_CIRCLE_CX_MIRROR}" cy="20" r="2" '
                f'class="symbol {cell_class}"'
            )
            svg_text = svg_text.replace(old_circle, new_circle, 1)

    return svg_text


def render_svg_direct(circuit: Circuit, output_path: Path,
                      skin: str | None = None) -> Path:
    """IR → JSON → netlistsvg → SVG → 差分对后处理（快捷路径）。

    差分对成员使用相同的 normal skin (base/gate-left) 渲染,
    渲染后通过 SVG 后处理将右侧成员镜像为 base/gate-right,
    实现基极/栅极向外。
    """
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

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_path.with_suffix(".json")

    # ---- 生成 JSON (所有差分对成员使用 normal skin) ----
    json_data, diff_pair_refs = circuit_to_netlistsvg_json(
        circuit, direction=direction,
    )

    json_path.write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ---- 调用 netlistsvg 渲染 ----
    cmd: list[str] = [netlistsvg, str(json_path), "-o", str(output_path)]
    if skin_file:
        cmd.extend(["--skin", skin_file])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"netlistsvg 执行失败:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    if not output_path.exists():
        raise FileNotFoundError(f"netlistsvg 未生成 SVG: {output_path}")

    # ---- SVG 后处理: 镜像差分对右侧成员使基极/栅极向外 ----
    if diff_pair_refs:
        svg_text = output_path.read_text(encoding="utf-8")
        svg_text = _mirror_diff_pairs_in_svg(svg_text, diff_pair_refs)
        output_path.write_text(svg_text, encoding="utf-8")

    return output_path
