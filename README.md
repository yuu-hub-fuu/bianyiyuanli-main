# Nexa Compiler Project

## 快速开始

```bash
python -m pip install pytest
python nexa_cli.py example.nx --mode core --dump tables --run
python nexa_cli.py example.nx --mode full --dump all --run --trace --report out/report.html
pytest -q
```

## 语言特性徽章

- Core ✅（变量/表达式/if/while/符号表/四元式）
- Struct ✅
- Macro ⚠️ AST-level macro expansion with depth limit + teaching gensym
- Generic ⚠️ monomorph demo（调用点实例化）
- Select ⚠️ lowering 为 `br.ready + recv + default` 的非阻塞子集（仅教学运行时路径）
- LLVM ⚠️ 仅支持线性整数子集（不支持 `if/while/select/chan/str` 的 HIR 控制流）
- x86-64 ⚠️ teaching text emitter（可读目标代码）

## 验收输出（CLI）

`--dump tables` 或 `--dump all` 输出：

- 关键字表
- 界符表
- 标识符表
- 常量表
- 符号表
- 四元式表（HIR）

## 模式

- `--mode core`：课程基础模式（稳定答辩路径）
- `--mode full`：高分展示模式（宏/泛型/select/可视化）

## 运行模式（VM）

`--run` 会使用 `nexa.vm.HIRVM` 执行 HIR，保证课程演示“可运行闭环”。

`--trace` 可打印 VM 指令级 trace；`--report out/report.html` 可生成课程化 HTML 报告（词法/符号/四元式/CFG/运行结果/诊断，若存在则嵌入 AST/CFG SVG）。

## 图形界面

```bash
python -m nexa.ide.app
```

界面包含：源码区、HIR Table、Symbol Tree、Diagnostics Groups、Run Output、Trace Panel、CFG/ASM/Timeline。

## 可视化导出

编译时会输出 DOT 文件：

- `out/ast.dot`
- `out/cfg_<fn>.dot`

安装 `graphviz` Python 包后会自动生成对应 SVG 文件。
