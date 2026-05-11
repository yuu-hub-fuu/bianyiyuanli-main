from __future__ import annotations

import argparse
from pathlib import Path

from nexa.compiler import compile_source
from nexa.report.html_report import write_html_report


def _print_table(title: str, rows: list[str]) -> None:
    print(f"== {title} ==")
    if rows:
        print("\n".join(rows))
    else:
        print("(empty)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Nexa compiler")
    ap.add_argument("source", type=Path)
    ap.add_argument("--dump", choices=["none", "tokens", "tables", "ast", "hir", "cfg", "asm", "all"], default="none")
    ap.add_argument("--mode", choices=["core", "full"], default="full")
    ap.add_argument("--export-dir", default=None)
    ap.add_argument("--emit-llvm", action="store_true")
    ap.add_argument("--run", action="store_true", help="run via the HIR VM (interpreter)")
    ap.add_argument("--trace", action="store_true", help="print VM execution trace (requires --run)")
    ap.add_argument("--report", type=Path, default=None, help="write HTML compile report")
    ap.add_argument("--build", action="store_true",
                    help="emit real Win64 .s, assemble to .o, link to out/<source>.exe via gcc")
    ap.add_argument("--build-dir", default="out", help="directory for native build artifacts (default: out/)")
    ap.add_argument("--run-exe", action="store_true",
                    help="execute the produced .exe after --build (the OS loader actually runs it on the CPU)")
    args = ap.parse_args()

    src = args.source.read_text(encoding="utf-8")
    res = compile_source(
        src,
        mode=args.mode,
        export_dir=args.export_dir,
        run=args.run,
        trace=args.trace and args.run,
        build=args.build or args.run_exe,
        build_dir=args.build_dir,
        source_stem=args.source.stem,
        run_exe=args.run_exe,
        source_path=str(args.source),
    )

    print("== TIMELINE ==")
    for st in res.timeline:
        marker = {"ok": "[OK]", "warning": "[WARN]", "failed": "[FAIL]", "skipped": "[SKIP]"}.get(st.status, "[?]")
        print(f"{marker:<6} {st.name:<12} {st.detail}")

    for d in res.diagnostics:
        print(f"[{d.level}] {d.message} @ line {d.span.line}:{d.span.col}")
        for n in d.notes:
            print(f"  note: {n}")
        for f in d.fixits:
            print(f"  fix: {f}")


    if args.run and res.run_value is not None:
        print("== RUN ==")
        for line in res.run_stdout:
            print(line)
        print(f"exit={res.run_value}")
        if args.trace:
            print("== TRACE ==")
            for i, fr in enumerate(res.vm_trace, 1):
                print(f"#{i:04d} {fr.fn}@{fr.ip} op={fr.instr} env={fr.env}")


    if args.emit_llvm:
        if args.mode != "core":
            print("[warning] LLVM backend only supports core integer subset")
        print("== LLVM IR ==")
        print(res.artifacts.llvm_ir)

    if args.dump in {"tokens", "all"}:
        _print_table("TOKENS", res.artifacts.tokens)

    if args.dump in {"tables", "all"}:
        _print_table("关键字表", res.artifacts.tables.get("keywords", []))
        _print_table("界符表", res.artifacts.tables.get("delimiters", []))
        _print_table("标识符表", res.artifacts.tables.get("identifiers", []))
        _print_table("常量表", res.artifacts.tables.get("constants", []))
        _print_table("符号表", res.artifacts.symbols)
        _print_table("四元式表", res.artifacts.tables.get("quadruples", []))

    if args.dump in {"ast", "all"}:
        _print_table("AST", res.artifacts.ast_text.splitlines())

    if args.dump in {"hir", "all"}:
        from nexa.compiler import _hir_lines
        _print_table("HIR(原始)", _hir_lines(res.artifacts.hir_raw))
        _print_table("HIR(优化后)", _hir_lines(res.artifacts.hir_opt))

    if args.dump in {"cfg", "all"}:
        print("== CFG ==")
        for fn, rows in res.artifacts.cfg.items():
            print(f"-- {fn} --")
            print("\n".join(rows))

    if args.dump in {"asm", "all"}:
        print("== ASM ==")
        for fn, text in res.artifacts.asm.items():
            print(f"-- {fn} --")
            print(text)

    if res.build is not None:
        print("== NATIVE BUILD ==")
        print(f"asm  : {res.build.asm_path}")
        print(f"obj  : {res.build.object_path}")
        print(f"rt.o : {res.build.runtime_object_path}")
        print(f"exe  : {res.build.exe_path}")
        if res.exe_exit_code is not None:
            print("== EXE RUN ==")
            if res.exe_stdout:
                print(res.exe_stdout, end="" if res.exe_stdout.endswith("\n") else "\n")
            if res.exe_stderr:
                print(res.exe_stderr, end="" if res.exe_stderr.endswith("\n") else "\n")
            print(f"exit={res.exe_exit_code}")

    if args.report is not None:
        write_html_report(args.report, res)
        print(f"[report] wrote {args.report}")

    return 1 if any(d.level == "error" for d in res.diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
