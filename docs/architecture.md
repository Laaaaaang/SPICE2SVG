# 架构设计文档

## 1. 设计目标

将任意标准 SPICE 网表自动转换为可视化 SVG 原理图，中间产物为可编辑的
SKiDL Python 代码。系统应当：

- **准确** — 忠实还原 SPICE 网表中的电路拓扑
- **可扩展** — 容易添加新的 SPICE 元件类型和仿真器方言
- **双路径** — 既可生成 SKiDL 代码（便于人工修改），也可直接出 SVG（追求速度）
- **可测试** — 每个阶段独立可测，有明确的输入/输出契约

---

## 2. 数据流

```
输入                    阶段 1            阶段 2             阶段 3            阶段 4
────────────────────────────────────────────────────────────────────────────────────
.cir / .sp 文本   ──▶  Token 流   ──▶  Circuit IR   ──▶  SKiDL .py    ──▶  .svg
                      (tokenizer)     (spice_parser)    (skidl_gen)      (renderer)
                                           │
                                           └──────────▶  JSON  ──▶  .svg
                                                       (json_conv)  (netlistsvg)
```

### 阶段间数据格式

| 边界 | 数据格式 |
|------|---------|
| 文件 → tokenizer | `str` (原始文件文本) |
| tokenizer → parser | `list[Token]` (token 流) |
| parser → IR | `Circuit` 对象 (dataclass 树) |
| IR → skidl_generator | `Circuit` 对象 |
| skidl_generator → 文件 | `str` (Python 源码文本) |
| IR → json_converter | `Circuit` 对象 |
| json_converter → netlistsvg | `dict` (JSON) |

---

## 3. 核心数据结构 (Circuit IR)

```
Circuit
├── name: str
├── components: list[Component]
│   └── Component
│       ├── type: str          # "R", "C", "L", "D", "Q", "M", "V", "I", "X"
│       ├── ref: str           # "R1", "C2", "Q1"
│       ├── value: str         # "10k", "100nF"
│       ├── pins: list[Pin]
│       │   └── Pin
│       │       ├── number: int
│       │       ├── name: str
│       │       └── net_name: str
│       └── properties: dict   # model, footprint, 等
├── nets: list[Net]
│   └── Net
│       ├── name: str
│       ├── connections: list[(ref, pin_num)]
│       ├── is_ground: bool
│       ├── is_power: bool
│       └── direction: str     # "input" / "output" / "inout"
├── subcircuits: list[SubCircuit]
│   └── SubCircuit
│       ├── name: str
│       ├── ports: list[str]
│       └── circuit: Circuit   # 递归!
├── models: dict[str, ModelDef]
└── params: dict[str, str]
```

---

## 4. SPICE 解析策略

### 4.1 词法分析 (Tokenizer)

SPICE 网表具有以下词法特征：

- **行导向**: 每行一个元件或指令
- **行续接**: `+` 在行首表示续上一行
- **注释**: `*` 开头的行，或 `;` 之后的内容
- **数值后缀**: `1k` = 1e3, `10u` = 10e-6, `3.3meg` = 3.3e6

Tokenizer 负责将原始文本预处理为干净的逻辑行流。

### 4.2 语法解析 (Parser)

每个逻辑行的首字符决定元件类型：

| 首字符 | 类型 | 引脚数 | 格式 |
|--------|------|--------|------|
| R | 电阻 | 2 | `R<name> <n+> <n-> <value>` |
| C | 电容 | 2 | `C<name> <n+> <n-> <value>` |
| L | 电感 | 2 | `L<name> <n+> <n-> <value>` |
| D | 二极管 | 2 | `D<name> <n+> <n-> <model>` |
| Q | BJT | 3 | `Q<name> <nc> <nb> <ne> <model>` |
| M | MOSFET | 4 | `M<name> <nd> <ng> <ns> <nb> <model>` |
| V | 电压源 | 2 | `V<name> <n+> <n-> <value>` |
| I | 电流源 | 2 | `I<name> <n+> <n-> <value>` |
| X | 子电路实例 | N | `X<name> <nodes...> <subckt>` |
| . | 指令 | - | `.subckt`, `.model`, `.param`, `.end` 等 |

