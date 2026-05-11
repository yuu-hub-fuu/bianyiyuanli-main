# Nexa Compiler Project

Nexa is a compiler-principles course project. It implements a small teaching language and a complete local toolchain from source code to lexical tables, AST, semantic diagnostics, HIR/MIR, optimization, CFG, LLVM IR, real Win64 x86-64 assembly, native build, and visual inspection.

## Quick Start

```bash
python -m pip install pytest
python nexa_cli.py example.nx --mode core --dump tables --run
python nexa_cli.py example.nx --mode full --dump all --run --trace --report out/report.html
pytest -q tests -p no:cacheprovider --tb=short
```

## Language Features

- Core syntax: variables, assignment, arithmetic/logical expressions, functions, `if`, `while`, `return`, and blocks.
- Types and data: `i32`, `f64`, `bool`, `str`, structs, arrays, indexing, and assignment.
- Teaching extensions: macros, generic monomorphization demo, channels/select subset, diagnostics with fix suggestions, and report export.
- Optimization: constant propagation, copy propagation, constant folding, algebraic simplification, dead-code elimination, unreachable-code elimination, common subexpression elimination, loop-invariant code motion, strength reduction, and small-function inlining.

## Compiler Pipeline

The main pipeline is:

```text
source -> lexer -> parser -> macro expansion -> semantic check
       -> HIR -> optimization -> MIR/CFG -> register allocation
       -> LLVM IR / Win64 x86-64 assembly / native executable
```

Important output artifacts include:

- keyword, delimiter, identifier, and constant tables
- AST text/tree output
- symbol table
- raw and optimized HIR quadruples
- CFG blocks and edges
- LLVM IR
- real Win64 x86-64 assembly
- optional native `.exe` build output

## CLI

Useful commands:

```bash
python nexa_cli.py example.nx --mode core --dump tables --run
python nexa_cli.py example.nx --mode full --dump all --run --trace
python nexa_cli.py example.nx --emit-llvm
python nexa_cli.py example.nx --build --run-exe
python nexa_cli.py example.nx --report out/report.html
```

## Desktop IDE

The IDE entrypoint is a Python tkinter desktop GUI:

```bash
python -m nexa.ide.app
```

It is not a FastAPI/WebSocket browser IDE. The desktop IDE supports source editing, Tokens, AST, symbol table, HIR, CFG, ASM, LLVM, Timeline, Run, Trace, diagnostics, quick fixes, and HTML report export.

## Native Backend

The x86-64 backend emits real Win64 assembly, assembles it with the MinGW64 toolchain, links it with the Nexa runtime, and can run the generated executable. It also includes local instruction-level optimizations such as `lea` arithmetic, shift-based multiplication by powers of two, `test` zero checks, `xor` zeroing, and redundant move elimination.

## Graph And Report Export

Compilation with an export directory writes:

- `out/ast.dot`
- `out/cfg_<fn>.dot`

If Graphviz is available, matching SVG files can be rendered. HTML reports include lexical tables, symbols, HIR quadruples, CFG, run output, diagnostics, and optional graph artifacts.
