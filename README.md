# SPICE2SVG

SPICE2SVG is a Python toolkit for converting SPICE netlists into structured circuit representations and schematic SVGs.

It supports two end-to-end pipelines:

- `SPICE -> Circuit IR -> SKiDL -> SVG`
- `SPICE -> Circuit IR -> netlistsvg JSON -> SVG`

This repository focuses on the algorithmic part of the system: parsing, intermediate representation design, topology recognition, and layout-aware rendering heuristics.

## Preview

Initial rendering result generated from `examples/1.cir`:

![SPICE2SVG preview](docs/images/overview_1.svg)

## Overview

SPICE netlists are compact and simulation-friendly, but they are difficult to read as diagrams. SPICE2SVG reconstructs enough structure from raw netlists to generate readable schematics automatically.

```text
SPICE text
   |
   v
Tokenizer -> Parser -> Circuit IR -> Generator -> SKiDL Python -> SVG
                           |
                           +-> JSON Converter -> netlistsvg -> SVG
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

### 3. Topology recognition

The current implementation recognizes and groups:

- differential pairs
- current mirrors
- complementary driver pairs
- complementary push-pull output pairs

Recognized blocks are reordered before layout so the graph passed into ELK already carries analog structure.

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
