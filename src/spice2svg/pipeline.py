"""流水线编排器 — 串联 Parser → Recognizer → Generator → Renderer。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .parser import parse, parse_file
from .generator import generate_skidl_code
from .renderer import circuit_to_json_string, render_svg_direct, render_svg_via_skidl
from .renderer.json_converter import circuit_to_netlistsvg_json_with_supernodes
from .models import Circuit
from .recognizer import recognize_supernodes, ALL_PATTERNS, SuperNode


@dataclass
class PipelineResult:
    circuit: Circuit
    skidl_code: str = ""
    json_str: str = ""
    svg_path: Path | None = None
    warnings: list[str] = field(default_factory=list)
    supernodes: list[SuperNode] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.svg_path is not None and self.svg_path.exists()


def run_full_pipeline(
    input_path: str | Path,
    output_dir: str | Path = ".",
    *,
    dialect: str = "generic",
    direct: bool = False,
    skin: str | None = None,
    skip_svg: bool = False,
    use_supernodes: bool = False,
) -> PipelineResult:
    """完整转换: SPICE → (超节点识别) → SKiDL → SVG。"""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult(circuit=Circuit())

    # 1. 解析
    circuit = parse_file(input_path, dialect=dialect)
    result.circuit = circuit
    result.warnings = circuit.validate()

    # 1.5. 超节点识别 (可选)
    sn_list: list[SuperNode] = []
    if use_supernodes:
        sn_list = recognize_supernodes(circuit, ALL_PATTERNS)
        result.supernodes = sn_list
        if sn_list:
            result.warnings.append(
                f"识别出 {len(sn_list)} 个超节点: "
                + ", ".join(f"{s.ref}({s.pattern_name})" for s in sn_list)
            )

    # 2. SKiDL 代码
    skidl_code = generate_skidl_code(circuit)
    result.skidl_code = skidl_code
    skidl_path = output_dir / f"{input_path.stem}_skidl.py"
    skidl_path.write_text(skidl_code, encoding="utf-8")

    # 3. JSON
    json_str = circuit_to_json_string(circuit, supernodes=sn_list or None)
    result.json_str = json_str
    json_path = output_dir / f"{input_path.stem}.json"
    json_path.write_text(json_str, encoding="utf-8")

    if skip_svg:
        return result

    # 4. SVG
    svg_path = output_dir / f"{input_path.stem}.svg"
    try:
        if direct:
            result.svg_path = render_svg_direct(
                circuit, svg_path, skin=skin,
                supernodes=sn_list or None,
            )
        else:
            result.svg_path = render_svg_via_skidl(skidl_code, output_dir)
    except Exception as exc:
        result.warnings.append(f"SVG 渲染失败: {exc}")
        if not direct:
            try:
                result.svg_path = render_svg_direct(
                    circuit, svg_path, skin=skin,
                    supernodes=sn_list or None,
                )
                result.warnings.append("已回退到快捷路径渲染")
            except Exception as exc2:
                result.warnings.append(f"快捷路径也失败: {exc2}")

    return result


def parse_only(input_path: str | Path, dialect: str = "generic") -> Circuit:
    return parse_file(input_path, dialect=dialect)


def codegen_only(
    input_path: str | Path,
    output_path: str | Path | None = None,
    dialect: str = "generic",
) -> str:
    circuit = parse_file(input_path, dialect=dialect)
    code = generate_skidl_code(circuit)
    if output_path:
        Path(output_path).write_text(code, encoding="utf-8")
    return code
