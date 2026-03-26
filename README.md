# SPICE2SVG

**SPICE 网表 → 自动分组 → 超节点原理图**

SPICE2SVG 能够将 SPICE 网表自动转换为可读的原理图 SVG。核心亮点是 **超节点（Supernode）识别与分块绘制**：系统自动识别差分对、电流镜、推挽输出级等 15+ 种模拟电路拓扑，将匹配的晶体管组折叠为带有内部原理图细节的独立块（block），再与外围元件一起进行布局渲染。

### ✨ 最新成果：超节点分块渲染

> **自动拓扑识别** → 将匹配的多管结构折叠为超节点块  
> **块内原理图** → 每个超节点块内绘制完整的晶体管级电路符号  
> **端口对齐** → 块的外部端口与 netlistsvg 布局引擎精确对接  
> **电源显式连接** → 推挽级的 VCC/VEE、镜像参考节点均正确暴露

#### 支持的超节点类型

| 分类 | 拓扑 |
|------|------|
| 差分对 | NPN / PNP / NMOS / PMOS |
| 电流镜 | NPN / PNP / NMOS / PMOS |
| 交叉耦合对 | NPN / NMOS |
| 共源共栅 | NPN / PNP / NMOS / PMOS |
| Darlington | NPN / PNP |
| Sziklai 互补对 | NPN+PNP |
| Vbe 乘法器 | NPN+R1+R2 |
| 推挽输出 | BJT / MOS |
| Wilson 电流镜 | NPN |
| 差分对+有源负载 | NPN+PNP / PNP+NPN |

#### 渲染示例

`examples/1.cir` — 差分输入 + PNP 有源负载 + VAS + Vbe 偏置 + 推挽输出 + 全局负反馈：

![Supernode rendering - example 1](docs/images/supernode_1.svg)

`examples/5.cir` — 双差分输入 + 双 VAS + Vbe 乘法器 + 驱动级 + 推挽输出级：

![Supernode rendering - example 5](docs/images/supernode_5.svg)

#### 使用方法

```bash
# 启用超节点识别
spice2svg convert examples/1.cir -o output/ --direct --supernodes
```

---

## Overview

SPICE2SVG is a Python toolkit for converting SPICE netlists into structured circuit representations and schematic SVGs.

It supports two end-to-end pipelines:

- `SPICE -> Circuit IR -> SKiDL -> SVG`
- `SPICE -> Circuit IR -> netlistsvg JSON -> SVG`

This repository focuses on the algorithmic part of the system: parsing, intermediate representation design, topology recognition, and layout-aware rendering heuristics.

### Basic rendering (without supernodes)

![SPICE2SVG preview](docs/images/overview_1.svg)

## Motivation

Today, many LLMs can already generate SPICE-style netlists that are syntactically correct or close to correct. However, beginners often struggle to understand the connection structure encoded in a netlist, especially in analog circuits where topology matters more than isolated devices.

This creates a communication gap:

- natural-language intent is translated into a netlist
- the netlist is hard for learners to inspect visually
- topology-level meaning is easily lost or distorted during explanation and iteration

SPICE2SVG is designed as a demo tool to support **LLM-assisted learning and simple analog circuit design**. Its purpose is to make the structure inside a generated netlist visible again, so that learners can move back and forth between:

- natural-language descriptions
- SPICE netlists
- schematic-style visualizations

In that sense, the project helps close the loop from **natural language -> schematic/netlist -> visual understanding**, which is especially useful for teaching, guided exploration, and rapid prototyping of simple analog circuits.

## Overview

SPICE netlists are compact and simulation-friendly, but they are difficult to read as diagrams. SPICE2SVG reconstructs enough structure from raw netlists to generate readable schematics automatically.

```text
SPICE text
   |
   v
Tokenizer -> Parser -> Circuit IR -> Recognizer -> Supernodes
                           |              |            |
                           |              v            v
                           |         JSON Converter -> netlistsvg -> SVG
                           |                  (with supernode cells & skins)
                           v
                       Generator -> SKiDL Python -> SVG
```

## Core capabilities

- Parse standard SPICE netlists (`.cir`, `.sp`, `.spice`) into a typed `Circuit` IR
- Generate executable SKiDL Python code from the IR
- Render SVG schematics directly through `netlistsvg`
- Support passive devices, sources, BJTs, MOSFETs, JFETs, controlled sources, behavioral sources, and subcircuits
- Detect analog structures such as differential pairs, current mirrors, and complementary push-pull stages
- Normalize power nets into explicit `VCC`, `VEE`, and `GND` schematic symbols
- Support both top-down (`DOWN`) and left-to-right (`RIGHT`) layout skins

## Unique contribution

My distinctive contribution in this project is the **extensible block layout system**.

Instead of sending a raw graph directly to the layout engine, the renderer adds a structural layer that recognizes analog building blocks and rewrites the graph before layout.

This layer includes:

- automatic polarity resolution for `NPN/PNP` and `NMOS/PMOS`
- dynamic symbol-family selection (`normal`, `mirror-right`, `mirror-left`)
- topology-driven recognition of reusable analog blocks
- block-preserving component reordering before ELK layout
- port-direction heuristics for cleaner analog routing
- special handling for inverted `PNP/PMOS` follower topologies to eliminate diagonal wires

