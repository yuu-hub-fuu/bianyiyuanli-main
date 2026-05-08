from __future__ import annotations

import re
import shutil
import subprocess
import tkinter as tk
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from nexa.compiler import BuildResult, compile_source
from nexa.report.html_report import write_html_report

try:
    from PIL import Image, ImageTk
except Exception:  # noqa: BLE001
    Image = None
    ImageTk = None


BG = "#1e1e1e"
PANEL = "#252526"
PANEL_2 = "#2d2d30"
TAB_ACTIVE = "#1e1e1e"
BORDER = "#3c3c3c"
FG = "#d4d4d4"
FG_DIM = "#858585"
BLUE = "#569cd6"
GREEN = "#4ec9b0"
YELLOW = "#dcdcaa"
ORANGE = "#ce9178"
RED = "#f44747"
PURPLE = "#c586c0"
FONT_CODE = ("Cascadia Code", 11)
FONT_CODE_FALLBACK = ("Consolas", 11)
FONT_UI = ("Segoe UI", 10)

OUTPUT_ORDER = ["Tokens", "AST", "Symbols", "HIR", "CFG", "ASM", "LLVM", "Timeline"]
BOTTOM_TABS = ["Problems", "OutputLog", "Run", "Trace"]

LANG = {
    "zh": {
        "run": "▶ 运行",
        "compile": "⚙ 编译",
        "open": "📂 打开",
        "open_file": "📄 打开文件",
        "open_folder": "📁 打开文件夹",
        "save": "💾 保存",
        "save_as": "另存为",
        "report": "📊 报告",
        "apply_fix": "🔧 应用修复",
        "mode": "模式",
        "language": "语言",
        "source": "源码",
        "output": "输出",
        "artifacts": "编译产物",
        "diagnostics": "诊断",
        "problems": "问题",
        "output_log": "输出",
        "ready": "就绪",
        "compiling": "编译中...",
        "run_disabled": "未运行",
        "trace_disabled": "未启用跟踪",
        "graph_pending": "编译后显示图像。",
        "pillow_missing": "需要安装 Pillow>=10 才能显示图像。",
        "dot_missing": "未找到 Graphviz dot。请安装 Graphviz，并把 bin 目录加入 PATH，或设置 GRAPHVIZ_DOT。",
        "dot_failed": "Graphviz 渲染失败。",
        "shortcuts_title": "Nexa Studio 快捷键",
        "shortcuts": "Ctrl+Enter  编译\nF5          运行并跟踪\nCtrl+O      打开\nCtrl+S      保存\nF1          快捷键\nCtrl+滚轮    缩放 AST/CFG 图像",
        "no_fix": "没有可自动应用的修复建议。",
        "quick_fixes": "快速修复",
        "apply_selected": "应用选中",
        "apply_all_safe": "应用全部安全修复",
        "jump": "跳转",
        "close": "关闭",
        "safe_fixed": "已应用安全修复",
        "collapse_bottom": "收起底部",
        "expand_bottom": "展开底部",
        "explorer": "资源管理器",
        "goto_definition": "跳转到定义",
        "definition_not_found": "没有找到定义",
        "context_compile": "编译",
        "context_run": "运行",
        "tokens": "🔤 词法 Tokens",
        "ast": "🌳 语法树 AST",
        "symbols": "📋 符号表 Symbols",
        "hir": "📝 HIR",
        "cfg": "🔀 控制流 CFG",
        "asm": "⚡ 汇编 ASM",
        "llvm": "🔷 LLVM IR",
        "timeline": "⏱ 流水线 Timeline",
        "run_tab": "▶ 运行 Run",
        "trace": "🔍 跟踪 Trace",
    },
    "en": {
        "run": "▶ Run",
        "compile": "⚙ Compile",
        "open": "📂 Open",
        "open_file": "📄 Open File",
        "open_folder": "📁 Open Folder",
        "save": "💾 Save",
        "save_as": "Save As",
        "report": "📊 Report",
        "apply_fix": "🔧 Apply Fix",
        "mode": "Mode",
        "language": "Language",
        "source": "Source",
        "output": "Output",
        "artifacts": "Artifacts",
        "diagnostics": "Diagnostics",
        "problems": "Problems",
        "output_log": "Output",
        "ready": "Ready",
        "compiling": "Compiling...",
        "run_disabled": "(run disabled)",
        "trace_disabled": "(trace disabled)",
        "graph_pending": "Graph image will appear after compile.",
        "pillow_missing": "Install Pillow>=10 to display graph images.",
        "dot_missing": "Graphviz dot was not found. Install Graphviz and add its bin directory to PATH, or set GRAPHVIZ_DOT.",
        "dot_failed": "Graphviz render failed.",
        "shortcuts_title": "Nexa Studio Shortcuts",
        "shortcuts": "Ctrl+Enter  Compile\nF5          Run with trace\nCtrl+O      Open\nCtrl+S      Save\nF1          Shortcuts\nCtrl+Wheel  Zoom AST/CFG graph",
        "no_fix": "No automatic fix-it is available.",
        "quick_fixes": "Quick Fixes",
        "apply_selected": "Apply Selected",
        "apply_all_safe": "Apply All Safe",
        "jump": "Jump",
        "close": "Close",
        "safe_fixed": "Applied safe fixes",
        "collapse_bottom": "Collapse Bottom",
        "expand_bottom": "Expand Bottom",
        "explorer": "Explorer",
        "goto_definition": "Go to Definition",
        "definition_not_found": "Definition not found",
        "context_compile": "Compile",
        "context_run": "Run",
        "tokens": "🔤 Tokens",
        "ast": "🌳 AST",
        "symbols": "📋 Symbols",
        "hir": "📝 HIR",
        "cfg": "🔀 CFG",
        "asm": "⚡ ASM",
        "llvm": "🔷 LLVM IR",
        "timeline": "⏱ Timeline",
        "run_tab": "▶ Run",
        "trace": "🔍 Trace",
    },
}

OUTPUT_LABEL_KEYS = {
    "Tokens": "tokens",
    "AST": "ast",
    "Symbols": "symbols",
    "HIR": "hir",
    "CFG": "cfg",
    "ASM": "asm",
    "LLVM": "llvm",
    "Timeline": "timeline",
    "Run": "run_tab",
    "Trace": "trace",
}

BOTTOM_LABEL_KEYS = {
    "Problems": "problems",
    "OutputLog": "output_log",
    "Run": "run_tab",
    "Trace": "trace",
}


SAMPLE = """fn main() -> i32 {
  let sum: i32 = 0;
  for let i: i32 = 0; i < 4; i = i + 1 {
    if i == 2 { continue; }
    sum = sum + i;
  }
  return sum;
}
"""


class NexaStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nexa Studio")
        self.geometry("1480x920")
        self.minsize(1100, 680)
        self.configure(bg=BG)

        self.current_file: Path | None = None
        self.last_result: BuildResult | None = None
        self._highlight_job: str | None = None
        self._graph_images: dict[str, object] = {}
        self._graph_paths: dict[str, Path] = {}
        self._graph_scales: dict[str, float] = {}
        self._pan_start: tuple[int, int] | None = None
        self.code_font = self._choose_code_font()
        self.lang = tk.StringVar(value="zh")
        self.output_choice = tk.StringVar(value="Tokens")
        self.current_output = "Tokens"
        self.output_label_to_name: dict[str, str] = {}
        self.toolbar_buttons: dict[str, ttk.Button] = {}
        self.static_labels: dict[str, ttk.Label] = {}
        self.output_frames: dict[str, ttk.Frame] = {}
        self.bottom_frames: dict[str, ttk.Frame] = {}
        self.bottom_text_views: dict[str, tk.Text] = {}
        self.workspace_root = Path.cwd()
        self.file_tree_nodes: dict[str, Path] = {}
        self.definition_index: dict[str, tuple[Path | None, int, int, str]] = {}
        self._bottom_collapsed = False
        self._panes_initialized = False

        self._setup_style()
        self._build_ui()
        self._apply_language()
        self._bind_keys()
        self._build_editor_context_menu()
        self.editor.insert("1.0", SAMPLE)
        self._highlight_source()
        self.compile_now(run=False, trace=False)

    def _choose_code_font(self) -> tuple[str, int]:
        available = set(tkfont.families(self))
        for family in ("Cascadia Code", "JetBrains Mono", "Fira Code", "Consolas"):
            if family in available:
                return (family, 11)
        return FONT_CODE_FALLBACK

    def _t(self, key: str) -> str:
        lang = self.lang.get() if hasattr(self, "lang") else "zh"
        return LANG.get(lang, LANG["zh"]).get(key, key)

    def _output_label(self, name: str) -> str:
        return self._t(OUTPUT_LABEL_KEYS.get(name, name.lower()))

    def _bottom_label(self, name: str) -> str:
        return self._t(BOTTOM_LABEL_KEYS.get(name, name.lower()))

    def _setup_style(self) -> None:
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(".", background=PANEL, foreground=FG, font=FONT_UI)
        self.style.configure("TFrame", background=PANEL)
        self.style.configure("Root.TFrame", background=BG)
        self.style.configure("Panel.TFrame", background=PANEL)
        self.style.configure("Toolbar.TFrame", background=PANEL)
        self.style.configure("TLabel", background=PANEL, foreground=FG)
        self.style.configure("Dim.TLabel", background=PANEL, foreground=FG_DIM)
        self.style.configure("Status.TLabel", background=PANEL_2, foreground=FG_DIM)
        self.style.configure("Accent.TButton", background=BLUE, foreground="#ffffff", bordercolor=BLUE, focusthickness=0, padding=(12, 5))
        self.style.map("Accent.TButton", background=[("active", "#1688d3")])
        self.style.configure("TButton", background=PANEL_2, foreground=FG, bordercolor=BORDER, padding=(10, 5), focusthickness=0, relief="flat")
        self.style.map("TButton", background=[("active", "#333337")], foreground=[("disabled", FG_DIM)])
        self.style.configure("TCombobox", fieldbackground=BG, background=PANEL_2, foreground=FG, arrowcolor=FG, bordercolor=BORDER)
        self.style.configure("TNotebook", background=BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=PANEL_2, foreground=FG_DIM, padding=(12, 7), borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", TAB_ACTIVE)], foreground=[("selected", FG)])
        self.style.configure("TPanedwindow", background=BORDER)
        self.style.configure("Treeview", background=BG, fieldbackground=BG, foreground=FG, bordercolor=BORDER, rowheight=24, font=self.code_font)
        self.style.configure("Treeview.Heading", background=PANEL_2, foreground=FG_DIM, relief="flat", font=("Segoe UI", 9))
        self.style.map("Treeview", background=[("selected", "#094771")], foreground=[("selected", "#ffffff")])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_toolbar()

        self.main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.main_pane.grid(row=1, column=0, sticky="nsew")

        self.work_pane = ttk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL)
        self.main_pane.add(self.work_pane, weight=8)

        self.explorer_panel = ttk.Frame(self.work_pane, style="Panel.TFrame")
        self.explorer_panel.rowconfigure(1, weight=1)
        self.explorer_panel.columnconfigure(0, weight=1)
        self._build_explorer(self.explorer_panel)
        self.work_pane.add(self.explorer_panel, weight=16)
        self.explorer_visible = True

        self.editor_panel = ttk.Frame(self.work_pane, style="Root.TFrame")
        self.editor_panel.rowconfigure(1, weight=1)
        self.editor_panel.columnconfigure(0, weight=1)
        self._build_editor_header(self.editor_panel)
        self._build_editor(self.editor_panel)
        self.work_pane.add(self.editor_panel, weight=42)

        self.output_panel = ttk.Frame(self.work_pane, style="Root.TFrame")
        self.output_panel.rowconfigure(0, weight=0)
        self.output_panel.rowconfigure(1, weight=1)
        self.output_panel.columnconfigure(0, weight=1)
        self._build_notebook(self.output_panel)
        self.work_pane.add(self.output_panel, weight=42)

        self.bottom_panel = ttk.Frame(self.main_pane, style="Panel.TFrame")
        self.bottom_panel.rowconfigure(0, weight=1)
        self.bottom_panel.columnconfigure(0, weight=1)
        self._build_diagnostics(self.bottom_panel)
        self.main_pane.add(self.bottom_panel, weight=2)

        self._build_statusbar()
        self.after(120, self._set_initial_panes)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 6))
        toolbar.grid(row=0, column=0, sticky="ew")

        buttons = [
            ("run", lambda: self.compile_now(run=True, trace=True), "Accent.TButton", (0, 6)),
            ("compile", lambda: self.compile_now(run=False, trace=False), "TButton", (0, 6)),
            ("open_file", self.open_file, "TButton", (8, 6)),
            ("open_folder", self.open_folder, "TButton", (0, 6)),
            ("save", self.save_file, "TButton", (0, 6)),
            ("save_as", self.save_file_as, "TButton", (0, 6)),
            ("report", self.export_report, "TButton", (8, 6)),
            ("apply_fix", self.apply_first_fix, "TButton", (0, 6)),
        ]
        for key, command, style, padx in buttons:
            btn = ttk.Button(toolbar, text=key, style=style, command=command)
            btn.pack(side=tk.LEFT, padx=padx)
            self.toolbar_buttons[key] = btn

        self.static_labels["mode"] = ttk.Label(toolbar, text="Mode")
        self.static_labels["mode"].pack(side=tk.LEFT, padx=(18, 5))
        self.mode = tk.StringVar(value="full")
        mode = ttk.Combobox(toolbar, textvariable=self.mode, values=("full", "core"), width=8, state="readonly")
        mode.pack(side=tk.LEFT)

        self.static_labels["language"] = ttk.Label(toolbar, text="Language")
        self.static_labels["language"].pack(side=tk.LEFT, padx=(14, 5))
        lang_box = ttk.Combobox(
            toolbar,
            textvariable=self.lang,
            values=("zh", "en"),
            width=5,
            state="readonly",
        )
        lang_box.pack(side=tk.LEFT)
        lang_box.bind("<<ComboboxSelected>>", lambda _e: self._apply_language())

        self.file_label = ttk.Label(toolbar, text="untitled.nx", style="Dim.TLabel")
        self.file_label.pack(side=tk.RIGHT, padx=(10, 0))

    def _set_initial_panes(self) -> None:
        if self._panes_initialized:
            return
        self.update_idletasks()
        try:
            main_h = max(self.main_pane.winfo_height(), 1)
            work_w = max(self.work_pane.winfo_width(), 1)
            # Keep the bottom panel useful but modest on first open.
            self.main_pane.sashpos(0, max(360, int(main_h * 0.76)))
            self.work_pane.sashpos(0, min(260, max(180, int(work_w * 0.16))))
            self.work_pane.sashpos(1, max(520, int(work_w * 0.56)))
            self._panes_initialized = True
        except tk.TclError:
            self.after(120, self._set_initial_panes)

    def _show_explorer(self) -> None:
        if self.explorer_visible:
            return
        try:
            self.work_pane.insert(0, self.explorer_panel, weight=16)
            self.explorer_visible = True
            self.after(40, self._reset_horizontal_panes)
        except tk.TclError:
            pass

    def _hide_explorer(self) -> None:
        if not self.explorer_visible:
            return
        try:
            self.work_pane.forget(self.explorer_panel)
            self.explorer_visible = False
            self.after(40, self._reset_horizontal_panes)
        except tk.TclError:
            pass

    def _reset_horizontal_panes(self) -> None:
        self.update_idletasks()
        try:
            work_w = max(self.work_pane.winfo_width(), 1)
            if self.explorer_visible:
                self.work_pane.sashpos(0, min(260, max(180, int(work_w * 0.16))))
                self.work_pane.sashpos(1, max(520, int(work_w * 0.56)))
            else:
                self.work_pane.sashpos(0, max(420, int(work_w * 0.48)))
        except tk.TclError:
            pass

    def _toggle_bottom_panel(self) -> None:
        self.update_idletasks()
        try:
            height = max(self.main_pane.winfo_height(), 1)
            if self._bottom_collapsed:
                self.main_pane.sashpos(0, max(360, int(height * 0.76)))
                self._bottom_collapsed = False
            else:
                self.main_pane.sashpos(0, max(420, height - 34))
                self._bottom_collapsed = True
            self.bottom_toggle.configure(text=self._t("expand_bottom") if self._bottom_collapsed else self._t("collapse_bottom"))
        except tk.TclError:
            pass

    def _build_explorer(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["explorer"] = ttk.Label(header, text=self._t("explorer"), font=("Segoe UI", 10, "bold"))
        self.static_labels["explorer"].pack(side=tk.LEFT)
        ttk.Button(header, text="↻", width=3, command=self._refresh_explorer).pack(side=tk.RIGHT)

        self.file_tree = ttk.Treeview(parent, show="tree", selectmode="browse")
        self.file_tree.grid(row=1, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.file_tree.yview)
        yscroll.grid(row=1, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=yscroll.set)
        self.file_tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.file_tree.bind("<Double-1>", self._open_selected_tree_file)
        self._refresh_explorer()

    def _refresh_explorer(self) -> None:
        if not hasattr(self, "file_tree"):
            return
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_tree_nodes.clear()
        root = self.workspace_root.resolve()
        root_id = self.file_tree.insert("", tk.END, text=f"▾ {root.name.upper()}", open=True)
        self.file_tree_nodes[root_id] = root
        self._populate_tree_node(root_id, root)

    def _populate_tree_node(self, parent_id: str, path: Path) -> None:
        self.file_tree.delete(*self.file_tree.get_children(parent_id))
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            if self._hide_from_explorer(child):
                continue
            text = ("▸ " if child.is_dir() else self._file_icon(child)) + child.name
            node = self.file_tree.insert(parent_id, tk.END, text=text, open=False)
            self.file_tree_nodes[node] = child
            if child.is_dir():
                self.file_tree.insert(node, tk.END, text="")

    def _hide_from_explorer(self, path: Path) -> bool:
        hidden_names = {
            "__pycache__",
            ".pytest_cache",
            ".pytest-tmp",
            ".git",
            "nexa.egg-info",
            "pytest-cache-files-8sqwlt6m",
            "pytest-cache-files-tz46f7sv",
            "pytest-cache-files-vphbmkpt",
            "pytest-cache-files-yl0hddtk",
        }
        if path.name in hidden_names:
            return True
        if path.name.endswith(".egg-info"):
            return True
        return False

    def _file_icon(self, path: Path) -> str:
        if path.suffix == ".nx":
            return "◆ "
        if path.suffix == ".py":
            return "🐍 "
        if path.suffix in {".md", ".txt"}:
            return "☰ "
        return "• "

    def _on_tree_open(self, _event=None) -> None:
        selected = self.file_tree.focus()
        path = self.file_tree_nodes.get(selected)
        if path and path.is_dir():
            self._populate_tree_node(selected, path)

    def _open_selected_tree_file(self, _event=None) -> None:
        selected = self.file_tree.focus()
        path = self.file_tree_nodes.get(selected)
        if path and path.is_file():
            self._load_file(path)

    def _build_editor_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["source"] = ttk.Label(header, text="Source", font=("Segoe UI", 10, "bold"))
        self.static_labels["source"].pack(side=tk.LEFT)
        self.breadcrumb = ttk.Label(header, text="untitled.nx - 1:1", style="Dim.TLabel")
        self.breadcrumb.pack(side=tk.RIGHT)

    def _build_editor(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Root.TFrame")
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self.line_numbers = tk.Text(
            frame,
            width=5,
            padx=8,
            pady=8,
            bg=PANEL,
            fg=FG_DIM,
            relief=tk.FLAT,
            highlightthickness=0,
            state=tk.DISABLED,
            font=self.code_font,
            takefocus=False,
        )
        self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.editor = tk.Text(
            frame,
            wrap="none",
            font=self.code_font,
            undo=True,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            selectbackground="#264f78",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BLUE,
            padx=10,
            pady=8,
        )
        self.editor.grid(row=0, column=1, sticky="nsew")

        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._on_editor_scrollbar)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.editor.xview)
        yscroll.grid(row=0, column=2, sticky="ns")
        xscroll.grid(row=1, column=1, sticky="ew")
        self.editor.configure(yscrollcommand=lambda first, last: self._on_editor_scroll(first, last, yscroll), xscrollcommand=xscroll.set)

        self.editor.tag_configure("keyword", foreground=BLUE)
        self.editor.tag_configure("type", foreground=GREEN)
        self.editor.tag_configure("number", foreground=ORANGE)
        self.editor.tag_configure("string", foreground=ORANGE)
        self.editor.tag_configure("comment", foreground=FG_DIM)
        self.editor.tag_configure("operator", foreground=FG)
        self.editor.tag_configure("escape", foreground=YELLOW)
        self.editor.tag_configure("function", foreground=YELLOW)
        self.editor.tag_configure("current_line", background="#242424")
        self.editor.tag_configure("bracket_match", background="#515c6a")
        self.editor.tag_configure("definition_target", background="#264f78")
        self.editor.tag_configure("diagnostic_error", underline=True, foreground=RED)

    def _build_notebook(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        self.static_labels["artifacts"] = ttk.Label(header, text="Artifacts", font=("Segoe UI", 10, "bold"))
        self.static_labels["artifacts"].grid(row=0, column=0, sticky="w")
        self.output_menu = ttk.Combobox(header, textvariable=self.output_choice, values=OUTPUT_ORDER, width=18, state="readonly")
        self.output_menu.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.output_menu.bind("<<ComboboxSelected>>", lambda _e: self._show_output(self.output_choice.get()))

        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.text_views: dict[str, tk.Text] = {}
        self.tables: dict[str, ttk.Treeview] = {}
        self.graph_canvases: dict[str, tk.Canvas] = {}

        self._add_table_tab("Tokens", ("#", "Kind", "Lexeme", "Line:Col"), (50, 120, 260, 90))
        self._add_graph_text_tab("AST")
        self._add_table_tab("Symbols", ("Name", "Category", "Type", "Scope", "Slot"), (160, 110, 160, 80, 80))
        self._add_text_tab("HIR")
        self._add_graph_text_tab("CFG")
        self._add_text_tab("ASM")
        self._add_text_tab("LLVM")
        self._add_table_tab("Timeline", ("Stage", "Status", "Detail"), (150, 90, 360))
        self._add_text_tab("Run")
        self._add_text_tab("Trace")

        self._configure_code_tags()
        for name in OUTPUT_ORDER:
            if name != self.current_output and name in self.output_frames:
                self.notebook.hide(self.output_frames[name])
        self._refresh_output_menu()
        self._show_output(self.current_output)

    def _show_output(self, name: str) -> None:
        name = self.output_label_to_name.get(name, name)
        if name not in self.output_frames:
            return
        self.current_output = name
        label = self._output_label(name)
        if self.output_choice.get() != label:
            self.output_choice.set(label)
        for other, frame in self.output_frames.items():
            if other == name:
                try:
                    self.notebook.add(frame, text=self._output_label(other))
                except tk.TclError:
                    pass
            else:
                try:
                    self.notebook.hide(frame)
                except tk.TclError:
                    pass
        self.notebook.select(self.output_frames[name])

    def _refresh_output_menu(self) -> None:
        self.output_label_to_name = {self._output_label(name): name for name in OUTPUT_ORDER}
        labels = [self._output_label(name) for name in OUTPUT_ORDER]
        self.output_menu.configure(values=labels)
        self.output_choice.set(self._output_label(self.current_output))

    def _apply_language(self) -> None:
        for key, button in self.toolbar_buttons.items():
            button.configure(text=self._t(key))
        for key, label in self.static_labels.items():
            label.configure(text=self._t(key))
        if hasattr(self, "output_menu"):
            self._refresh_output_menu()
            self._show_output(self.current_output)
        if hasattr(self, "bottom_notebook"):
            for name, frame in self.bottom_frames.items():
                self.bottom_notebook.tab(frame, text=self._bottom_label(name))
        if hasattr(self, "diag_summary"):
            if self.last_result:
                self._render_diagnostics(self.last_result)
            else:
                self.diag_summary.configure(text="0 issues" if self.lang.get() == "en" else "0 个问题")
        if hasattr(self, "status_left") and self.status_left.cget("text") in {"Ready", "就绪"}:
            self.status_left.configure(text=self._t("ready"))
        if hasattr(self, "bottom_toggle"):
            self.bottom_toggle.configure(text=self._t("expand_bottom") if self._bottom_collapsed else self._t("collapse_bottom"))
        if hasattr(self, "editor_menu"):
            self._refresh_editor_context_menu()

    def _add_text_tab(self, name: str) -> None:
        frame = ttk.Frame(self.notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(
            frame,
            wrap="none",
            font=self.code_font,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            selectbackground="#264f78",
            relief=tk.FLAT,
            highlightthickness=0,
            padx=10,
            pady=8,
        )
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.notebook.add(frame, text=self._output_label(name))
        self.output_frames[name] = frame
        self.text_views[name] = text

    def _add_graph_text_tab(self, name: str) -> None:
        frame = ttk.Frame(self.notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        pane = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        pane.grid(row=0, column=0, sticky="nsew")

        image_frame = ttk.Frame(pane, style="Root.TFrame")
        image_frame.rowconfigure(0, weight=1)
        image_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(image_frame, bg=BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.create_text(16, 16, anchor="nw", text=self._t("graph_pending"), fill=FG_DIM, font=FONT_UI)
        canvas.bind("<ButtonPress-1>", self._start_pan)
        canvas.bind("<B1-Motion>", lambda e, n=name: self._pan_graph(e, n))
        canvas.bind("<Control-MouseWheel>", lambda e, n=name: self._zoom_graph(e, n))
        pane.add(image_frame, weight=2)

        text_frame = ttk.Frame(pane, style="Root.TFrame")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text = tk.Text(
            text_frame,
            wrap="none",
            font=self.code_font,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            selectbackground="#264f78",
            relief=tk.FLAT,
            highlightthickness=0,
            padx=10,
            pady=8,
        )
        yscroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        xscroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        pane.add(text_frame, weight=1)

        self.notebook.add(frame, text=self._output_label(name))
        self.output_frames[name] = frame
        self.text_views[name] = text
        self.graph_canvases[name] = canvas
        self._graph_scales[name] = 1.0

    def _add_table_tab(self, name: str, columns: tuple[str, ...], widths: tuple[int, ...]) -> None:
        frame = ttk.Frame(self.notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=columns, show="headings")
        for column, width in zip(columns, widths):
            table.heading(column, text=column)
            table.column(column, width=width, stretch=True)
        table.tag_configure("ok", foreground=GREEN)
        table.tag_configure("warning", foreground=YELLOW)
        table.tag_configure("failed", foreground=RED)
        table.tag_configure("skipped", foreground=FG_DIM)
        table.tag_configure("error", foreground=RED)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=table.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=table.xview)
        table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.notebook.add(frame, text=self._output_label(name))
        self.output_frames[name] = frame
        self.tables[name] = table

    def _build_diagnostics(self, parent: ttk.Frame) -> None:
        self.bottom_notebook = ttk.Notebook(parent)
        self.bottom_notebook.grid(row=0, column=0, sticky="nsew")

        problems = ttk.Frame(self.bottom_notebook, style="Panel.TFrame")
        problems.rowconfigure(1, weight=1)
        problems.columnconfigure(0, weight=1)
        self.bottom_notebook.add(problems, text=self._bottom_label("Problems"))
        self.bottom_frames["Problems"] = problems

        header = ttk.Frame(problems, style="Panel.TFrame", padding=(10, 5))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["diagnostics"] = ttk.Label(header, text="Diagnostics", font=("Segoe UI", 10, "bold"))
        self.static_labels["diagnostics"].pack(side=tk.LEFT)
        self.diag_summary = ttk.Label(header, text="0 issues", style="Dim.TLabel")
        self.diag_summary.pack(side=tk.RIGHT)

        columns = ("Level", "Message", "Location")
        self.diag_table = ttk.Treeview(problems, columns=columns, show="headings", height=4)
        for column, width in zip(columns, (90, 900, 120)):
            self.diag_table.heading(column, text=column)
            self.diag_table.column(column, width=width, stretch=True)
        self.diag_table.tag_configure("error", foreground=RED)
        self.diag_table.tag_configure("warning", foreground=YELLOW)
        self.diag_table.tag_configure("note", foreground=FG_DIM)
        self.diag_table.grid(row=1, column=0, sticky="nsew")
        self.diag_table.bind("<Double-1>", self._jump_to_selected_diagnostic)

        self._add_bottom_text_tab("OutputLog")
        self._add_bottom_text_tab("Run")
        self._add_bottom_text_tab("Trace")

    def _add_bottom_text_tab(self, name: str) -> None:
        frame = ttk.Frame(self.bottom_notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(
            frame,
            wrap="none",
            font=self.code_font,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            selectbackground="#264f78",
            relief=tk.FLAT,
            highlightthickness=0,
            padx=10,
            pady=8,
        )
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.bottom_notebook.add(frame, text=self._bottom_label(name))
        self.bottom_frames[name] = frame
        self.bottom_text_views[name] = text

    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self, style="Panel.TFrame", padding=(10, 4))
        bar.grid(row=2, column=0, sticky="ew")
        self.status_left = ttk.Label(bar, text=self._t("ready"), style="Status.TLabel")
        self.status_left.pack(side=tk.LEFT)
        self.bottom_toggle = ttk.Button(bar, text=self._t("collapse_bottom"), command=self._toggle_bottom_panel)
        self.bottom_toggle.pack(side=tk.RIGHT, padx=(8, 0))
        self.status_right = ttk.Label(bar, text="", style="Status.TLabel")
        self.status_right.pack(side=tk.RIGHT)

    def _bind_keys(self) -> None:
        self.bind("<Control-Return>", lambda _e: self.compile_now(run=False, trace=False))
        self.bind("<F5>", lambda _e: self.compile_now(run=True, trace=True))
        self.bind("<Control-o>", lambda _e: self.open_file())
        self.bind("<Control-Shift-O>", lambda _e: self.open_folder())
        self.bind("<Control-s>", lambda _e: self.save_file())
        self.bind("<F12>", lambda _e: self.goto_definition())
        self.bind("<F1>", lambda _e: self._show_shortcuts())
        self.editor.bind("<KeyRelease>", lambda _e: (self._highlight_source_later(), self._update_breadcrumb()))
        self.editor.bind("<ButtonRelease-1>", lambda _e: (self._highlight_current_line(), self._highlight_matching_bracket(), self._update_breadcrumb()))
        self.editor.bind("<Control-Button-1>", self._goto_definition_from_click)
        self.editor.bind("<Button-3>", self._show_editor_context_menu)

    def _build_editor_context_menu(self) -> None:
        self.editor_menu = tk.Menu(self, tearoff=False, bg=PANEL_2, fg=FG, activebackground="#094771", activeforeground="#ffffff")
        self._refresh_editor_context_menu()

    def _refresh_editor_context_menu(self) -> None:
        self.editor_menu.delete(0, tk.END)
        self.editor_menu.add_command(label=self._t("goto_definition"), command=self.goto_definition)
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label=self._t("context_compile"), command=lambda: self.compile_now(run=False, trace=False))
        self.editor_menu.add_command(label=self._t("context_run"), command=lambda: self.compile_now(run=True, trace=True))
        self.editor_menu.add_separator()
        self.editor_menu.add_command(label=self._t("apply_fix"), command=self.apply_first_fix)

    def _show_editor_context_menu(self, event) -> str:
        index = self.editor.index(f"@{event.x},{event.y}")
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self._highlight_current_line()
        self._highlight_matching_bracket()
        word = self._identifier_at_index(index)
        state = tk.NORMAL if word else tk.DISABLED
        self.editor_menu.entryconfigure(0, state=state)
        try:
            self.editor_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.editor_menu.grab_release()
        return "break"

    def _configure_code_tags(self) -> None:
        for text in self.text_views.values():
            text.tag_configure("keyword", foreground=BLUE)
            text.tag_configure("type", foreground=GREEN)
            text.tag_configure("number", foreground=ORANGE)
            text.tag_configure("comment", foreground=FG_DIM)
            text.tag_configure("label", foreground=YELLOW)
            text.tag_configure("branch", foreground=RED)
            text.tag_configure("ok", foreground=GREEN)
            text.tag_configure("warning", foreground=YELLOW)
            text.tag_configure("error", foreground=RED)

    def _set_text(self, name: str, content: str, highlighter: str | None = None) -> None:
        text = self.text_views[name]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        if highlighter:
            self._highlight_view(text, highlighter)
        text.configure(state=tk.DISABLED)

    def _set_table(self, name: str, rows: list[tuple], tags: list[str] | None = None) -> None:
        table = self.tables[name]
        table.delete(*table.get_children())
        for index, row in enumerate(rows):
            tag = tags[index] if tags and index < len(tags) else ""
            table.insert("", tk.END, values=row, tags=(tag,) if tag else ())

    def _set_bottom_text(self, name: str, content: str) -> None:
        text = self.bottom_text_views[name]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        text.configure(state=tk.DISABLED)

    def _highlight_view(self, text: tk.Text, kind: str) -> None:
        for tag in ("keyword", "type", "number", "comment", "label", "branch", "ok", "warning", "error"):
            text.tag_remove(tag, "1.0", tk.END)
        content = text.get("1.0", tk.END)
        patterns = {
            "llvm": [
                ("keyword", r"\b(define|declare|private|constant|ret|br|call|store|load|alloca)\b"),
                ("type", r"\b(i32|i1|i8\*|double|void)\b"),
                ("label", r"^[A-Za-z_][\w.]*:"),
                ("number", r"%[\w.]+|@\w+"),
            ],
            "asm": [
                ("label", r"^[A-Za-z_.$][\w.$]*:"),
                ("keyword", r"\b(mov|add|sub|imul|idiv|cmp|jne|jmp|call|ret|leave|push|cqo|sete|setne|setl|setle|setg|setge|movzx)\b"),
                ("type", r"\b(r(?:ax|bx|cx|dx|bp|sp|di|si|1[0-5]|8|9)|e[a-d]x)\b"),
                ("comment", r";.*$"),
            ],
            "hir": [
                ("branch", r"\b(BRANCH_TRUE|BRANCH_READY|JUMP)\b"),
                ("keyword", r"\b(CONST|MOVE|BIN|UNARY|ARG|CALL|RET|PARAM|LABEL|ARRAY_NEW|ARRAY_GET|ARRAY_SET|STRUCT_NEW|FIELD_GET|FIELD_SET)\b"),
                ("type", r"\b(i32|f64|bool|str|Chan|Array)\b"),
            ],
        }.get(kind, [])
        for tag, pattern in patterns:
            for match in re.finditer(pattern, content, flags=re.MULTILINE):
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.end()}c"
                text.tag_add(tag, start, end)

    def _highlight_source_later(self) -> None:
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(120, self._highlight_source)

    def _highlight_source(self) -> None:
        self._highlight_job = None
        content = self.editor.get("1.0", tk.END)
        for tag in ("keyword", "type", "number", "string", "comment", "operator", "escape", "function"):
            self.editor.tag_remove(tag, "1.0", tk.END)
        patterns = [
            ("comment", r"/\*.*?\*/", re.MULTILINE | re.DOTALL),
            ("comment", r"//.*$", re.MULTILINE),
            ("string", r'"(?:[^"\\]|\\.)*"', re.MULTILINE),
            ("escape", r'\\[nrt"\\]', re.MULTILINE),
            ("function", r"\b[A-Za-z_]\w*(?=\s*\()", re.MULTILINE),
            ("keyword", r"\b(import|fn|let|return|if|else|while|for|in|break|continue|struct|enum|match|macro|spawn|select|recv|send|default|true|false)\b", re.MULTILINE),
            ("type", r"\b(i32|f64|bool|str|Chan|Ord)\b", re.MULTILINE),
            ("number", r"\b\d+(?:\.\d+)?\b", re.MULTILINE),
            ("operator", r"->|=>|==|!=|<=|>=|&&|\|\||[+\-*/%=<>!]", re.MULTILINE),
        ]
        for tag, pattern, flags in patterns:
            for match in re.finditer(pattern, content, flags=flags):
                self.editor.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        self._refresh_line_numbers()
        self._highlight_current_line()
        self._highlight_matching_bracket()
        self._update_breadcrumb()
        self._rebuild_definition_index()

    def _highlight_current_line(self) -> None:
        self.editor.tag_remove("current_line", "1.0", tk.END)
        line = self.editor.index(tk.INSERT).split(".")[0]
        self.editor.tag_add("current_line", f"{line}.0", f"{line}.end+1c")
        self.editor.tag_lower("current_line")

    def _highlight_matching_bracket(self) -> None:
        self.editor.tag_remove("bracket_match", "1.0", tk.END)
        idx = self.editor.index(tk.INSERT)
        for offset in ("-1c", ""):
            pos = self.editor.index(f"{idx}{offset}")
            ch = self.editor.get(pos)
            pairs = {"(": ")", "[": "]", "{": "}", ")": "(", "]": "[", "}": "{"}
            if ch in pairs:
                match = self._find_matching_bracket(pos, ch)
                if match:
                    self.editor.tag_add("bracket_match", pos, f"{pos}+1c")
                    self.editor.tag_add("bracket_match", match, f"{match}+1c")
                return

    def _find_matching_bracket(self, pos: str, ch: str) -> str | None:
        opens = "([{"
        forward = ch in opens
        target = {"(": ")", "[": "]", "{": "}", ")": "(", "]": "[", "}": "{"}[ch]
        depth = 0
        text = self.editor.get("1.0", "end-1c")
        start = int(self.editor.count("1.0", pos, "chars")[0])
        rng = range(start, len(text)) if forward else range(start, -1, -1)
        for i in rng:
            c = text[i]
            if c == ch:
                depth += 1
            elif c == target:
                depth -= 1
                if depth == 0:
                    return f"1.0+{i}c"
        return None

    def _update_breadcrumb(self) -> None:
        file_name = str(self.current_file) if self.current_file else "untitled.nx"
        line, col = self.editor.index(tk.INSERT).split(".")
        self.breadcrumb.configure(text=f"{file_name} - {line}:{int(col) + 1}")

    def _line_col_from_offset(self, text: str, offset: int) -> tuple[int, int]:
        line = text.count("\n", 0, offset) + 1
        line_start = text.rfind("\n", 0, offset) + 1
        return line, offset - line_start + 1

    def _resolve_import_path_for_ide(self, raw: str, base_dir: Path) -> Path:
        path = Path(raw)
        if path.suffix == "":
            path = path.with_suffix(".nx")
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve()

    def _rebuild_definition_index(self) -> None:
        source = self.editor.get("1.0", "end-1c")
        current_path = self.current_file.resolve() if self.current_file else None
        base_dir = current_path.parent if current_path else self.workspace_root.resolve()
        index: dict[str, tuple[Path | None, int, int, str]] = {}
        self._scan_definitions(source, current_path, index)
        self._scan_import_definitions(source, base_dir, index, set())
        self.definition_index = index

    def _scan_import_definitions(
        self,
        source: str,
        base_dir: Path,
        index: dict[str, tuple[Path | None, int, int, str]],
        seen: set[Path],
    ) -> None:
        for match in re.finditer(r'^\s*import\s+(?:"([^"]+)"|([A-Za-z_]\w*))\s*;', source, re.MULTILINE):
            raw = match.group(1) or match.group(2) or ""
            path = self._resolve_import_path_for_ide(raw, base_dir)
            alias = path.stem
            line, col = self._line_col_from_offset(source, match.start())
            index.setdefault(alias, (path, 1, 1, "module"))
            if path in seen or not path.exists():
                continue
            seen.add(path)
            try:
                imported = path.read_text(encoding="utf-8-sig")
            except OSError:
                continue
            self._scan_definitions(imported, path, index)
            self._scan_import_definitions(imported, path.parent, index, seen)

    def _scan_definitions(
        self,
        source: str,
        path: Path | None,
        index: dict[str, tuple[Path | None, int, int, str]],
    ) -> None:
        for kind, pattern in (
            ("fn", r"\bfn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"),
            ("struct", r"\bstruct\s+([A-Za-z_]\w*)\b"),
            ("let", r"\blet\s+([A-Za-z_]\w*)\b"),
        ):
            for match in re.finditer(pattern, source):
                name = match.group(1)
                line, col = self._line_col_from_offset(source, match.start(1))
                index[name] = (path, line, col, kind)
                if kind == "fn":
                    params = match.group(2)
                    params_start = match.start(2)
                    for p in re.finditer(r"\b([A-Za-z_]\w*)\s*:", params):
                        pname = p.group(1)
                        pline, pcol = self._line_col_from_offset(source, params_start + p.start(1))
                        # Params are local; only index current file params so F12 is useful
                        # while editing the active function.
                        if path == self.current_file or path is None:
                            index[pname] = (path, pline, pcol, "param")

    def _identifier_at_index(self, index: str) -> str:
        start = self.editor.index(f"{index} wordstart")
        end = self.editor.index(f"{index} wordend")
        word = self.editor.get(start, end)
        return word if re.fullmatch(r"[A-Za-z_]\w*", word) else ""

    def _goto_definition_from_click(self, event) -> str:
        index = self.editor.index(f"@{event.x},{event.y}")
        word = self._identifier_at_index(index)
        self.goto_definition(word)
        return "break"

    def goto_definition(self, symbol: str | None = None) -> None:
        symbol = symbol or self._identifier_at_index(tk.INSERT)
        if not symbol:
            self.status_left.configure(text=self._t("definition_not_found"))
            return
        self._rebuild_definition_index()
        target = self.definition_index.get(symbol)
        if target is None:
            self.status_left.configure(text=f"{self._t('definition_not_found')}: {symbol}")
            return
        path, line, col, kind = target
        if path is not None and (self.current_file is None or path.resolve() != self.current_file.resolve()):
            self._load_file(path, keep_explorer=self.explorer_visible)
        index = f"{line}.{max(col - 1, 0)}"
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self.editor.see(index)
        self.editor.tag_remove("definition_target", "1.0", tk.END)
        self.editor.tag_add("definition_target", index, f"{index}+{len(symbol)}c")
        self.status_left.configure(text=f"{self._t('goto_definition')}: {symbol} ({kind})")

    def _show_shortcuts(self) -> None:
        messagebox.showinfo(
            self._t("shortcuts_title"),
            self._t("shortcuts"),
        )

    def _refresh_line_numbers(self) -> None:
        line_count = int(self.editor.index("end-1c").split(".")[0])
        numbers = "\n".join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.configure(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", numbers)
        self.line_numbers.configure(state=tk.DISABLED)

    def _on_editor_scroll(self, first: str, last: str, scrollbar: ttk.Scrollbar) -> None:
        scrollbar.set(first, last)
        self.line_numbers.yview_moveto(first)

    def _on_editor_scrollbar(self, *args) -> None:
        self.editor.yview(*args)
        self.line_numbers.yview(*args)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Nexa source", "*.nx"), ("All files", "*.*")])
        if not path:
            return
        self._load_file(Path(path), keep_explorer=False)

    def open_folder(self) -> None:
        path = filedialog.askdirectory(initialdir=str(self.workspace_root))
        if not path:
            return
        self.workspace_root = Path(path)
        self._show_explorer()
        self._refresh_explorer()
        self.status_left.configure(text=f"{self._t('open_folder')}: {self.workspace_root}")

    def _load_file(self, target: Path, keep_explorer: bool = True) -> None:
        try:
            text = target.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            messagebox.showerror("Nexa Studio", f"Cannot open non-text file:\n{target}")
            return
        if not keep_explorer:
            self._hide_explorer()
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self.current_file = target
        self.file_label.configure(text=str(target))
        self._highlight_source()
        self.compile_now(run=False, trace=False)

    def save_file(self) -> None:
        if self.current_file is None:
            self.save_file_as()
            return
        self.current_file.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
        self.status_left.configure(text=f"{self._t('save')}: {self.current_file.name}")

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".nx", filetypes=[("Nexa source", "*.nx"), ("All files", "*.*")])
        if not path:
            return
        self.current_file = Path(path)
        self.file_label.configure(text=str(self.current_file))
        self.save_file()

    def export_report(self) -> None:
        if self.last_result is None:
            self.compile_now(run=True, trace=True)
        if self.last_result is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML report", "*.html"), ("All files", "*.*")])
        if not path:
            return
        write_html_report(Path(path), self.last_result)
        self.status_left.configure(text=f"{self._t('report')}: {Path(path).name}")

    def compile_now(self, run: bool = False, trace: bool = False) -> None:
        self._highlight_source()
        self.status_left.configure(text=self._t("compiling"))
        self.update_idletasks()

        source = self.editor.get("1.0", tk.END)
        res = compile_source(source, mode=self.mode.get(), export_dir="out", run=run, trace=trace, source_path=self.current_file)
        self.last_result = res

        self._render_result(res)
        errors = sum(1 for d in res.diagnostics if str(d.level) == "error")
        warnings = sum(1 for d in res.diagnostics if str(d.level) == "warning")
        status = "failed" if errors else "ok"
        if self.lang.get() == "zh":
            status_text = "失败" if errors else "成功"
            self.status_left.configure(text=f"● 编译{status_text}: {errors} 个错误, {warnings} 个警告", foreground=RED if errors else GREEN)
        else:
            self.status_left.configure(text=f"● Compile {status}: {errors} errors, {warnings} warnings", foreground=RED if errors else GREEN)
        self.status_right.configure(text=f"tokens {len(res.artifacts.token_rows)} | symbols {len(res.artifacts.symbol_rows)} | trace {len(res.vm_trace)}")

    def _render_result(self, res: BuildResult) -> None:
        token_rows = [
            (i + 1, row["kind"], row["lexeme"], f'{row["line"]}:{row["col"]}')
            for i, row in enumerate(res.artifacts.token_rows)
        ]
        self._set_table("Tokens", token_rows)

        self._set_text("AST", res.artifacts.ast_text)
        self._set_table(
            "Symbols",
            [(r["name"], r["category"], r["type"], r["scope"], r["slot"]) for r in res.artifacts.symbol_rows],
        )

        hir_lines = ["RAW HIR"]
        hir_lines.extend(self._format_hir_rows(res.artifacts.hir_raw_structured))
        hir_lines.extend(["", "OPTIMIZED HIR"])
        hir_lines.extend(self._format_hir_rows(res.artifacts.hir_opt_structured))
        self._set_text("HIR", "\n".join(hir_lines), "hir")

        cfg_lines = []
        for fn, graph in res.artifacts.cfg_structured.items():
            cfg_lines.append(f"{fn}:")
            cfg_lines.append("  blocks:")
            for block in graph.get("blocks", []):
                cfg_lines.append(f"    [{block['id']}]")
                cfg_lines.extend(f"      {ins}" for ins in block.get("instrs", []))
            cfg_lines.append("  edges:")
            for edge in graph.get("edges", []):
                label = f" ({edge['label']})" if edge.get("label") else ""
                cfg_lines.append(f"    {edge['from']} -> {edge['to']}{label}")
            cfg_lines.append("")
        self._set_text("CFG", "\n".join(cfg_lines))

        self._set_text("ASM", "\n\n".join(f"-- {name} --\n{text}" for name, text in res.artifacts.asm.items()), "asm")
        self._set_text("LLVM", res.artifacts.llvm_ir, "llvm")

        timeline_tags = [stage.status for stage in res.timeline]
        self._set_table("Timeline", [(stage.name, stage.status, stage.detail) for stage in res.timeline], timeline_tags)

        output_lines = [
            "Pipeline",
            *[f"{stage.name:<12} {stage.status:<8} {stage.detail}" for stage in res.timeline],
            "",
            f"tokens={len(res.artifacts.token_rows)} symbols={len(res.artifacts.symbol_rows)} diagnostics={len(res.diagnostics)}",
        ]
        if res.run_value is not None:
            output_lines.append(f"exit={res.run_value}")
        self._set_bottom_text("OutputLog", "\n".join(output_lines))

        run_lines = list(res.run_stdout)
        if res.run_value is not None:
            run_lines.append(f"exit={res.run_value}")
        self._set_bottom_text("Run", "\n".join(run_lines) or self._t("run_disabled"))
        self._set_bottom_text("Trace", "\n".join(f"#{i + 1:04d} {f.fn}@{f.ip} {f.instr:<12} env={f.env}" for i, f in enumerate(res.vm_trace)) or self._t("trace_disabled"))

        self._render_diagnostics(res)
        self._render_graph_images()

    def _format_hir_rows(self, rows: list[dict]) -> list[str]:
        return [
            f"{row['fn']:<14} {row['index']:>3}  {row['kind']:<13} {row['text']}"
            for row in rows
        ]

    def _render_diagnostics(self, res: BuildResult) -> None:
        self.diag_table.delete(*self.diag_table.get_children())
        self.editor.tag_remove("diagnostic_error", "1.0", tk.END)
        for index, diagnostic in enumerate(res.diagnostics):
            level = str(diagnostic.level)
            location = f"{diagnostic.span.line}:{diagnostic.span.col}"
            item = self.diag_table.insert("", tk.END, values=(level, diagnostic.message, location), tags=(level,))
            self.diag_table.set(item, "Location", location)
            if level == "error":
                start = f"{diagnostic.span.line}.{max(diagnostic.span.col - 1, 0)}"
                self.editor.tag_add("diagnostic_error", start, f"{start}+1c")
        errors = sum(1 for d in res.diagnostics if str(d.level) == "error")
        warnings = sum(1 for d in res.diagnostics if str(d.level) == "warning")
        if self.lang.get() == "zh":
            self.diag_summary.configure(text=f"{errors} 个错误, {warnings} 个警告")
        else:
            self.diag_summary.configure(text=f"{errors} errors, {warnings} warnings")

    def _jump_to_selected_diagnostic(self, _event=None) -> None:
        selected = self.diag_table.selection()
        if not selected or self.last_result is None:
            return
        location = self.diag_table.item(selected[0], "values")[2]
        try:
            line, col = (int(part) for part in location.split(":", 1))
        except ValueError:
            return
        for diagnostic in self.last_result.diagnostics:
            if diagnostic.span.line == line and diagnostic.span.col == col:
                self._jump_to_diagnostic(diagnostic)
                return

    def _render_graph_images(self) -> None:
        if Image is None or ImageTk is None:
            for name, canvas in self.graph_canvases.items():
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw", text=self._t("pillow_missing"), fill=YELLOW, font=FONT_UI)
            return
        configured_dot = os.environ.get("GRAPHVIZ_DOT")
        dot = configured_dot if configured_dot and Path(configured_dot).exists() else shutil.which("dot")
        if not dot:
            for name, canvas in self.graph_canvases.items():
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw", text=self._t("dot_missing"), fill=YELLOW, font=FONT_UI)
            return
        out_dir = Path("out")
        ast_dot = out_dir / "ast.dot"
        if ast_dot.exists():
            self._render_dot_file("AST", dot, ast_dot, out_dir / "ast.png")
        cfg_dot = next(out_dir.glob("cfg_*.dot"), None) if out_dir.exists() else None
        if cfg_dot:
            self._render_dot_file("CFG", dot, cfg_dot, cfg_dot.with_suffix(".png"))

    def _render_dot_file(self, name: str, dot: str, src: Path, dst: Path) -> None:
        try:
            subprocess.run([dot, "-Tpng", str(src), "-o", str(dst)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            canvas = self.graph_canvases.get(name)
            if canvas:
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw", text=f"{self._t('dot_failed')} {src.name}", fill=RED, font=FONT_UI)
            return
        self._graph_paths[name] = dst
        self._graph_scales[name] = 1.0
        self._show_graph_image(name)

    def _show_graph_image(self, name: str) -> None:
        if Image is None or ImageTk is None or name not in self._graph_paths:
            return
        canvas = self.graph_canvases.get(name)
        if canvas is None:
            return
        path = self._graph_paths[name]
        scale = self._graph_scales.get(name, 1.0)
        image = Image.open(path)
        if scale != 1.0:
            w = max(1, int(image.width * scale))
            h = max(1, int(image.height * scale))
            image = image.resize((w, h))
        photo = ImageTk.PhotoImage(image)
        self._graph_images[name] = photo
        canvas.delete("all")
        canvas.create_image(12, 12, anchor="nw", image=photo)
        canvas.configure(scrollregion=(0, 0, image.width + 24, image.height + 24))

    def _start_pan(self, event) -> None:
        self._pan_start = (event.x, event.y)

    def _pan_graph(self, event, name: str) -> None:
        canvas = self.graph_canvases.get(name)
        if canvas is None or self._pan_start is None:
            return
        x, y = self._pan_start
        canvas.scan_mark(x, y)
        canvas.scan_dragto(event.x, event.y, gain=1)
        self._pan_start = (event.x, event.y)

    def _zoom_graph(self, event, name: str) -> None:
        current = self._graph_scales.get(name, 1.0)
        self._graph_scales[name] = min(3.0, current * 1.1) if event.delta > 0 else max(0.25, current / 1.1)
        self._show_graph_image(name)

    def apply_first_fix(self) -> None:
        if self.last_result is None:
            return
        fixes = self._collect_fix_items()
        if not fixes:
            messagebox.showinfo("Nexa Studio", self._t("no_fix"))
            return
        self._show_fix_panel(fixes)

    def _collect_fix_items(self) -> list[tuple[str, object, str]]:
        items: list[tuple[str, object, str]] = []
        if self.last_result is None:
            return items
        for diagnostic in self.last_result.diagnostics:
            if not diagnostic.fixits:
                continue
            code = f"{diagnostic.code} " if diagnostic.code else ""
            where = f"{diagnostic.span.line}:{diagnostic.span.col}"
            for fix_text in diagnostic.fixits:
                label = f"[{where}] {code}{diagnostic.message} -> {fix_text}"
                items.append((label, diagnostic, fix_text))
        return items

    def _show_fix_panel(self, fixes: list[tuple[str, object, str]]) -> None:
        win = tk.Toplevel(self)
        win.title(self._t("quick_fixes"))
        win.configure(bg=PANEL)
        win.geometry("760x360")
        win.transient(self)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        frame = ttk.Frame(win, style="Panel.TFrame", padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        listbox = tk.Listbox(
            frame,
            bg=BG,
            fg=FG,
            selectbackground="#094771",
            selectforeground="#ffffff",
            activestyle="none",
            font=self.code_font,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=yscroll.set)
        listbox.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        for label, _diagnostic, _fix in fixes:
            listbox.insert(tk.END, label)
        listbox.selection_set(0)

        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        def selected_item():
            selected = listbox.curselection()
            if not selected:
                return None
            return fixes[selected[0]]

        def apply_selected() -> None:
            item = selected_item()
            if item is None:
                return
            _label, diagnostic, fix_text = item
            if self._apply_fixit(diagnostic, fix_text):
                win.destroy()
                self.compile_now()

        def jump_selected() -> None:
            item = selected_item()
            if item is None:
                return
            _label, diagnostic, _fix_text = item
            self._jump_to_diagnostic(diagnostic)

        def apply_safe() -> None:
            count = self._apply_all_safe_fixes(fixes)
            if count:
                win.destroy()
                self.compile_now()
                self.status_left.configure(text=f"{self._t('safe_fixed')}: {count}")

        ttk.Button(buttons, text=self._t("apply_selected"), style="Accent.TButton", command=apply_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=self._t("apply_all_safe"), command=apply_safe).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=self._t("jump"), command=jump_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=self._t("close"), command=win.destroy).pack(side=tk.RIGHT)
        listbox.bind("<Double-1>", lambda _e: apply_selected())

    def _jump_to_diagnostic(self, diagnostic) -> None:
        index = f"{diagnostic.span.line}.{max(diagnostic.span.col - 1, 0)}"
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self.editor.see(index)

    def _apply_all_safe_fixes(self, fixes: list[tuple[str, object, str]]) -> int:
        semicolons: set[tuple[int, int]] = set()
        for _label, diagnostic, fix_text in fixes:
            if self._is_semicolon_fix(diagnostic, fix_text):
                semicolons.add((diagnostic.span.line, max(diagnostic.span.col - 1, 0)))
        for line, col in sorted(semicolons, reverse=True):
            index = f"{line}.{col}"
            if self.editor.get(index) != ";":
                self.editor.insert(index, ";")
        return len(semicolons)

    def _is_semicolon_fix(self, diagnostic, fix_text: str) -> bool:
        message = diagnostic.message
        return diagnostic.code == "E001" or ";" in fix_text or "semicolon" in message.lower() or "分号" in message or "鍒嗗彿" in message

    def _apply_fixit(self, diagnostic, fix_text: str) -> bool:
        message = diagnostic.message
        line = diagnostic.span.line
        col = max(diagnostic.span.col - 1, 0)
        if self._is_semicolon_fix(diagnostic, fix_text):
            self.editor.insert(f"{line}.{col}", ";")
            return True
        decl_match = re.search(r"let\s+([A-Za-z_]\w*)\s*:\s*([A-Za-z0-9_]+)", fix_text)
        if decl_match or diagnostic.code == "E002" or "未声明" in message:
            name = decl_match.group(1) if decl_match else self._extract_name(message)
            ty = decl_match.group(2) if decl_match else self._infer_fix_type(line)
            current_line = self.editor.get(f"{line}.0", f"{line}.end")
            indent = re.match(r"\s*", current_line).group(0)
            self.editor.insert(f"{line}.0", f"{indent}let {name}: {ty} = {self._default_value(ty)};\n")
            return True
        type_match = re.search(r"(?:改为|to|为)\s*([A-Za-z0-9_]+)", fix_text)
        if type_match or diagnostic.code == "E003" or "类型不匹配" in message:
            desired = type_match.group(1) if type_match else self._infer_fix_type(line)
            text = self.editor.get(f"{line}.0", f"{line}.end")
            match = re.search(r":\s*[A-Za-z0-9_]+", text)
            if match:
                self.editor.delete(f"{line}.{match.start()}", f"{line}.{match.end()}")
                self.editor.insert(f"{line}.{match.start()}", f": {desired}")
            else:
                self.editor.mark_set(tk.INSERT, f"{line}.{col}")
                self.editor.see(tk.INSERT)
            return True
        return False

    def _extract_name(self, message: str) -> str:
        match = re.search(r"['\"]?([A-Za-z_]\w*)['\"]?$", message)
        return match.group(1) if match else "value"

    def _infer_fix_type(self, line: int) -> str:
        text = self.editor.get(f"{line}.0", f"{line}.end")
        if re.search(r"\d+\.\d+", text):
            return "f64"
        if re.search(r"\b(true|false)\b", text):
            return "bool"
        if '"' in text:
            return "str"
        return "i32"

    def _default_value(self, ty: str) -> str:
        return {"f64": "0.0", "bool": "false", "str": '""'}.get(ty, "0")


def main() -> None:
    app = NexaStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
