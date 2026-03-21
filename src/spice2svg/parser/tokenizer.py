"""SPICE 网表词法分析器。

将原始 SPICE 文本预处理为干净的逻辑行列表。
处理：行续接 (+)、注释 (* ; $)、空行。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpiceLine:
    """一条逻辑 SPICE 行及其在源文件中的起始行号。"""
    text: str
    line_number: int  # 1-based

    def __repr__(self) -> str:
        return f"L{self.line_number}: {self.text}"


def tokenize(text: str, *, strip_comments: bool = True) -> list[SpiceLine]:
    """将原始 SPICE 文本转换为逻辑行列表。

    规则:
    1. ``*`` 开头为注释行（第一行保留作为 title）
    2. ``;`` 或 ``$`` 后面的内容为行内注释
    3. ``+`` 开头的行与上一逻辑行合并（行续接）
    4. 空行跳过
    5. ``.end`` 标记网表结束
    """
    raw_lines = text.splitlines()
    logical_lines: list[SpiceLine] = []
    current_text = ""
    current_start = 0

    for i, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()

        # 空行
        if not stripped:
            continue

        # 全行注释
        if stripped.startswith("*"):
            # SPICE 惯例：第一行即使是注释也作为 title
            if not logical_lines and not current_text:
                logical_lines.append(SpiceLine(text=stripped, line_number=i))
            continue

        # 去除行内注释
        if strip_comments:
            for marker in (";", "$"):
                idx = stripped.find(marker)
                if idx >= 0:
                    stripped = stripped[:idx].strip()
            if not stripped:
                continue

        # 行续接
        if stripped.startswith("+"):
            continuation = stripped[1:].strip()
            if current_text:
                current_text += " " + continuation
            else:
                current_text = continuation
                current_start = i
        else:
            # 保存上一逻辑行
            if current_text:
                logical_lines.append(SpiceLine(text=current_text, line_number=current_start))
            current_text = stripped
            current_start = i

    # 保存最后一行
    if current_text:
        logical_lines.append(SpiceLine(text=current_text, line_number=current_start))

    return logical_lines
