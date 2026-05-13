# Nexa Compiler Project

Nexa is a compiler-principles course project. It implements a compact teaching language and a complete local toolchain from source code to lexical tables, AST, semantic diagnostics, HIR/MIR, optimization, CFG, register allocation, LLVM IR, Win64 x86-64 assembly, native `.exe` build output, VM execution, and visual inspection.

## Quick Start

```bash
python -m pip install -e .
python -m pip install pytest

python nexa_cli.py example.nx --mode full --run
python nexa_cli.py example.nx --mode full --dump all --run --trace --export-dir out --report out/report.html
python -m pytest
```

If you only want to use the package from the current checkout without installing dependencies again:

```bash
python -m pip install -e . --no-deps
```

## Language Features

### Core Syntax

Nexa currently supports:

- variable declarations with optional type inference
- assignment
- arithmetic, comparison, and logical expressions
- functions and direct function calls
- single-file relative imports with `import "file.nx";`
- `if` / `else`
- `while`
- `return`
- nested blocks and block expressions
- single-line comments with `//`

Example:

```nx
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

fn main() -> i32 {
    let x: i32 = add(1, 2);
    if x > 0 { return x; }
    return 0;
}
```

### Types And Data

Supported types include:

- `i32`
- `f64`
- `bool`
- `str`
- `void`
- `Array[T]`
- user-defined `struct`
- `Chan[i32]`

Examples:

```nx
struct Pair { x: i32, y: i32 }

fn main() -> i32 {
    let n: i32 = 10;
    let f: f64 = 1.5 + 2.25;
    let ok: bool = f > 3.0;

    let p: Pair = Pair { x: n, y: 20 };
    p.x = p.x + 5;

    let xs: Array[i32] = [1, 2, 3, 4];
    xs[2] = xs[0] + xs[3];

    if ok { return p.x + xs[2]; }
    return 0;
}
```

Arrays support literal construction, indexing, and indexed assignment:

```nx
let xs: Array[i32] = [1, 2, 3];
let a: i32 = xs[0];
xs[1] = xs[0] + xs[2];
```

Structs support declaration, literal construction, field access, and field assignment:

```nx
struct Pair { x: i32, y: i32 }
let p: Pair = Pair { x: 1, y: 2 };
p.x = p.x + 1;
```

### Teaching Extensions

Nexa also includes course-oriented language features:

- AST-level macros
- generic functions with monomorphization
- a simple `Ord` generic-bound demo
- `chan`, `send`, `recv`
- `select { recv(...) => ... default => ... }`
- `spawn` syntax
- semantic diagnostics with fix suggestions

Example:

```nx
macro unless(cond, body) {
    if !cond { body; }
}

fn max[T: Ord](a: T, b: T) -> T {
    if a > b { return a; }
    return b;
}
```

### Imports

Nexa supports a first version of file imports:

```nx
import "math.nx";

fn main() -> i32 {
    return math.add(1, 2);
}
```

The imported file can provide functions:

```nx
pub fn add(a: i32, b: i32) -> i32 {
    return a + b;
}
```

Import paths are resolved relative to the source file that contains the import. Only `pub fn` declarations are visible outside the imported file; plain `fn` declarations are private implementation details that can still be used inside that file. Imported function symbols are internally mangled with the imported file stem, for example `math.nx` public function `add` becomes `math__add` at the Nexa IR level and `nx_math__add` in assembly. The entry file keeps `main` as the runtime entry point.

Imports also support aliases:

```nx
import "math.nx" as m;

fn main() -> i32 {
    return m.add(1, 2);
}
```

This first version is intentionally simple:

- imports expose functions through a module namespace such as `math.add(...)`
- imports also keep direct calls to public functions like `add(...)` for compatibility with the first prototype
- `import "file.nx" as alias;` enables alias-qualified calls such as `alias.add(...)`
- imported files export only `pub fn`; plain `fn` is private to that file
- local functions in the importing file take precedence
- imported functions are renamed to avoid linker-symbol collisions
- imported structs/macros can be parsed with the imported file, but cross-file package semantics are still minimal
- cyclic imports and package directories are not production features yet