Because of this design, the layout algorithm is extensible: new block recognizers can be added as independent policies without rewriting the entire renderer.

## Architecture

### `src/spice2svg/parser`

- `tokenizer.py`: logical-line processing, continuation lines, comments, numeric suffixes
- `spice_parser.py`: components, directives, models, parameters, and subcircuits
- `spice_dialect.py`: abstraction layer for SPICE dialect differences

### `src/spice2svg/models`

- `circuit.py`: top-level circuit container
- `component.py`: component and pin metadata
- `net.py`: net objects, boundary detection, and direction metadata

### `src/spice2svg/generator`

- `skidl_generator.py`: converts the IR into executable SKiDL Python code
- `templates.py`: reusable code templates for code generation
- `footprint_map.py`: default mapping from SPICE parts to footprints

### `src/spice2svg/renderer`

- `json_converter.py`: algorithmic IR-to-netlistsvg conversion
- `svg_renderer.py`: direct renderer and SKiDL fallback orchestration
- `skin.py`: skin resolution and skin listing

### `src/spice2svg/recognizer`

- `pattern_def.py`: declarative pattern definition DSL (roles, constraints, external ports)
- `patterns.py`: 15+ analog topology pattern definitions
- `engine.py`: constraint-based matching engine and supernode builder
- `supernode.py`: supernode data model (ref, skin type, ports, internal nets)

### `src/spice2svg/pipeline.py`

- orchestrates parsing, code generation, JSON export, and SVG rendering

### `src/spice2svg/cli.py`

- command-line entry point for `convert`, `parse`, and `codegen`

## Layout algorithm highlights

The renderer is the most algorithm-heavy part of the repository.

### 1. Typed pin remapping

SPICE pin numbers are remapped to schematic-aware names such as:

- resistor: `A`, `B`
- BJT: `C`, `B`, `E`
- MOS/JFET: `D`, `G`, `S`
- sources: `+`, `-`

This enables symbol-aware rendering and directed layout.

### 2. Power-net normalization

The converter splits signal nets from power nets and emits dedicated one-pin power cells for each local power connection. This reduces long global wires and improves analog readability.

### 3. Topology recognition and supernode folding

The recognizer module uses a declarative constraint-based pattern matching engine to identify analog building blocks:

- differential pairs (NPN/PNP/NMOS/PMOS)
- current mirrors (NPN/PNP/NMOS/PMOS)
- cross-coupled pairs, cascode stacks
- Darlington pairs, Sziklai complementary pairs
- Vbe multiplier bias circuits
- complementary push-pull output stages (BJT/MOS)
- Wilson current mirrors
- differential pairs with active loads (4-transistor blocks)

Recognized blocks are folded into **supernodes** — single cells with dedicated schematic-style SVG skins that show internal transistor-level detail while maintaining clean external port connections to the rest of the circuit.

### 4. Symbol policy layer

The skin system supports multiple symbol families for active devices:

- standard symbols
- right-mirrored symbols
- left-block symbols used for grouped analog structures

This allows the same device category to be rendered differently depending on its role in a detected block.

### 5. Port-direction heuristics

ELK layering is guided through semantic `input/output` port directions. The converter adjusts port directions for cases such as:

- diode-connected transistors
- current mirrors
- complementary push-pull stages
- inverted `PNP/PMOS` follower topologies

These heuristics are the main reason the generated analog schematics are much cleaner than naive graph layouts.

## Installation

### Python package

```bash
pip install -e .
```

### SVG backend

Install `netlistsvg` for direct SVG generation:

```bash
npm install -g netlistsvg
```

## Usage

### Convert a netlist to SVG

```bash
spice2svg convert examples/voltage_divider.cir -o output/ --direct
```

### Generate SKiDL code only

```bash
spice2svg codegen examples/voltage_divider.cir -o output/voltage_divider_skidl.py
```

### Parse only and inspect the IR

```bash
spice2svg parse examples/voltage_divider.cir --dump-ir
```

### Use the rightward layout skin

```bash
spice2svg convert examples/5.cir -o output/ --direct --skin skins/right.svg
```

## Example circuits

The repository includes examples ranging from simple passive networks to multi-stage analog amplifiers:

- voltage divider
- RC low-pass filter
- RLC band-pass filter
- CMOS inverter
- common-emitter amplifier
- multi-stage differential/VAS/push-pull amplifier

## Development

### Run tests

```bash
pytest
```

### Project layout

```text
src/spice2svg/
  parser/
  models/
  generator/
  renderer/
  recognizer/
tests/
examples/
skins/
docs/
```

## Repository scope

This repository is intended to publish the implementation and algorithms behind the project:

- SPICE parsing
- Circuit IR construction
- SKiDL generation
- topology recognition
- block-aware layout heuristics
- SVG rendering integration

Generated files in `output/` are not required in the source repository.

## GitHub

Target repository: https://github.com/Laaaaaang/SPICE2SVG.git
