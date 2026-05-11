# tkinter 桌面图形化 IDE 说明

当前 IDE 主入口是：

```bash
python -m nexa.ide.app
```

`nexa/ide/app.py` 是 Python tkinter + ttk 桌面图形化程序，主类为 `NexaStudio(tk.Tk)`。它不是 FastAPI/WebSocket 网页端，也不是 PySide6。

桌面 IDE 支持源码编辑、Token、AST、符号表、HIR、CFG、ASM、LLVM、Timeline、Run、Trace、诊断、快速修复和 HTML 报告导出。