## Built-In Functions

Currently available built-ins:

```text
print(value)           -> void     # supports i32, f64, bool, and str in current backends
panic(str)             -> void
read_i32()             -> i32
read_f64()             -> f64
len(Array[T])          -> i32
chan(i32)              -> Chan[i32]
send(Chan[i32], i32)   -> void
recv(Chan[i32])        -> i32
```

`read_i32` and `read_f64` are simple stdin helpers. They are intentionally smaller than C `scanf`: each call reads one value of the declared type.

## Modes

Nexa has two modes:

```text
core  - stable basic teaching path
full  - enables macro expansion and generic monomorphization demos
```

Default mode is `full`.

Use `full` for `example.nx`, because the sample program uses the `unless` macro:

```bash
python nexa_cli.py example.nx --mode full --run
```

If you run the same file in `core` mode, semantic analysis will report `unless` as an undefined function because macro expansion is disabled.

## Compiler Pipeline

The main pipeline is:

```text
source
 -> lexer
 -> parser
 -> macro expansion
 -> semantic check
 -> generic monomorphization
 -> HIR generation
 -> HIR optimization
 -> MIR / CFG
 -> register allocation
 -> LLVM IR / Win64 x86-64 assembly / native executable
 -> optional VM run or native exe run
```

Important artifacts:

- token stream
- keyword table
- delimiter table
- identifier table
- constant table
- AST text/tree output
- symbol table
- raw HIR quadruples
- optimized HIR quadruples
- CFG blocks and edges
- register allocation result used by the backend
- LLVM IR
- Win64 x86-64 assembly
- native `.o` and `.exe`
- VM run result and trace
- HTML report
- AST/CFG DOT files and optional rendered graph images

## Optimization

HIR optimization currently includes:

- constant propagation
- copy propagation
- constant folding
- algebraic simplification
- dead-code elimination
- unreachable-code elimination
- common subexpression elimination
- loop-invariant code motion
- strength reduction
- small-function inlining

The CLI can show raw and optimized HIR:

```bash
python nexa_cli.py example.nx --mode full --dump hir
```

## CLI Usage

Show all options:

```bash
python nexa_cli.py --help
```

General shape:

```bash
python nexa_cli.py <source.nx> [options]
```

### Dump Stage Outputs

```bash
python nexa_cli.py example.nx --mode full --dump tokens
python nexa_cli.py example.nx --mode full --dump tables
python nexa_cli.py example.nx --mode full --dump ast
python nexa_cli.py example.nx --mode full --dump hir
python nexa_cli.py example.nx --mode full --dump cfg
python nexa_cli.py example.nx --mode full --dump asm
python nexa_cli.py example.nx --mode full --dump all
```

`--dump asm` prints the generated assembly text to the terminal.

### VM Run

Run through the HIR VM:

```bash
python nexa_cli.py example.nx --mode full --run
```

Run with VM trace:

```bash
python nexa_cli.py example.nx --mode full --run --trace
```

The VM path is useful for teaching, debugging, and deterministic inspection of the optimized HIR execution.

### LLVM IR

Print LLVM IR:

```bash
python nexa_cli.py example.nx --mode full --emit-llvm
```

LLVM IR is another backend artifact. It is useful for showing how Nexa can target a modern compiler IR.

### Native Win64 Build

Build native artifacts:

```bash
python nexa_cli.py example.nx --mode full --build
```

This emits:

```text
out/example.s
out/example.o
out/example.exe
```

Build and run the produced executable:

```bash
python nexa_cli.py example.nx --mode full --build --run-exe
```

Use a custom build directory:

```bash
python nexa_cli.py example.nx --mode full --build --build-dir native_out
```

Native build requires a GCC/MinGW64 toolchain on `PATH`.

### Graph Export

Export AST and CFG DOT files:

