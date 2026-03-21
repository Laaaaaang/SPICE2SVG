"""将 Circuit IR 转换为 SKiDL Python 代码。"""

from __future__ import annotations

from ..models import Circuit
from .templates import (
    HEADER_TEMPLATE,
    TEMPLATE_FUNC,
    generate_part_template,
    generate_net_declaration,
    generate_component_instance,
    generate_pin_connection,
)


def generate_skidl_code(circuit: Circuit) -> str:
    """将 Circuit IR 转换为完整可执行的 SKiDL Python 文件。"""
    sections: list[str] = []

    # 1. 文件头
    sections.append(HEADER_TEMPLATE.format(
        name=circuit.name or "unnamed",
        title=circuit.title or "",
    ))

    # 2. 模板创建辅助函数
    sections.append(TEMPLATE_FUNC)

    # 3. Part 模板
    comp_types = sorted(circuit.component_types())
    if comp_types:
        sections.append("\n# === Part Templates ===\n")
        for ct in comp_types:
            sections.append(generate_part_template(ct))

    # 4. Net 声明
    if circuit.nets:
        sections.append("\n\n# === Nets ===\n")
        for net in circuit.nets.values():
            sections.append(generate_net_declaration(
                net.name, net.direction, net.is_ground, net.is_boundary,
            ))

    # 5. 元件实例化
    if circuit.components:
        sections.append("\n\n# === Components ===\n")
        for comp in circuit.components:
            sections.append(generate_component_instance(comp))

    # 6. 引脚连接
    if circuit.components:
        sections.append("\n\n# === Connections ===\n")
        for comp in circuit.components:
            for pin in comp.pins:
                sections.append(generate_pin_connection(
                    comp.ref, pin.number, pin.net_name,
                ))

    # 7. 输出
    sections.append("""

# === Generate Output ===
ERC()
generate_netlist()
try:
    generate_svg()
    print("SVG schematic generated successfully.")
except Exception as exc:
    print(f"SVG generation failed: {exc}")
""")

    return "\n".join(sections)