### 4.3 方言差异

| 特性 | ngspice | LTspice | HSPICE |
|------|---------|---------|--------|
| 大小写 | 不敏感 | 不敏感 | 不敏感 |
| 节点名 | 字母/数字 | 字母/数字 | 分层路径 |
| 地节点 | `0` 或 `gnd` | `0` | `0` 或 `gnd!` |
| 注释 | `*` 行首 | `*` 或 `;` | `$` 也行 |
| MOSFET | 4端 | 4端 | 4端 + bulk |

---

## 5. SKiDL 代码生成策略

### 5.1 元件模板

为 SPICE 中出现的每种元件类型，生成一个 SKiDL `Part` 模板：

```python
# 自动生成的 Part 模板 (以 R 为例)
r_template = Part(name="R", tool=SKIDL, dest=TEMPLATE)
r_template.ref_prefix = "R"
r_template.description = "resistor"
r_template.footprint = "Resistor_SMD:R_0805_2012Metric"
r_template += Pin(num=1, name="1", func=Pin.funcs.PASSIVE)
r_template += Pin(num=2, name="2", func=Pin.funcs.PASSIVE)
```

### 5.2 网络与连接

用 SKiDL 的链式语法表达连接关系：

```python
vin = Net("VIN")
vout = Net("VOUT")
gnd = Net("GND")

r1 = r_template(value="10k")
c1 = c_template(value="10nF")

# 方式 A: 链式连接 (仅适用于串联拓扑)
vin & r1 & vout

# 方式 B: 显式引脚连接 (通用)
r1[1] += vin
r1[2] += vout
c1[1] += vout
c1[2] += gnd
```

生成器默认使用 **方式 B** (显式引脚连接)，因为它对任意拓扑都适用。

---

## 6. SVG 渲染策略

### 6.1 完整路径

1. 将生成的 SKiDL `.py` 文件用 `subprocess` 或 `exec()` 执行
2. SKiDL 自动调用 `generate_svg()` → 先生成 JSON → 再调 netlistsvg

### 6.2 快捷路径

1. 从 Circuit IR 直接构造 netlistsvg JSON 格式
2. 调用 `netlistsvg` CLI 渲染 SVG
3. 不经过 SKiDL，更快、依赖更少

### 6.3 netlistsvg JSON 格式

```json
{
  "modules": {
    "": {
      "cells": {
        "R1": {
          "type": "R_1_",
          "attributes": { "value": "10k" },
          "connections": { "1": [1], "2": [2] },
          "port_directions": { "1": "input", "2": "input" }
        }
      },
      "ports": {
        "VIN": { "bits": [1], "direction": "input" },
        "VOUT": { "bits": [2], "direction": "output" }
      }
    }
  }
}
```

---

## 7. 错误处理

| 阶段 | 可能的错误 | 处理策略 |
|------|-----------|---------|
| Tokenizer | 编码错误、空文件 | 抛出 `ParseError` 并指明行号 |
| Parser | 未知元件类型、引脚数不匹配 | 警告 + 跳过，或严格模式下报错 |
| IR 验证 | 悬空网络、未连接引脚 | 类似 ERC 检查，输出警告列表 |
| Generator | 无法映射的元件类型 | 回退到通用 N 引脚 Part |
| Renderer | netlistsvg 不可用 | 优雅降级，输出 JSON |

---

## 8. 扩展点

- **新元件类型**: 在 `spice_parser.py` 添加解析规则 + 在 `footprint_map.py` 添加映射
- **新方言**: 在 `spice_dialect.py` 注册新的方言配置
- **新输出格式**: 在 `renderer/` 下添加新的渲染器 (如 KiCad PCB、PDF)
- **自定义皮肤**: 在 `skins/` 下放置 netlistsvg skin SVG 文件