```bash
python nexa_cli.py example.nx --mode full --export-dir out
```

Generated files include:

```text
out/ast.dot
out/cfg_<fn>.dot
```

If Graphviz is available, matching SVG files may also be rendered.

### HTML Report

Generate a report:

```bash
python nexa_cli.py example.nx --mode full --dump all --run --trace --export-dir out --report out/report.html
```

Reports include lexical tables, symbols, HIR quadruples, CFG, run output, diagnostics, and optional graph artifacts.

## Desktop IDE

Launch the tkinter desktop IDE:

```bash
python -m nexa.ide.app
```

The IDE supports:

- source editing
- file tree/open/save
- Tokens view
- AST view
- symbol table
- HIR view
- CFG view
- ASM view
- LLVM IR view
- Timeline view
- VM run
- VM trace
- diagnostics panel
- jump-to-diagnostic
- quick fixes
- HTML report export

Useful shortcuts:

```text
Ctrl+Enter   Compile
F5           Run with trace
Ctrl+O       Open
Ctrl+S       Save
F1           Shortcuts
Ctrl+Wheel   Zoom AST/CFG graph
```

This is a tkinter desktop GUI, not a FastAPI/WebSocket browser IDE.

## Native Backend

The x86-64 backend emits real Win64 assembly using Intel syntax, assembles it with GCC/MinGW64, links it with the Nexa runtime, and can run the generated executable.

Native backend support includes:

- integer arithmetic and comparisons
- `f64` arithmetic and comparisons using SSE instructions
- polymorphic `print` dispatch for `i32`, `f64`, `bool`, and `str`
- `read_i32`, `read_f64`, and `len(Array[T])` runtime helpers
- function calls
- `if` / `while`
- arrays
- structs
- generic monomorphized functions
- `panic`
- single-threaded channel runtime helpers

The generated assembly uses runtime helpers from:

```text
nexa/runtime/nexa_rt.c
```

The native backend also performs local instruction-level improvements such as:

- `lea` arithmetic forms
- shift-based multiplication by powers of two
- `test` for zero checks
- `xor` zeroing
- redundant move elimination

## VM Runtime

`--run` executes optimized HIR in `nexa.vm.HIRVM`.

The VM supports:

- function calls
- arithmetic and comparison operations
- `i32`, `f64`, `bool`, and `str` values
- arrays
- structs
- channels/select subset
- stdout collection
- execution trace
- runtime error reporting

The VM is the easiest route for classroom demonstration. The native backend is the route for showing a real assembly/link/run pipeline.

## Testing

Run all tests:

```bash
python -m pytest
```

Short test command:

```bash
pytest -q tests -p no:cacheprovider --tb=short
```

Native backend tests are skipped automatically if GCC is not available on `PATH`.

## Example Program

`example.nx` demonstrates macros, generics, channels/select, and runtime checking:

```nx
macro unless(cond, body) {
    if !cond { body; }
}

struct Pair { x: i32, y: i32 }

fn max[T: Ord](a: T, b: T) -> T {
    if a > b { return a; }
    return b;
}

fn main() -> i32 {
    let ch: Chan[i32] = chan(1);
    send(ch, 42);
    let ans: i32 = select {
        recv(ch) => { 42; }
        default => { 0; }
    };
    unless(ans == 42, { panic("bad"); });
    return max(ans, 40);
}
```

Run it:

```bash
python nexa_cli.py example.nx --mode full --run
```

Expected result:

```text
exit=42
```

## Current Limits

Nexa is still a course-project language, not an industrial language. Current limits include:

- no formatted `scanf` equivalent; only `read_i32()` and `read_f64()` are provided
- first-version imports only; no package registry, version solver, or full dependency resolver
- no heap lifetime management beyond the simple runtime model
- no full concurrency semantics in the native backend
- `spawn` is still mainly syntax/teaching surface
- LLVM IR is an artifact backend and does not cover every extended feature as a production target
- language and runtime are intentionally small for compiler-principles demonstration
