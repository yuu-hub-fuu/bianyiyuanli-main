# Nexa Compiler Project

## Quick Start

```bash
python -m pip install pytest
python nexa_cli.py example.nx --mode core --dump tables --run
python nexa_cli.py example.nx --mode full --dump all --run --trace --report out/report.html
pytest -q
```

## Language Features

- Core: variables, expressions, functions, `if`, `while`, `for`, `break`, `continue`.
- Structs, enums, and `match`: parsed, type-checked, lowered, and runnable in the VM.
- Modern expressions: lambdas, string interpolation, pipe `|>`, dictionaries, ranges, and array slices.
- Collections: `array.map/filter/reduce` accept lambda function values.
- Macro expansion: AST-level macro expansion with depth limit and teaching gensym.
- Generic functions: monomorphized demo path for call-site instantiation.
- Select/channel subset: `br.ready + recv + default` lowering for the teaching runtime.
- LLVM IR: supports HIR labels, jumps, branches, loops, channel runtime calls, bool/string constants, and integer operations.
- x86-64: readable teaching text emitter.

## Standard Library

Module-style builtins are available in VM run mode:

- `str`: length, concat, contains, prefix/suffix checks, split/join, replace, substring, trim, case conversion, numeric parse/format.
- `math`: integer `abs/max/min`, f64 `pow/sqrt/sin/cos`, `floor/ceil`, and `random`.
- `array` / `collections`: length, push, pop, index lookup, contains, sort, reverse, and slice. Higher-order `map/filter/reduce` are type-registered but need future function-value support.
- `os`: environment variables, safe `args/getcwd/chdir/sleep`, and non-terminating `exit` in the VM.
- `fs` / `io`: read, write, append, exists, is-dir, mkdir, read-dir, and non-recursive remove. Paths are sandboxed to the current source file directory during `compile_source(..., run=True, source_path=...)`.
- `time`: millisecond/nanosecond clock, sleep, and ISO formatting.
- `json`: parse and stringify.
- `testing`: `assert_eq`, `assert_true`, and `assert_false`.
- `net`: signatures are reserved, but runtime calls are disabled in the safe VM.

## CLI Output

`--dump tables` or `--dump all` can show:

- keyword/delimiter/identifier/constant tables
- symbol table
- HIR quadruples
- CFG
- ASM
- LLVM IR with `--emit-llvm`

## Modes

- `--mode core`: stable course-baseline mode.
- `--mode full`: macro/generic/select visualization mode.

## VM Run Mode

`--run` executes optimized HIR with `nexa.vm.HIRVM`.

`--trace` prints VM instruction trace when used with `--run`.

`--report out/report.html` writes a teaching HTML report with lexical tables, symbols, HIR, CFG, run output, diagnostics, and optional SVG artifacts.

## Desktop IDE

```bash
python -m nexa.ide.app
```

The tkinter IDE includes source editing, syntax highlighting, diagnostics, tokens, AST, symbols, HIR, CFG, ASM, LLVM, timeline, run output, trace, and report export.

## Graph Export

Compilation with an export directory writes:

- `out/ast.dot`
- `out/cfg_<fn>.dot`

If the optional `graphviz` Python package is installed, matching SVG files are rendered next to the DOT files.
