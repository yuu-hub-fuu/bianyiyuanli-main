"""Drive the host toolchain to produce real .o and .exe artifacts.

Pipeline (Windows, MinGW64):

    .nx  -- nexa frontend -->  MIRModule
                 |
                 v emit_module
            out/<name>.s   (GAS Intel syntax, Win64 ABI)
                 |
                 v gcc -c   (invokes as.exe internally)
            out/<name>.o   (PE/COFF object)
                 |
                 v gcc      (invokes ld.exe + links libc + nexa_rt.c)
            out/<name>.exe  (PE32+ executable; Windows loader can run it)

We deliberately use `gcc` as a single driver rather than calling `as` and
`ld` separately, because it transparently handles CRT linkage, libc
imports, and the right flags for assembling a `.intel_syntax noprefix`
file on Windows.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from nexa.backend.asm_x64 import emit_module
from nexa.ir.mir import MIRModule


_RUNTIME_C = Path(__file__).resolve().parent.parent / "runtime" / "nexa_rt.c"


@dataclass(slots=True)
class BuildOutput:
    asm_path: Path
    object_path: Path
    runtime_object_path: Path
    exe_path: Path
    asm_text: str
    log: list[str]


class BuildError(RuntimeError):
    pass


def _find_gcc() -> str:
    candidate = os.environ.get("NEXA_GCC") or shutil.which("gcc")
    if not candidate:
        raise BuildError("gcc not found on PATH (set NEXA_GCC or install MinGW64)")
    return candidate


def _run(cmd: list[str], log: list[str]) -> None:
    log.append("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        log.append(proc.stdout.rstrip())
    if proc.stderr:
        log.append(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise BuildError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n" + "\n".join(log[-10:]))


def build_module(
    mod: MIRModule,
    source_stem: str,
    out_dir: str | os.PathLike[str] = "out",
    keep_intermediate: bool = True,
) -> BuildOutput:
    """Lower MIR to .s, assemble to .o, link with the C runtime to .exe."""
    if not _RUNTIME_C.exists():
        raise BuildError(f"runtime source missing: {_RUNTIME_C}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    asm_text = emit_module(mod)

    asm_path = out / f"{source_stem}.s"
    obj_path = out / f"{source_stem}.o"
    rt_obj_path = out / f"{source_stem}_rt.o"
    exe_path = out / f"{source_stem}.exe"

    asm_path.write_text(asm_text, encoding="utf-8")

    gcc = _find_gcc()
    log: list[str] = []

    # Step 1: assemble user .s into .o.
    _run([gcc, "-c", str(asm_path), "-o", str(obj_path)], log)

    # Step 2: compile the C runtime to .o.
    _run([gcc, "-c", str(_RUNTIME_C), "-o", str(rt_obj_path)], log)

    # Step 3: link both into the final .exe.
    _run([gcc, str(obj_path), str(rt_obj_path), "-o", str(exe_path)], log)

    if not keep_intermediate:
        for p in (asm_path, obj_path, rt_obj_path):
            try:
                p.unlink()
            except OSError:
                pass

    return BuildOutput(
        asm_path=asm_path,
        object_path=obj_path,
        runtime_object_path=rt_obj_path,
        exe_path=exe_path,
        asm_text=asm_text,
        log=log,
    )


def run_executable(exe: Path, args: list[str] | None = None, timeout: float = 10.0) -> tuple[int, str, str]:
    cmd = [str(exe)] + (args or [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr
