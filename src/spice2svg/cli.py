"""命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import run_full_pipeline, parse_only, codegen_only


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spice2svg",
        description="SPICE Netlist → SKiDL → SVG 转换工具",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # convert
    p_conv = sub.add_parser("convert", help="完整转换: SPICE → SVG")
    p_conv.add_argument("input", help="SPICE 网表文件")
    p_conv.add_argument("-o", "--output", default=".", help="输出目录")
    p_conv.add_argument("--dialect", default="generic")
    p_conv.add_argument("--direct", action="store_true", help="快捷路径")
    p_conv.add_argument("--skin", default=None)
    p_conv.add_argument("--no-svg", action="store_true")
    p_conv.add_argument("--supernodes", action="store_true",
                        help="启用超节点识别 (差分对、电流镜等折叠为单个块)")

    # parse
    p_parse = sub.add_parser("parse", help="仅解析")
    p_parse.add_argument("input")
    p_parse.add_argument("--dialect", default="generic")
    p_parse.add_argument("--dump-ir", action="store_true")

    # codegen
    p_cg = sub.add_parser("codegen", help="仅生成 SKiDL 代码")
    p_cg.add_argument("input")
    p_cg.add_argument("-o", "--output", default=None)
    p_cg.add_argument("--dialect", default="generic")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "convert":
            result = run_full_pipeline(
                args.input, args.output,
                dialect=args.dialect, direct=args.direct,
                skin=args.skin, skip_svg=args.no_svg,
                use_supernodes=args.supernodes,
            )
            print(result.circuit.summary())
            if result.warnings:
                print("\n警告:")
                for w in result.warnings:
                    print(f"  ⚠ {w}")
            if result.svg_path:
                print(f"\n✅ SVG: {result.svg_path}")
            else:
                print("\n❌ SVG 未生成")
            return 0 if result.success or args.no_svg else 1

        elif args.command == "parse":
            circuit = parse_only(args.input, dialect=args.dialect)
            print(circuit.summary())
            if args.dump_ir:
                print("\n--- Components ---")
                for comp in circuit.components:
                    print(f"  {comp}")
                print("\n--- Nets ---")
                for net in circuit.nets.values():
                    flags = []
                    if net.is_ground: flags.append("GND")
                    if net.is_power:  flags.append("PWR")
                    if net.direction != "inout": flags.append(net.direction)
                    flag_str = f" [{', '.join(flags)}]" if flags else ""
                    print(f"  {net}{flag_str}")
                if circuit.models:
                    print("\n--- Models ---")
                    for m in circuit.models.values():
                        print(f"  {m.name} ({m.type}): {m.params}")
            warnings = circuit.validate()
            if warnings:
                print("\n警告:")
                for w in warnings:
                    print(f"  ⚠ {w}")
            return 0

        elif args.command == "codegen":
            code = codegen_only(args.input, args.output, dialect=args.dialect)
            if not args.output:
                print(code)
            else:
                print(f"✅ SKiDL 代码: {args.output}")
            return 0

    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
