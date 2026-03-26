# SPICE2SVG

SPICE2SVG converts SPICE netlists into structured circuit representations and schematic SVGs.

Key features include automatic identification of common analog topologies and grouping matched transistor sets into "supernode" blocks. Each supernode can render an internal transistor-level schematic while exposing clean external ports for layout and connection.

Highlights:

- Automatic topology recognition for 15+ analog patterns (differential pairs, current mirrors, push-pull stages, etc.)
- Supernode block rendering with internal schematic detail
- Port alignment and compatibility with the `netlistsvg` layout engine
- Explicit handling of power rails (VCC / VEE) and reference nodes

## Supernode Types

Supported supernode/topology types include (but are not limited to):

- Differential pairs (NPN / PNP / NMOS / PMOS)
- Current mirrors (NPN / PNP / NMOS / PMOS)
- Cross-coupled pairs (NPN / NMOS)
- Cascode and stacked stages
- Darlington and Sziklai complementary pairs
- Vbe multipliers and bias networks
- Push-pull output stages (BJT / MOS)
- Wilson current mirrors
- Differential pair with active load variants

## Example renderings

`examples/1.cir` — differential input, PNP active load, VAS, Vbe bias, push-pull output, global feedback:

![Supernode rendering - example 1](docs/images/supernode_1.svg)

`examples/5.cir` — cascaded differential stages, Vbe multiplier, driver and push-pull outputs:

![Supernode rendering - example 5](docs/images/supernode_5.svg)

## Overview

SPICE2SVG provides two end-to-end pipelines:

- SPICE -> Circuit IR -> SKiDL -> SVG
- SPICE -> Circuit IR -> netlistsvg JSON -> SVG

This repository focuses on parsing, designing the intermediate representation (IR), topology recognition, and layout-aware rendering heuristics used to produce readable analog schematics.

Conceptual flow:

```
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

## Core Capabilities

- Parse standard SPICE netlists (`.cir`, `.sp`, `.spice`) into a typed `Circuit` IR
- Generate executable SKiDL Python code from the IR
- Render schematic SVGs with `netlistsvg`
- Support passive components, voltage/current sources, BJTs, MOSFETs, JFETs, controlled and behavioral sources, and subcircuits
- Detect analog structures such as differential pairs, current mirrors, cascoded stages, and push-pull outputs
- Normalize power nets to explicit `VCC`, `VEE`, and `GND` schematic symbols
- Provide both top-down (`DOWN`) and left-to-right (`RIGHT`) layout skins

## Distinctive Design

The project introduces an extensible block layout system: rather than sending a raw connectivity graph straight to the layout engine, the renderer recognizes analog building blocks and rewrites the graph to preserve structure and visual clarity.

Features of this layer:

- Automatic polarity resolution for NPN/PNP and NMOS/PMOS families
- Symbol family selection (`normal`, `mirror-right`, `mirror-left`) to improve visual consistency
- Declarative pattern-based recognizers for reusable analog blocks
- Block-preserving reordering before ELK layout to improve routing and wire clarity
- Port-direction heuristics to guide ELK layering for cleaner analog diagrams

These mechanisms make it straightforward to add new block recognizers without changing the core renderer.

## Architecture

Key folders and responsibilities:

- `src/spice2svg/parser`
  - `tokenizer.py`: logical-line processing, continuations, comments, numeric suffixes
  - `spice_parser.py`: parsing components, directives, models, parameters, and subcircuits
  - `spice_dialect.py`: SPICE dialect abstractions

- `src/spice2svg/models`
  - `circuit.py`: top-level circuit container
  - `component.py`: component and pin metadata
  - `net.py`: net objects and net boundary/direction utilities

- `src/spice2svg/generator`
  - `skidl_generator.py`: IR -> executable SKiDL Python
  - `templates.py`: code templates
  - `footprint_map.py`: default SPICE-to-footprint mappings

- `src/spice2svg/renderer`
  - `json_converter.py`: IR -> netlistsvg JSON conversion
  - `svg_renderer.py`: direct renderer and SKiDL fallback orchestration
  - `skin.py`: skin resolution and listing

- `src/spice2svg/recognizer`
  - `pattern_def.py`: declarative pattern DSL (roles, constraints, external ports)
  - `patterns.py`: topology patterns (15+)
  - `engine.py`: constraint-based matching engine and supernode builder
  - `supernode.py`: supernode model (reference, skin, ports, internal nets)

- `src/spice2svg/pipeline.py`: orchestrates parse, codegen, JSON export, and rendering
- `src/spice2svg/cli.py`: command-line entry point (`convert`, `parse`, `codegen`)

## Layout algorithm highlights

1) Typed pin remapping — SPICE pin numbers are mapped to schematic-aware pin names (e.g. BJT: `C`, `B`, `E`; MOS: `D`, `G`, `S`) to enable symbol-aware layout.

2) Power-net normalization — signal and power nets are separated and power connections are emitted as single-pin power cells to reduce long global wires.

3) Topology recognition and supernode folding — a constraint-based pattern engine identifies analog blocks (differential pairs, current mirrors, cascodes, etc.) and folds them into single cells with dedicated skins.

4) Symbol policy layer — multiple symbol families let devices render appropriately depending on their role in a block.

5) Port-direction heuristics — semantic input/output directions guide ELK layering for cleaner schematic results.

## Installation

Install in editable mode for development:

```bash
pip install -e .
```

Install the SVG backend (`netlistsvg`) for direct SVG rendering:

```bash
npm install -g netlistsvg
```

## Usage

Convert a netlist to SVG:

```bash
spice2svg convert examples/voltage_divider.cir -o output/ --direct
```

Generate SKiDL code only:

```bash
spice2svg codegen examples/voltage_divider.cir -o output/voltage_divider_skidl.py
```

Parse only and dump the IR:

```bash
spice2svg parse examples/voltage_divider.cir --dump-ir
```

Use the rightward layout skin:

```bash
spice2svg convert examples/5.cir -o output/ --direct --skin skins/right.svg
```

## Examples

The repository contains example circuits from simple passive filters to multi-stage analog amplifiers:

- voltage divider
- RC low-pass filter
- RLC band-pass filter
- CMOS inverter
- common-emitter amplifier
- multi-stage differential / VAS / push-pull amplifiers

## Development

Run tests:

```bash
pytest
```

Project layout:

```
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

## Scope

This repository documents and publishes the implementation for:

- SPICE parsing
- Circuit IR construction
- SKiDL generation
- Topology recognition
- Block-aware layout heuristics
- SVG rendering integration

Generated files inside `output/` are not required to be committed.

## Repository

Target repository: https://github.com/Laaaaaang/SPICE2SVG.git
