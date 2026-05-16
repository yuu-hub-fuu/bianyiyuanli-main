from __future__ import annotations

import re
import shutil
import subprocess
import time
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


# ── Colour palette (VS Code Dark+ - Modern) ────────────────────────────────
BG       = "#1e1e1e"      # 主背景
PANEL    = "#252526"      # 一级面板
PANEL_2  = "#2d2d30"      # 二级面板（活跃）
PANEL_3  = "#3c3c3c"      # 三级面板（不活跃/悬停）
TAB_ACTIVE = "#1e1e1e"    # 活动标签
BORDER   = "#3c3c3c"      # 边框
FG       = "#e0e0e0"      # 前景文字（更亮）
FG_DIM   = "#858585"      # 暗文字
BLUE     = "#4db8ff"      # 主蓝色（更亮）
GREEN    = "#52d97f"      # 主绿色（更亮）
YELLOW   = "#dcdcaa"      # 黄色
ORANGE   = "#ff9966"      # 橙色（更亮）
RED      = "#ff5555"      # 红色（更亮）
PURPLE   = "#d99dff"      # 紫色（更亮）
ACCENT   = "#0078d4"      # 强调色
ACCENT_H = "#1f8ad4"      # 强调色（悬停）
SEL_BG   = "#264f78"      # 选择背景
FIND_BG  = "#2d2d30"      # 查找栏背景

FONT_CODE_FALLBACK = ("Consolas", 11)
FONT_UI  = ("Segoe UI", 10)

OUTPUT_ORDER = ["Tokens", "AST", "Symbols", "HIR", "CFG", "ASM", "LLVM", "Timeline"]
BOTTOM_TABS  = ["Problems", "OutputLog", "Run", "Trace"]

LANG = {
    "zh": {
        "run":              "▶  运行",
        "compile":          "⚙  编译",
        "new":              "新建",
        "open_file":        "打开文件",
        "open_folder":      "打开文件夹",
        "save":             "保存",
        "save_as":          "另存为",
        "report":           "导出报告",
        "apply_fix":        "🔧 修复",
        "mode":             "模式",
        "language":         "界面语言",
        "source":           "源码",
        "output":           "输出",
        "artifacts":        "编译产物",
        "diagnostics":      "诊断",
        "problems":         "问题",
        "output_log":       "输出日志",
        "ready":            "就绪",
        "compiling":        "编译中…",
        "run_disabled":     "（未运行）",
        "trace_disabled":   "（未启用跟踪）",
        "graph_pending":    "编译后显示图像。",
        "pillow_missing":   "需要安装 Pillow ≥10 才能显示图像。",
        "dot_missing":      "未找到 Graphviz dot。请安装 Graphviz 并将 bin 目录加入 PATH，或设置 GRAPHVIZ_DOT。",
        "dot_failed":       "Graphviz 渲染失败。",
        "shortcuts_title":  "Nexa Studio 快捷键",
        "shortcuts": (
            "Ctrl+Enter    编译\n"
            "F5            运行并跟踪\n"
            "Ctrl+O        打开文件\n"
            "Ctrl+Shift+O  打开文件夹\n"
            "Ctrl+S        保存\n"
            "Ctrl+N        新建\n"
            "Ctrl+F        查找\n"
            "Ctrl+H        查找并替换\n"
            "Ctrl+=        放大字体\n"
            "Ctrl+-        缩小字体\n"
            "Ctrl+0        重置字体\n"
            "F12           跳转到定义\n"
            "F1            显示快捷键\n"
            "Ctrl+滚轮      缩放 AST/CFG 图像"
        ),
        "no_fix":           "没有可自动应用的修复建议。",
        "quick_fixes":      "快速修复",
        "apply_selected":   "应用选中",
        "apply_all_safe":   "应用全部安全修复",
        "jump":             "跳转",
        "close":            "关闭",
        "safe_fixed":       "已应用安全修复",
        "collapse_bottom":  "收起底部",
        "expand_bottom":    "展开底部",
        "explorer":         "资源管理器",
        "goto_definition":  "跳转到定义",
        "definition_not_found": "没有找到定义",
        "context_compile":  "编译",
        "context_run":      "运行",
        "tokens":    "🔤 Tokens",
        "ast":       "🌳 AST",
        "symbols":   "📋 符号表",
        "hir":       "📝 HIR",
        "cfg":       "🔀 CFG",
        "asm":       "⚡ ASM",
        "llvm":      "🔷 LLVM",
        "timeline":  "⏱ 流水线",
        "run_tab":   "▶ 运行",
        "trace":     "🔍 跟踪",
        # menus
        "menu_file":   "文件",
        "menu_edit":   "编辑",
        "menu_view":   "视图",
        "menu_run":    "运行",
        "menu_help":   "帮助",
        "mi_new":       "新建文件",
        "mi_open_file": "打开文件…",
        "mi_open_dir":  "打开文件夹…",
        "mi_save":      "保存",
        "mi_save_as":   "另存为…",
        "mi_export":    "导出报告…",
        "mi_exit":      "退出",
        "mi_undo":      "撤销",
        "mi_redo":      "重做",
        "mi_find":      "查找…",
        "mi_replace":   "查找并替换…",
        "mi_select_all":"全选",
        "mi_fix":       "应用修复",
        "mi_zoom_in":   "放大字体",
        "mi_zoom_out":  "缩小字体",
        "mi_zoom_rst":  "重置字体",
        "mi_wrap":      "自动换行",
        "mi_explorer":  "切换资源管理器",
        "mi_bottom":    "切换底部面板",
        "mi_compile":   "编译",
        "mi_run_trace": "运行并跟踪",
        "mi_shortcuts": "快捷键…",
        "mi_about":     "关于 Nexa Studio",
        # git panel
        "source_control": "源代码管理",
        "git_branch":   "当前分支",
        "git_changes":  "更改",
        "git_staged":   "已暂存",
        "git_unstaged": "未暂存",
        "git_commit":   "提交",
        "git_commit_msg":"输入提交信息…",
        "git_push":     "推送",
        "git_pull":     "拉取",
        "git_refresh":  "刷新",
        "git_init":     "初始化仓库",
        "git_no_repo":  "当前目录不是Git仓库",
        "git_commits_ahead": "领先提交",
        "git_commits_behind":"落后提交",
        # find bar
        "find_placeholder":    "查找…",
        "replace_placeholder": "替换…",
        "find_prev":    "↑",
        "find_next":    "↓",
        "find_close":   "✕",
        "replace_one":  "替换",
        "replace_all":  "全部替换",
        "case_sensitive":"Aa",
        "wrap_search":  "↩",
        "find_result":  "{n} 个匹配",
        "find_none":    "无匹配",
        # about
        "about_title":  "关于 Nexa Studio",
        "about_body":   "Nexa Studio\n现代化编译器 IDE\n\n支持词法分析、语法分析、语义分析\nHIR / CFG / ASM / LLVM IR\n图形可视化与诊断修复",
    },
    "en": {
        "run":              "▶  Run",
        "compile":          "⚙  Compile",
        "new":              "New",
        "open_file":        "Open File",
        "open_folder":      "Open Folder",
        "save":             "Save",
        "save_as":          "Save As",
        "report":           "Export Report",
        "apply_fix":        "🔧 Fix",
        "mode":             "Mode",
        "language":         "Language",
        "source":           "Source",
        "output":           "Output",
        "artifacts":        "Artifacts",
        "diagnostics":      "Diagnostics",
        "problems":         "Problems",
        "output_log":       "Output",
        "ready":            "Ready",
        "compiling":        "Compiling…",
        "run_disabled":     "(run disabled)",
        "trace_disabled":   "(trace disabled)",
        "graph_pending":    "Graph image will appear after compile.",
        "pillow_missing":   "Install Pillow ≥10 to display graph images.",
        "dot_missing":      "Graphviz dot not found. Install Graphviz and add its bin to PATH, or set GRAPHVIZ_DOT.",
        "dot_failed":       "Graphviz render failed.",
        "shortcuts_title":  "Nexa Studio Shortcuts",
        "shortcuts": (
            "Ctrl+Enter    Compile\n"
            "F5            Run with trace\n"
            "Ctrl+O        Open file\n"
            "Ctrl+Shift+O  Open folder\n"
            "Ctrl+S        Save\n"
            "Ctrl+N        New file\n"
            "Ctrl+F        Find\n"
            "Ctrl+H        Find & Replace\n"
            "Ctrl+=        Zoom in\n"
            "Ctrl+-        Zoom out\n"
            "Ctrl+0        Reset zoom\n"
            "F12           Go to definition\n"
            "F1            Show shortcuts\n"
            "Ctrl+Wheel    Zoom AST/CFG image"
        ),
        "no_fix":           "No automatic fix available.",
        "quick_fixes":      "Quick Fixes",
        "apply_selected":   "Apply Selected",
        "apply_all_safe":   "Apply All Safe",
        "jump":             "Jump",
        "close":            "Close",
        "safe_fixed":       "Applied safe fixes",
        "collapse_bottom":  "Collapse Bottom",
        "expand_bottom":    "Expand Bottom",
        "explorer":         "Explorer",
        "goto_definition":  "Go to Definition",
        "definition_not_found": "Definition not found",
        "context_compile":  "Compile",
        "context_run":      "Run",
        "tokens":    "🔤 Tokens",
        "ast":       "🌳 AST",
        "symbols":   "📋 Symbols",
        "hir":       "📝 HIR",
        "cfg":       "🔀 CFG",
        "asm":       "⚡ ASM",
        "llvm":      "🔷 LLVM",
        "timeline":  "⏱ Timeline",
        "run_tab":   "▶ Run",
        "trace":     "🔍 Trace",
        "menu_file":   "File",
        "menu_edit":   "Edit",
        "menu_view":   "View",
        "menu_run":    "Run",
        "menu_help":   "Help",
        "mi_new":       "New File",
        "mi_open_file": "Open File…",
        "mi_open_dir":  "Open Folder…",
        "mi_save":      "Save",
        "mi_save_as":   "Save As…",
        "mi_export":    "Export Report…",
        "mi_exit":      "Exit",
        "mi_undo":      "Undo",
        "mi_redo":      "Redo",
        "mi_find":      "Find…",
        "mi_replace":   "Find & Replace…",
        "mi_select_all":"Select All",
        "mi_fix":       "Apply Fix",
        "mi_zoom_in":   "Zoom In",
        "mi_zoom_out":  "Zoom Out",
        "mi_zoom_rst":  "Reset Zoom",
        "mi_wrap":      "Word Wrap",
        "mi_explorer":  "Toggle Explorer",
        "mi_bottom":    "Toggle Bottom Panel",
        "mi_compile":   "Compile",
        "mi_run_trace": "Run with Trace",
        "mi_shortcuts": "Keyboard Shortcuts…",
        "mi_about":     "About Nexa Studio",
        # git panel
        "source_control": "Source Control",
        "git_branch":   "Current Branch",
        "git_changes":  "Changes",
        "git_staged":   "Staged",
        "git_unstaged": "Unstaged",
        "git_commit":   "Commit",
        "git_commit_msg":"Enter commit message…",
        "git_push":     "Push",
        "git_pull":     "Pull",
        "git_refresh":  "Refresh",
        "git_init":     "Initialize Repository",
        "git_no_repo":  "Not a git repository",
        "git_commits_ahead": "Commits Ahead",
        "git_commits_behind":"Commits Behind",
        "find_placeholder":    "Find…",
        "replace_placeholder": "Replace…",
        "find_prev":    "↑",
        "find_next":    "↓",
        "find_close":   "✕",
        "replace_one":  "Replace",
        "replace_all":  "Replace All",
        "case_sensitive":"Aa",
        "wrap_search":  "↩",
        "find_result":  "{n} match(es)",
        "find_none":    "No match",
        "about_title":  "About Nexa Studio",
        "about_body":   "Nexa Studio\nModern Compiler IDE\n\nLexical · Parser · Semantic Analysis\nHIR / CFG / ASM / LLVM IR\nGraph Visualization & Quick Fixes",
    },
}

OUTPUT_LABEL_KEYS = {
    "Tokens": "tokens", "AST": "ast", "Symbols": "symbols",
    "HIR": "hir", "CFG": "cfg", "ASM": "asm", "LLVM": "llvm",
    "Timeline": "timeline", "Run": "run_tab", "Trace": "trace",
}
BOTTOM_LABEL_KEYS = {
    "Problems": "problems", "OutputLog": "output_log",
    "Run": "run_tab", "Trace": "trace",
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

# ── Tooltip helper ────────────────────────────────────────────────────────────
class _Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None) -> None:
        if self._tip or not self._text:
            return
        x = self._widget.winfo_rootx() + 0
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=self._text, background="#3c3c3c", foreground=FG,
                       relief="flat", padx=8, pady=4,
                       font=("Segoe UI", 9), borderwidth=1)
        lbl.pack()

    def _hide(self, _event=None) -> None:
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ─────────────────────────────────────────────────────────────────────────────
class NexaStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Nexa Studio")
        self.geometry("1480x920")
        self.minsize(1100, 680)
        self.configure(bg=BG)

        # ── state ────────────────────────────────────────────────────────────
        self.current_file: Path | None = None
        self.last_result: BuildResult | None = None
        self._highlight_job: str | None = None
        self._graph_images: dict[str, object] = {}
        self._graph_paths: dict[str, Path] = {}
        self._graph_scales: dict[str, float] = {}
        self._pan_start: tuple[int, int] | None = None
        self._font_size: int = 11
        self._find_visible: bool = False
        self._replace_visible: bool = False
        self._compile_start: float = 0.0
        self._bottom_collapsed: bool = False
        self._panes_initialized: bool = False
        self._left_panel_mode: str = "explorer"  # or "source_control"
        self.git_repo_root: Path | None = None
        self.git_status: dict = {}
        self.git_branch: str = ""

        self.code_font = self._choose_code_font()
        self.lang = tk.StringVar(value="zh")
        self.mode = tk.StringVar(value="full")
        self._word_wrap_var = tk.BooleanVar(value=False)
        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.find_case_var = tk.BooleanVar(value=False)
        self.find_wrap_var = tk.BooleanVar(value=True)

        self.toolbar_buttons: dict[str, ttk.Button] = {}
        self.static_labels: dict[str, ttk.Label] = {}
        self.output_frames: dict[str, ttk.Frame] = {}
        self.bottom_frames: dict[str, ttk.Frame] = {}
        self.bottom_text_views: dict[str, tk.Text] = {}
        self.text_views: dict[str, tk.Text] = {}
        self.tables: dict[str, ttk.Treeview] = {}
        self.graph_canvases: dict[str, tk.Canvas] = {}
        # Default to test/test1 sandbox if it exists, else cwd
        _default_sandbox = Path(__file__).resolve().parent.parent.parent / "test" / "test1"
        self.workspace_root = _default_sandbox if _default_sandbox.is_dir() else Path.cwd()
        self.file_tree_nodes: dict[str, Path] = {}
        self.definition_index: dict[str, tuple[Path | None, int, int, str]] = {}
        self.explorer_visible: bool = True
        self.open_files: list[Path] = []  # Track open files for editor list

        self._setup_style()
        self._build_menubar()
        self._build_ui()
        self._apply_language()
        self._bind_keys()
        self._build_editor_context_menu()
        self.editor.insert("1.0", SAMPLE)
        self._highlight_source()
        self.compile_now(run=False, trace=False)

    # ── font ─────────────────────────────────────────────────────────────────
    def _choose_code_font(self) -> tuple[str, int]:
        available = set(tkfont.families(self))
        for family in ("Cascadia Code", "JetBrains Mono", "Fira Code", "Consolas"):
            if family in available:
                return (family, self._font_size if hasattr(self, "_font_size") else 11)
        return FONT_CODE_FALLBACK

    def _effective_code_font(self) -> tuple[str, int]:
        return (self.code_font[0], self._font_size)

    def _zoom_editor_font(self, delta: int) -> None:
        if delta == 0:
            self._font_size = 11
        else:
            self._font_size = max(7, min(28, self._font_size + delta))
        f = self._effective_code_font()
        self.editor.configure(font=f)
        self.line_numbers.configure(font=f)
        for tv in self.text_views.values():
            tv.configure(font=f)
        for tv in self.bottom_text_views.values():
            tv.configure(font=f)
        self.style.configure("Treeview", font=f)
        self._set_status_right(f"字体 {self._font_size}pt" if self.lang.get() == "zh" else f"Font {self._font_size}pt")
        self._refresh_line_numbers()

    # ── i18n ─────────────────────────────────────────────────────────────────
    def _t(self, key: str) -> str:
        lang = self.lang.get() if hasattr(self, "lang") else "zh"
        return LANG.get(lang, LANG["zh"]).get(key, key)

    def _output_label(self, name: str) -> str:
        return self._t(OUTPUT_LABEL_KEYS.get(name, name.lower()))

    def _bottom_label(self, name: str) -> str:
        return self._t(BOTTOM_LABEL_KEYS.get(name, name.lower()))

    # ── style ─────────────────────────────────────────────────────────────────
    def _setup_style(self) -> None:
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(".", background=PANEL, foreground=FG, font=FONT_UI)
        self.style.configure("TFrame",       background=PANEL)
        self.style.configure("Root.TFrame",  background=BG)
        self.style.configure("Panel.TFrame", background=PANEL)
        self.style.configure("Toolbar.TFrame", background=PANEL_2,
                             relief="flat", borderwidth=0)
        self.style.configure("FindBar.TFrame", background=FIND_BG)
        self.style.configure("TLabel",       background=PANEL,  foreground=FG)
        self.style.configure("Dim.TLabel",   background=PANEL,  foreground=FG_DIM)
        self.style.configure("Status.TLabel",background=PANEL_2, foreground=FG_DIM,
                             padding=(6, 0))
        # Buttons
        self.style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                             bordercolor=ACCENT, focusthickness=0, padding=(12, 5))
        self.style.map("Accent.TButton",
                       background=[("active", ACCENT_H), ("pressed", "#005a9e")])
        self.style.configure("TButton", background=PANEL_2, foreground=FG,
                             bordercolor=BORDER, padding=(10, 5),
                             focusthickness=0, relief="flat", font=FONT_UI)
        self.style.map("TButton",
                       background=[("active", PANEL_3), ("pressed", "#333337"),
                                   ("!disabled", PANEL_2)],
                       foreground=[("disabled", FG_DIM), ("active", FG)],
                       bordercolor=[("active", "#0078d4")])
        self.style.configure("Small.TButton", background=PANEL_2, foreground=FG_DIM,
                             bordercolor=BORDER, padding=(5, 3),
                             focusthickness=0, relief="flat", font=("Segoe UI", 9))
        self.style.map("Small.TButton",
                       background=[("active", "#3a3a3d")],
                       foreground=[("active", FG)])
        self.style.configure("Find.TButton", background=FIND_BG, foreground=FG_DIM,
                             bordercolor=BORDER, padding=(6, 3),
                             focusthickness=0, relief="flat", font=("Segoe UI", 9))
        self.style.map("Find.TButton",
                       background=[("active", "#3a3a3d")],
                       foreground=[("active", FG)])
        # Combobox
        self.style.configure("TCombobox", fieldbackground=BG, background=PANEL_2,
                             foreground=FG, arrowcolor=FG, bordercolor=BORDER)
        # Notebook
        self.style.configure("TNotebook", background=BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=PANEL_2, foreground=FG_DIM,
                             padding=(11, 7), borderwidth=0, font=("Segoe UI", 9))
        self.style.map("TNotebook.Tab",
                       background=[("selected", TAB_ACTIVE), ("!selected", PANEL_2),
                                   ("active", PANEL_3)],
                       foreground=[("selected", BLUE), ("!selected", FG_DIM),
                                   ("active", FG)],
                       bordercolor=[("selected", BLUE)])
        # PanedWindow
        self.style.configure("TPanedwindow", background=BORDER)
        # Treeview
        self.style.configure("Treeview", background=BG, fieldbackground=BG,
                             foreground=FG, bordercolor=BORDER, rowheight=24,
                             font=self._choose_code_font())
        self.style.configure("Treeview.Heading", background=PANEL_2,
                             foreground=FG, relief="flat",
                             font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Treeview",
                       background=[("selected", "#094771"), ("!selected", BG)],
                       foreground=[("selected", BLUE), ("!selected", FG)],
                       bordercolor=[("selected", BLUE)])
        # Checkbutton (for find bar)
        self.style.configure("Find.TCheckbutton", background=FIND_BG,
                             foreground=FG_DIM, focusthickness=0)
        self.style.map("Find.TCheckbutton",
                       foreground=[("active", FG), ("selected", BLUE)])

    # ── menubar ──────────────────────────────────────────────────────────────
    def _build_menubar(self) -> None:
        self._menubar = tk.Menu(self, bg=PANEL_2, fg=FG,
                                activebackground=ACCENT, activeforeground="#ffffff",
                                borderwidth=0, relief="flat", tearoff=False)
        self.config(menu=self._menubar)
        self._menus: dict[str, tk.Menu] = {}
        self._menu_items: dict[str, list] = {}
        self._rebuild_menubar()

    def _rebuild_menubar(self) -> None:
        self._menubar.delete(0, tk.END)

        def _sub() -> tk.Menu:
            return tk.Menu(self._menubar, tearoff=False, bg=PANEL_2, fg=FG,
                           activebackground=ACCENT, activeforeground="#ffffff",
                           borderwidth=1, relief="solid")

        # File
        fm = _sub()
        fm.add_command(label=self._t("mi_new"),       accelerator="Ctrl+N",       command=self._new_file)
        fm.add_command(label=self._t("mi_open_file"), accelerator="Ctrl+O",       command=self.open_file)
        fm.add_command(label=self._t("mi_open_dir"),  accelerator="Ctrl+Shift+O", command=self.open_folder)
        fm.add_separator()
        fm.add_command(label=self._t("mi_save"),      accelerator="Ctrl+S",       command=self.save_file)
        fm.add_command(label=self._t("mi_save_as"),   accelerator="Ctrl+Shift+S", command=self.save_file_as)
        fm.add_separator()
        fm.add_command(label=self._t("mi_export"),    command=self.export_report)
        fm.add_separator()
        fm.add_command(label=self._t("mi_exit"),      command=self.destroy)
        self._menubar.add_cascade(label=self._t("menu_file"), menu=fm)

        # Edit
        em = _sub()
        em.add_command(label=self._t("mi_undo"),       accelerator="Ctrl+Z",
                       command=lambda: self.editor.event_generate("<<Undo>>"))
        em.add_command(label=self._t("mi_redo"),       accelerator="Ctrl+Y",
                       command=lambda: self.editor.event_generate("<<Redo>>"))
        em.add_separator()
        em.add_command(label=self._t("mi_find"),       accelerator="Ctrl+F",
                       command=lambda: self._toggle_find_bar(replace=False))
        em.add_command(label=self._t("mi_replace"),    accelerator="Ctrl+H",
                       command=lambda: self._toggle_find_bar(replace=True))
        em.add_separator()
        em.add_command(label=self._t("mi_select_all"), accelerator="Ctrl+A",
                       command=lambda: self.editor.tag_add(tk.SEL, "1.0", tk.END))
        em.add_command(label=self._t("mi_fix"),        command=self.apply_first_fix)
        self._menubar.add_cascade(label=self._t("menu_edit"), menu=em)

        # View
        vm = _sub()
        vm.add_command(label=self._t("mi_zoom_in"),  accelerator="Ctrl+=",
                       command=lambda: self._zoom_editor_font(1))
        vm.add_command(label=self._t("mi_zoom_out"), accelerator="Ctrl+-",
                       command=lambda: self._zoom_editor_font(-1))
        vm.add_command(label=self._t("mi_zoom_rst"), accelerator="Ctrl+0",
                       command=lambda: self._zoom_editor_font(0))
        vm.add_separator()
        vm.add_checkbutton(label=self._t("mi_wrap"), variable=self._word_wrap_var,
                           command=self._toggle_word_wrap)
        vm.add_separator()
        vm.add_command(label=self._t("mi_explorer"), command=self._toggle_explorer)
        vm.add_command(label=self._t("mi_bottom"),   command=self._toggle_bottom_panel)
        self._menubar.add_cascade(label=self._t("menu_view"), menu=vm)

        # Run
        rm = _sub()
        rm.add_command(label=self._t("mi_compile"),   accelerator="Ctrl+Enter",
                       command=lambda: self.compile_now(run=False, trace=False))
        rm.add_command(label=self._t("mi_run_trace"), accelerator="F5",
                       command=lambda: self.compile_now(run=True, trace=True))
        self._menubar.add_cascade(label=self._t("menu_run"), menu=rm)

        # Help
        hm = _sub()
        hm.add_command(label=self._t("mi_shortcuts"), accelerator="F1",
                       command=self._show_shortcuts)
        hm.add_separator()
        hm.add_command(label=self._t("mi_about"), command=self._show_about)
        self._menubar.add_cascade(label=self._t("menu_help"), menu=hm)

    # ── main UI layout ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # toolbar
        self.rowconfigure(1, weight=0)  # find bar
        self.rowconfigure(2, weight=1)  # main pane
        self.rowconfigure(3, weight=0)  # statusbar

        self._build_toolbar()
        self._build_find_bar()

        self.main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.main_pane.grid(row=2, column=0, sticky="nsew")

        self.work_pane = ttk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL)
        self.main_pane.add(self.work_pane, weight=8)

        # Activity Bar (left vertical icon strip)
        self._build_activity_bar()

        # Left sidebar container (Explorer or Source Control)
        self.left_panel = ttk.Frame(self.work_pane, style="Panel.TFrame")
        self.left_panel.rowconfigure(0, weight=1)
        self.left_panel.columnconfigure(0, weight=1)

        # Content container (no header row needed)
        self.left_content = ttk.Frame(self.left_panel, style="Panel.TFrame")
        self.left_content.grid(row=0, column=0, sticky="nsew")
        self.left_content.rowconfigure(0, weight=1)
        self.left_content.columnconfigure(0, weight=1)

        self.work_pane.add(self.left_panel, weight=15)

        # Explorer
        self.explorer_panel = ttk.Frame(self.left_content, style="Panel.TFrame")
        self.explorer_panel.rowconfigure(1, weight=1)
        self.explorer_panel.columnconfigure(0, weight=1)
        self._build_explorer(self.explorer_panel)

        # Source Control (Git)
        self.git_panel = ttk.Frame(self.left_content, style="Panel.TFrame")
        self.git_panel.rowconfigure(1, weight=1)
        self.git_panel.columnconfigure(0, weight=1)
        self._build_git_panel(self.git_panel)

        # Search
        self.search_panel = ttk.Frame(self.left_content, style="Panel.TFrame")
        self.search_panel.rowconfigure(2, weight=1)
        self.search_panel.columnconfigure(0, weight=1)
        self._build_search_panel(self.search_panel)

        # Debug
        self.debug_panel = ttk.Frame(self.left_content, style="Panel.TFrame")
        self.debug_panel.rowconfigure(99, weight=1)
        self.debug_panel.columnconfigure(0, weight=1)
        self._build_debug_panel(self.debug_panel)

        # Editor
        self.editor_panel = ttk.Frame(self.work_pane, style="Root.TFrame")
        self.editor_panel.rowconfigure(1, weight=1)
        self.editor_panel.columnconfigure(0, weight=1)
        self._build_editor_header(self.editor_panel)
        self._build_editor(self.editor_panel)
        self.work_pane.add(self.editor_panel, weight=58)

        # Output
        self.output_panel = ttk.Frame(self.work_pane, style="Root.TFrame")
        self.output_panel.rowconfigure(0, weight=1)
        self.output_panel.columnconfigure(0, weight=1)
        self._build_notebook(self.output_panel)
        self.work_pane.add(self.output_panel, weight=27)

        # Bottom
        self.bottom_panel = ttk.Frame(self.main_pane, style="Panel.TFrame")
        self.bottom_panel.rowconfigure(0, weight=1)
        self.bottom_panel.columnconfigure(0, weight=1)
        self._build_diagnostics(self.bottom_panel)
        self.main_pane.add(self.bottom_panel, weight=2)

        self._build_statusbar()
        self.after(120, self._set_initial_panes)
        self.after(100, self._show_left_panel)

    # ── activity bar (left vertical icon strip) ───────────────────────────────
    def _build_activity_bar(self) -> None:
        # Vertical activity bar on far left
        self.activity_bar = ttk.Frame(self.work_pane, style="Toolbar.TFrame",
                                      width=35)
        self.activity_bar.pack_propagate(False)  # Fixed width
        self.work_pane.add(self.activity_bar, weight=0)

        # Vertical container for icons
        icon_frame = ttk.Frame(self.activity_bar, style="Toolbar.TFrame")
        icon_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Activity bar buttons (vertical)
        self.explorer_icon_btn = tk.Button(
            icon_frame, text="📁", font=("Segoe UI", 14), fg=FG_DIM, bg=PANEL_2,
            relief=tk.FLAT, padx=6, pady=8, activebackground=ACCENT,
            activeforeground="#fff", command=lambda: self._show_left_panel("explorer"))
        self.explorer_icon_btn.pack(side=tk.TOP, pady=0)
        _Tooltip(self.explorer_icon_btn, "Explorer (Ctrl+E)")

        self.search_icon_btn = tk.Button(
            icon_frame, text="🔍", font=("Segoe UI", 14), fg=FG_DIM, bg=PANEL_2,
            relief=tk.FLAT, padx=6, pady=8, activebackground=ACCENT,
            activeforeground="#fff", command=lambda: self._show_left_panel("search"))
        self.search_icon_btn.pack(side=tk.TOP, pady=0)
        _Tooltip(self.search_icon_btn, "Search")

        self.git_icon_btn = tk.Button(
            icon_frame, text="⚡", font=("Segoe UI", 14), fg=FG_DIM, bg=PANEL_2,
            relief=tk.FLAT, padx=6, pady=8, activebackground=ACCENT,
            activeforeground="#fff", command=lambda: self._show_left_panel("source_control"))
        self.git_icon_btn.pack(side=tk.TOP, pady=0)
        _Tooltip(self.git_icon_btn, "Source Control (Ctrl+Shift+G)")

        self.debug_icon_btn = tk.Button(
            icon_frame, text="🐛", font=("Segoe UI", 14), fg=FG_DIM, bg=PANEL_2,
            relief=tk.FLAT, padx=6, pady=8, activebackground=ACCENT,
            activeforeground="#fff", command=lambda: self._show_left_panel("debug"))
        self.debug_icon_btn.pack(side=tk.TOP, pady=0)
        _Tooltip(self.debug_icon_btn, "Run and Debug (F5)")

        # Separator
        sep = ttk.Separator(icon_frame, orient=tk.HORIZONTAL)
        sep.pack(side=tk.TOP, fill=tk.X, pady=6, padx=0)

        self.extensions_icon_btn = tk.Button(
            icon_frame, text="🧩", font=("Segoe UI", 14), fg=FG_DIM, bg=PANEL_2,
            relief=tk.FLAT, padx=6, pady=8, activebackground=ACCENT,
            activeforeground="#fff", command=lambda: None)
        self.extensions_icon_btn.pack(side=tk.TOP, pady=0)
        _Tooltip(self.extensions_icon_btn, "Extensions (Coming soon)")

    def _update_activity_bar_buttons(self, active_mode: str) -> None:
        # Update button appearance based on active mode
        buttons = {
            "explorer": self.explorer_icon_btn,
            "search": self.search_icon_btn,
            "source_control": self.git_icon_btn,
            "debug": self.debug_icon_btn,
        }

        for mode, btn in buttons.items():
            if mode == active_mode:
                btn.config(fg=BLUE, bg=PANEL_3)
            else:
                btn.config(fg=FG_DIM, bg=PANEL_2)

    def _show_left_panel(self, mode: str = None) -> None:
        if mode:
            self._left_panel_mode = mode
        current = self._left_panel_mode

        # Hide all panels
        for p in ("explorer_panel", "git_panel", "search_panel", "debug_panel"):
            panel = getattr(self, p, None)
            if panel is not None:
                try:
                    panel.grid_forget()
                except tk.TclError:
                    pass

        # Show the selected panel
        if current == "explorer":
            self.explorer_panel.grid(row=0, column=0, sticky="nsew")
            self._update_activity_bar_buttons("explorer")
        elif current == "source_control":
            self.git_panel.grid(row=0, column=0, sticky="nsew")
            self._update_activity_bar_buttons("source_control")
            self._refresh_git_status()
        elif current == "search":
            self.search_panel.grid(row=0, column=0, sticky="nsew")
            self._update_activity_bar_buttons("search")
            if hasattr(self, "search_entry"):
                self.search_entry.focus_set()
        elif current == "debug":
            self.debug_panel.grid(row=0, column=0, sticky="nsew")
            self._update_activity_bar_buttons("debug")

    # ── toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=(8, 5))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.configure(style="Toolbar.TFrame")

        def _sep() -> None:
            ttk.Separator(toolbar, orient=tk.VERTICAL).pack(
                side=tk.LEFT, padx=6, pady=3, fill=tk.Y)

        def _btn(key: str, cmd, style: str = "TButton",
                 tip: str = "", padx=(0, 4)) -> ttk.Button:
            b = ttk.Button(toolbar, text=key, style=style, command=cmd)
            b.pack(side=tk.LEFT, padx=padx)
            if tip:
                _Tooltip(b, tip)
            self.toolbar_buttons[key] = b
            return b

        # Primary actions
        _btn("run",     lambda: self.compile_now(run=True, trace=True),
             "Accent.TButton", tip="F5", padx=(0, 2))
        _btn("compile", lambda: self.compile_now(run=False, trace=False),
             tip="Ctrl+Enter", padx=(0, 0))
        _sep()
        _btn("new",         self._new_file,     tip="Ctrl+N")
        _btn("open_file",   self.open_file,     tip="Ctrl+O")
        _btn("open_folder", self.open_folder,   tip="Ctrl+Shift+O", padx=(0, 0))
        _sep()
        _btn("save",    self.save_file,     tip="Ctrl+S")
        _btn("save_as", self.save_file_as)
        _sep()
        _btn("report",    self.export_report)
        _btn("apply_fix", self.apply_first_fix)

        # Mode / Language on right side
        self.static_labels["mode"] = ttk.Label(toolbar, text="Mode",
                                                style="Dim.TLabel")
        self.static_labels["mode"].pack(side=tk.LEFT, padx=(16, 4))
        mode_cb = ttk.Combobox(toolbar, textvariable=self.mode,
                               values=("full", "core"), width=7, state="readonly")
        mode_cb.pack(side=tk.LEFT, padx=(0, 0))

        # Font zoom (+/-)
        _sep()
        zoom_out = ttk.Button(toolbar, text="A−", style="Small.TButton",
                              command=lambda: self._zoom_editor_font(-1), width=3)
        zoom_out.pack(side=tk.LEFT, padx=(0, 2))
        _Tooltip(zoom_out, "Ctrl+−")
        zoom_in  = ttk.Button(toolbar, text="A+", style="Small.TButton",
                              command=lambda: self._zoom_editor_font(1), width=3)
        zoom_in.pack(side=tk.LEFT, padx=(0, 0))
        _Tooltip(zoom_in, "Ctrl+=")

        # Language
        self.static_labels["language"] = ttk.Label(toolbar, text="Lang",
                                                    style="Dim.TLabel")
        self.static_labels["language"].pack(side=tk.LEFT, padx=(14, 4))
        lang_cb = ttk.Combobox(toolbar, textvariable=self.lang,
                               values=("zh", "en"), width=5, state="readonly")
        lang_cb.pack(side=tk.LEFT)
        lang_cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_language())

        # File name on far right
        self.file_label = ttk.Label(toolbar, text="untitled.nx",
                                    style="Dim.TLabel")
        self.file_label.pack(side=tk.RIGHT, padx=(10, 4))

    # ── find / replace bar ────────────────────────────────────────────────────
    def _build_find_bar(self) -> None:
        self.find_bar = ttk.Frame(self, style="FindBar.TFrame", padding=(8, 4))
        # NOT gridded yet — shown on demand

        # Search row
        row1 = ttk.Frame(self.find_bar, style="FindBar.TFrame")
        row1.pack(fill=tk.X)

        self.find_entry = tk.Entry(
            row1, textvariable=self.find_var,
            bg="#3c3c3c", fg=FG, insertbackground=FG,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE,
            font=("Segoe UI", 10), width=28,
        )
        self.find_entry.pack(side=tk.LEFT, padx=(0, 4))

        self.find_result_lbl = ttk.Label(row1, text="", style="Dim.TLabel",
                                         background=FIND_BG, font=("Segoe UI", 9))
        self.find_result_lbl.pack(side=tk.LEFT, padx=(0, 6))

        for key, cmd, tip in (
            ("find_prev", lambda: self._find_next(backwards=True), "↑ 上一个"),
            ("find_next", lambda: self._find_next(backwards=False), "↓ 下一个"),
        ):
            b = ttk.Button(row1, text=self._t(key), style="Find.TButton",
                           command=cmd, width=2)
            b.pack(side=tk.LEFT, padx=(0, 2))
            _Tooltip(b, tip)
        ttk.Checkbutton(row1, text=self._t("case_sensitive"),
                        variable=self.find_case_var, style="Find.TCheckbutton",
                        command=self._on_find_change).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Checkbutton(row1, text=self._t("wrap_search"),
                        variable=self.find_wrap_var, style="Find.TCheckbutton").pack(
            side=tk.LEFT, padx=(0, 6))
        close_btn = ttk.Button(row1, text="✕", style="Find.TButton",
                               command=self._close_find_bar, width=2)
        close_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # Replace row (hidden by default)
        self.replace_row = ttk.Frame(self.find_bar, style="FindBar.TFrame")

        self.replace_entry = tk.Entry(
            self.replace_row, textvariable=self.replace_var,
            bg="#3c3c3c", fg=FG, insertbackground=FG,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE,
            font=("Segoe UI", 10), width=28,
        )
        self.replace_entry.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(self.replace_row, text=self._t("replace_one"),
                   style="Find.TButton",
                   command=self._replace_one).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(self.replace_row, text=self._t("replace_all"),
                   style="Find.TButton",
                   command=self._replace_all).pack(side=tk.LEFT)

        # Bindings
        self.find_var.trace_add("write", lambda *_: self._on_find_change())
        self.find_entry.bind("<Return>",       lambda _e: self._find_next())
        self.find_entry.bind("<Shift-Return>", lambda _e: self._find_next(backwards=True))
        self.find_entry.bind("<Escape>",       lambda _e: self._close_find_bar())
        self.replace_entry.bind("<Return>",    lambda _e: self._replace_one())
        self.replace_entry.bind("<Escape>",    lambda _e: self._close_find_bar())

    def _toggle_find_bar(self, replace: bool = False) -> None:
        if not self._find_visible:
            self._find_visible = True
            self.find_bar.grid(row=1, column=0, sticky="ew")
        if replace and not self._replace_visible:
            self._replace_visible = True
            self.replace_row.pack(fill=tk.X, pady=(4, 0))
        elif not replace and self._replace_visible:
            self._replace_visible = False
            self.replace_row.pack_forget()
        self.find_entry.focus_set()
        self.find_entry.select_range(0, tk.END)

    def _close_find_bar(self) -> None:
        self._find_visible = False
        self._replace_visible = False
        self.find_bar.grid_forget()
        self.replace_row.pack_forget()
        self.editor.tag_remove("find_match", "1.0", tk.END)
        self.find_result_lbl.configure(text="")
        self.editor.focus_set()

    def _on_find_change(self) -> None:
        self._highlight_all_matches()

    def _find_next(self, backwards: bool = False) -> None:
        pattern = self.find_var.get()
        if not pattern:
            return
        nocase = not self.find_case_var.get()
        if backwards:
            pos = self.editor.index(tk.INSERT)
            found = self.editor.search(pattern, pos, stopindex="1.0",
                                       backwards=True, nocase=nocase)
            if not found and self.find_wrap_var.get():
                found = self.editor.search(pattern, tk.END, stopindex="1.0",
                                           backwards=True, nocase=nocase)
        else:
            start = self.editor.index(tk.INSERT + "+1c")
            found = self.editor.search(pattern, start, stopindex=tk.END, nocase=nocase)
            if not found and self.find_wrap_var.get():
                found = self.editor.search(pattern, "1.0", stopindex=tk.END, nocase=nocase)
        if found:
            end = f"{found}+{len(pattern)}c"
            self.editor.tag_remove(tk.SEL, "1.0", tk.END)
            self.editor.tag_add(tk.SEL, found, end)
            self.editor.mark_set(tk.INSERT, found)
            self.editor.see(found)
        self._highlight_all_matches()

    def _highlight_all_matches(self) -> None:
        self.editor.tag_remove("find_match", "1.0", tk.END)
        pattern = self.find_var.get()
        if not pattern:
            self.find_result_lbl.configure(text="", foreground=FG_DIM)
            return
        nocase = not self.find_case_var.get()
        start = "1.0"
        count = 0
        while True:
            pos = self.editor.search(pattern, start, stopindex=tk.END, nocase=nocase)
            if not pos:
                break
            end = f"{pos}+{len(pattern)}c"
            self.editor.tag_add("find_match", pos, end)
            start = end
            count += 1
        if count:
            txt = self._t("find_result").replace("{n}", str(count))
            self.find_result_lbl.configure(text=txt, foreground=GREEN)
        else:
            self.find_result_lbl.configure(text=self._t("find_none"), foreground=RED)

    def _replace_one(self) -> None:
        pattern = self.find_var.get()
        replacement = self.replace_var.get()
        if not pattern:
            return
        nocase = not self.find_case_var.get()
        pos = self.editor.index(tk.INSERT)
        found = self.editor.search(pattern, pos, stopindex=tk.END, nocase=nocase)
        if not found and self.find_wrap_var.get():
            found = self.editor.search(pattern, "1.0", stopindex=tk.END, nocase=nocase)
        if found:
            end = f"{found}+{len(pattern)}c"
            self.editor.delete(found, end)
            self.editor.insert(found, replacement)
            self.editor.mark_set(tk.INSERT, f"{found}+{len(replacement)}c")
        self._highlight_all_matches()

    def _replace_all(self) -> None:
        pattern = self.find_var.get()
        replacement = self.replace_var.get()
        if not pattern:
            return
        nocase = not self.find_case_var.get()
        start = "1.0"
        count = 0
        while True:
            pos = self.editor.search(pattern, start, stopindex=tk.END, nocase=nocase)
            if not pos:
                break
            end = f"{pos}+{len(pattern)}c"
            self.editor.delete(pos, end)
            self.editor.insert(pos, replacement)
            start = f"{pos}+{len(replacement)}c"
            count += 1
        self._highlight_all_matches()
        if count:
            lang = self.lang.get()
            msg = f"已替换 {count} 处" if lang == "zh" else f"Replaced {count} occurrence(s)"
            self._set_status_right(msg)

    # ── pane helpers ──────────────────────────────────────────────────────────
    def _set_initial_panes(self) -> None:
        if self._panes_initialized:
            return
        self.update_idletasks()
        try:
            main_h = max(self.main_pane.winfo_height(), 1)
            work_w = max(self.work_pane.winfo_width(), 1)
            self.main_pane.sashpos(0, max(360, int(main_h * 0.76)))
            # 4 panels: activity_bar | left_panel | editor_panel | output_panel
            # sash 0: after activity_bar (fixed ~35px)
            # sash 1: after left_panel (~18% of remaining)
            # sash 2: after editor_panel (~72% of total → editor gets the most space)
            self.work_pane.sashpos(0, 35)
            self.work_pane.sashpos(1, min(260, max(180, 35 + int(work_w * 0.15))))
            self.work_pane.sashpos(2, max(620, int(work_w * 0.72)))
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

    def _toggle_explorer(self) -> None:
        if self.explorer_visible:
            self._hide_explorer()
        else:
            self._show_explorer()

    def _reset_horizontal_panes(self) -> None:
        self.update_idletasks()
        try:
            work_w = max(self.work_pane.winfo_width(), 1)
            if self.explorer_visible:
                self.work_pane.sashpos(0, 35)
                self.work_pane.sashpos(1, min(260, max(180, 35 + int(work_w * 0.15))))
                self.work_pane.sashpos(2, max(620, int(work_w * 0.72)))
            else:
                self.work_pane.sashpos(0, 35)
                self.work_pane.sashpos(1, max(420, int(work_w * 0.65)))
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
            lbl = (self._t("expand_bottom") if self._bottom_collapsed
                   else self._t("collapse_bottom"))
            self.bottom_toggle.configure(text=lbl)
        except tk.TclError:
            pass

    # ── explorer ──────────────────────────────────────────────────────────────
    def _build_explorer(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=0)  # Open editors
        parent.rowconfigure(1, weight=0)  # File tree header
        parent.rowconfigure(2, weight=1)  # File tree
        parent.columnconfigure(0, weight=1)

        # ── Open Editors Section ──
        self._build_open_editors_section(parent)

        # ── File Tree Section Header ──
        tree_header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        tree_header.grid(row=1, column=0, sticky="ew")
        ttk.Label(tree_header, text="BIANYIYUANLI-MAIN",
                 font=("Segoe UI", 9, "bold"), foreground=FG_DIM,
                 style="Dim.TLabel").pack(anchor=tk.W, side=tk.LEFT)
        ttk.Button(tree_header, text="↻", width=3, style="Small.TButton",
                   command=self._refresh_explorer).pack(side=tk.RIGHT)

        # ── File Tree Container ──
        tree_frame = ttk.Frame(parent, style="Panel.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.file_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                command=self.file_tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=yscroll.set)
        self.file_tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.file_tree.bind("<Double-1>",        self._open_selected_tree_file)
        self.file_tree.bind("<Button-3>",        self._show_tree_context_menu)
        self._refresh_explorer()

    def _build_open_editors_section(self, parent: ttk.Frame) -> None:
        sec_frame = ttk.Frame(parent, style="Panel.TFrame")
        sec_frame.grid(row=0, column=0, sticky="ew")
        sec_frame.columnconfigure(0, weight=1)

        # Header with collapse/expand
        header = ttk.Frame(sec_frame, style="Panel.TFrame", padding=(10, 4))
        header.pack(fill=tk.X)

        self.open_editors_btn = ttk.Button(
            header, text="▼ OPEN EDITORS", style="Small.TButton",
            command=self._toggle_open_editors, width=20)
        self.open_editors_btn.pack(anchor=tk.W)
        self._open_editors_expanded = True

        # Open editors list
        self.open_editors_frame = ttk.Frame(sec_frame, style="Panel.TFrame")
        self.open_editors_frame.pack(fill=tk.X, padx=0, pady=0)
        self.open_editors_frame.columnconfigure(0, weight=1)

        self.open_editors_tree = ttk.Treeview(
            self.open_editors_frame, height=6, columns=(), show="tree")
        self.open_editors_tree.column("#0", width=200)
        self.open_editors_tree.pack(fill=tk.BOTH, expand=True)
        self.open_editors_tree.bind("<Double-1>", self._on_open_editor_click)
        self.open_editors_tree.bind("<Button-3>", self._on_open_editor_context)

    def _toggle_open_editors(self) -> None:
        self._open_editors_expanded = not self._open_editors_expanded
        if self._open_editors_expanded:
            self.open_editors_btn.configure(text="▼ OPEN EDITORS")
            self.open_editors_frame.pack(fill=tk.X, padx=0, pady=0)
        else:
            self.open_editors_btn.configure(text="▶ OPEN EDITORS")
            self.open_editors_frame.pack_forget()

    def _refresh_open_editors(self) -> None:
        if not hasattr(self, "open_editors_tree"):
            return
        self.open_editors_tree.delete(*self.open_editors_tree.get_children())
        if self.current_file:
            icon = self._file_icon(self.current_file)
            filename = self.current_file.name
            self.open_editors_tree.insert("", tk.END, text=f"{icon}{filename}")

    def _on_open_editor_click(self, _event=None) -> None:
        selected = self.open_editors_tree.focus()
        if selected and self.current_file:
            self._load_file(self.current_file)

    def _on_open_editor_context(self, event) -> None:
        item = self.open_editors_tree.identify("item", event.x, event.y)
        if not item:
            return
        menu = tk.Menu(self, tearoff=False, bg=PANEL_2, fg=FG,
                      activebackground="#094771")
        menu.add_command(label="Close", command=lambda: None)
        menu.add_command(label="Close All", command=lambda: None)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _refresh_explorer(self) -> None:
        if not hasattr(self, "file_tree"):
            return
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_tree_nodes.clear()
        root = self.workspace_root.resolve()
        root_id = self.file_tree.insert("", tk.END,
                                        text=f"▾ {root.name}", open=True,
                                        tags=("folder_root",))
        self.file_tree_nodes[root_id] = root
        self.file_tree.tag_configure("folder_root", foreground=BLUE)
        self.file_tree.tag_configure("modified_file", foreground=YELLOW)
        self._populate_tree_node(root_id, root)

    def _populate_tree_node(self, parent_id: str, path: Path) -> None:
        self.file_tree.delete(*self.file_tree.get_children(parent_id))
        try:
            children = sorted(path.iterdir(),
                               key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            if self._hide_from_explorer(child):
                continue

            if child.is_dir():
                icon = "▸ 📁 "
                tag = "folder"
            else:
                icon = self._file_icon(child) + " "
                tag = "file"

            text = icon + child.name
            node = self.file_tree.insert(parent_id, tk.END, text=text, open=False,
                                        tags=(tag,))
            self.file_tree_nodes[node] = child

            # Configure tag colors
            if not hasattr(self, "_tree_tags_configured"):
                self.file_tree.tag_configure("folder", foreground=BLUE)
                self.file_tree.tag_configure("file", foreground=FG)
                self._tree_tags_configured = True

            if child.is_dir():
                self.file_tree.insert(node, tk.END, text="")

    def _hide_from_explorer(self, path: Path) -> bool:
        hidden = {"__pycache__", ".pytest_cache", ".pytest-tmp", ".git",
                  "nexa.egg-info"}
        if path.name in hidden or path.name.endswith(".egg-info"):
            return True
        if path.name.startswith("pytest-cache-files-"):
            return True
        return False

    def _file_icon(self, path: Path) -> str:
        suffix = path.suffix.lower()
        # Source code files
        if suffix == ".nx":  return "◆"
        if suffix == ".py":  return "🐍"
        if suffix in {".js", ".ts", ".jsx", ".tsx"}:  return "📜"
        if suffix in {".java", ".c", ".cpp", ".h"}:  return "⚙"
        # Config files
        if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}:  return "⚙"
        if suffix in {".xml", ".html", ".htm"}:  return "🔗"
        # Data files
        if suffix in {".csv", ".xlsx", ".xls"}:  return "📊"
        if suffix in {".sql", ".db"}:  return "🗄"
        # Text files
        if suffix in {".md", ".markdown", ".rst"}:  return "📝"
        if suffix in {".txt", ".log"}:  return "📄"
        # Executables
        if suffix in {".exe", ".sh", ".bat", ".cmd"}:  return "⚡"
        # Archives
        if suffix in {".zip", ".tar", ".gz", ".7z", ".rar"}:  return "📦"
        # Images
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}:  return "🖼"
        # Other
        return "•"

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

    def _show_tree_context_menu(self, event) -> None:
        item = self.file_tree.identify("item", event.x, event.y)
        if not item:
            return

        self.file_tree.focus(item)
        self.file_tree.selection_set(item)
        path = self.file_tree_nodes.get(item)
        if not path:
            return

        menu = tk.Menu(self, tearoff=False, bg=PANEL_2, fg=FG,
                      activebackground="#094771", activeforeground="#ffffff")

        if path.is_file():
            menu.add_command(label="Open", command=lambda: self._load_file(path))
            menu.add_separator()

        menu.add_command(label="Reveal in Explorer", command=lambda: None)
        menu.add_separator()

        if path.is_file():
            menu.add_command(label="Copy", command=lambda: self._copy_path(path))
            menu.add_command(label="Copy Relative Path",
                           command=lambda: self._copy_path(path, relative=True))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._delete_file(path))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_path(self, path: Path, relative: bool = False) -> None:
        if relative:
            try:
                text = str(path.relative_to(self.workspace_root))
            except ValueError:
                text = str(path)
        else:
            text = str(path.resolve())
        self.clipboard_clear()
        self.clipboard_append(text)

    def _delete_file(self, path: Path) -> None:
        if messagebox.askyesno("Delete", f"Delete {path.name}?"):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                self._refresh_explorer()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    # ── source control (git) ──────────────────────────────────────────────────
    def _build_git_panel(self, parent: ttk.Frame) -> None:
        # Header with refresh button
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["source_control"] = ttk.Label(
            header, text=self._t("source_control"), font=("Segoe UI", 10, "bold"))
        self.static_labels["source_control"].pack(side=tk.LEFT)
        ttk.Button(header, text="↻", width=3, style="Small.TButton",
                   command=self._refresh_git_status).pack(side=tk.RIGHT)

        # Main scrollable area
        main_frame = ttk.Frame(parent, style="Panel.TFrame")
        main_frame.grid(row=1, column=0, sticky="nsew")
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(main_frame, bg=PANEL, highlightthickness=0, relief=tk.FLAT)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        self.git_content = ttk.Frame(canvas, style="Panel.TFrame")
        canvas.create_window((0, 0), window=self.git_content, anchor="nw")

        def _on_frame_configure(event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        self.git_content.bind("<Configure>", _on_frame_configure)

        # Branch info section
        self._build_git_branch_section(self.git_content)

        # Changes section
        self._build_git_changes_section(self.git_content)

        # Commit message section
        self._build_git_commit_section(self.git_content)

        # Commit graph section
        self._build_git_graph(self.git_content)

    def _build_git_branch_section(self, parent: ttk.Frame) -> None:
        sec = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 6))
        sec.pack(fill=tk.X, padx=0, pady=0)

        # Current branch
        lbl = ttk.Label(sec, text=self._t("git_branch"), font=("Segoe UI", 9, "bold"),
                       foreground=FG_DIM, style="Dim.TLabel")
        lbl.pack(anchor=tk.W, pady=(0, 4))

        branch_frame = ttk.Frame(sec, style="Panel.TFrame")
        branch_frame.pack(anchor=tk.W, pady=(0, 8), fill=tk.X)

        self.git_branch_label = ttk.Label(
            branch_frame, text="Loading…", foreground=BLUE, style="TLabel",
            font=("Segoe UI", 11, "bold"))
        self.git_branch_label.pack(side=tk.LEFT)

        self.git_status_label = ttk.Label(
            branch_frame, text="", foreground=FG_DIM, style="Dim.TLabel",
            font=("Segoe UI", 8))
        self.git_status_label.pack(side=tk.RIGHT)

        # Branch buttons
        btn_frame = ttk.Frame(sec, style="Panel.TFrame")
        btn_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_frame, text="⬇ Pull", style="Small.TButton",
                   command=self._git_pull).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⬆ Push", style="Small.TButton",
                   command=self._git_push).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="⟳ Sync", style="Small.TButton",
                   command=self._git_sync).pack(side=tk.LEFT, padx=2)

    def _build_git_changes_section(self, parent: ttk.Frame) -> None:
        sec = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 6))
        sec.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        lbl = ttk.Label(sec, text=self._t("git_changes"), font=("Segoe UI", 9, "bold"),
                       foreground=FG_DIM, style="Dim.TLabel")
        lbl.pack(anchor=tk.W, pady=(0, 4))

        # Tree container frame (for grid geometry)
        tree_frame = ttk.Frame(sec, style="Panel.TFrame")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Changes tree
        self.git_tree = ttk.Treeview(tree_frame, height=8, columns=("status",),
                                     show="tree headings")
        self.git_tree.heading("#0", text="File")
        self.git_tree.heading("status", text="")
        self.git_tree.column("#0", width=180)
        self.git_tree.column("status", width=60)
        self.git_tree.tag_configure("modified", foreground=YELLOW)
        self.git_tree.tag_configure("added", foreground=GREEN)
        self.git_tree.tag_configure("deleted", foreground=RED)
        self.git_tree.tag_configure("renamed", foreground=PURPLE)

        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.git_tree.yview)
        self.git_tree.configure(yscrollcommand=yscroll.set)

        self.git_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

    def _build_git_commit_section(self, parent: ttk.Frame) -> None:
        sec = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 6))
        sec.pack(fill=tk.X, padx=0, pady=0)

        lbl = ttk.Label(sec, text=self._t("git_commit"), font=("Segoe UI", 9, "bold"),
                       foreground=FG_DIM, style="Dim.TLabel")
        lbl.pack(anchor=tk.W, pady=(0, 4))

        # Commit message input
        self.git_msg_text = tk.Text(
            sec, height=4, wrap=tk.WORD, font=("Segoe UI", 9),
            bg="#2d2d30", fg=FG, insertbackground=FG,
            relief=tk.FLAT, padx=6, pady=4)
        self.git_msg_text.pack(fill=tk.X, pady=(0, 6))
        self.git_msg_text.insert("1.0", self._t("git_commit_msg"))

        # Commit button
        ttk.Button(sec, text="✓ Commit", style="Accent.TButton",
                   command=self._git_commit).pack(fill=tk.X)

    def _refresh_git_status(self) -> None:
        try:
            if not hasattr(self, "git_branch_label"):
                return

            self._detect_git_repo()
            if not self.git_repo_root:
                self.git_branch_label.configure(
                    text=self._t("git_no_repo"), foreground=RED)
                if hasattr(self, "git_tree"):
                    self.git_tree.delete(*self.git_tree.get_children())
                # Show init UI
                if hasattr(self, "git_content"):
                    self._show_git_init_ui()
                return

            # Get current branch
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                branch = result.stdout.strip()
                self.git_branch = branch
                self.git_branch_label.configure(text=branch, foreground=BLUE)
            else:
                self.git_branch_label.configure(
                    text=self._t("git_no_repo"), foreground=RED)
                if hasattr(self, "git_content"):
                    self._show_git_init_ui()
                return

            # Get commits ahead/behind
            self._update_commits_info()

            # Get file status
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "status", "--porcelain"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                self._render_git_changes(result.stdout)

            # Refresh commit graph
            self._refresh_git_graph()

        except FileNotFoundError:
            if hasattr(self, "git_branch_label"):
                self.git_branch_label.configure(
                    text="Git not found", foreground=RED)
        except Exception as e:
            if hasattr(self, "git_branch_label"):
                self.git_branch_label.configure(
                    text=f"Error: {str(e)[:30]}", foreground=RED)

    def _detect_git_repo(self) -> None:
        current = self.workspace_root
        for _ in range(10):
            if (current / ".git").exists():
                self.git_repo_root = current
                return
            current = current.parent
        self.git_repo_root = None

    def _update_commits_info(self) -> None:
        if not self.git_repo_root:
            return
        try:
            # Get ahead/behind count
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "rev-list", "--left-right", "--count",
                 "HEAD...@{u}"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0:
                ahead, behind = result.stdout.strip().split()
                ahead, behind = int(ahead), int(behind)
                if ahead > 0 or behind > 0:
                    status = ""
                    if ahead > 0:
                        status += f"↑{ahead} "
                    if behind > 0:
                        status += f"↓{behind}"
                    if hasattr(self, "git_status_label"):
                        self.git_status_label.configure(text=status.strip())
                else:
                    if hasattr(self, "git_status_label"):
                        self.git_status_label.configure(text="")
        except Exception:
            pass

    def _render_git_changes(self, output: str) -> None:
        self.git_tree.delete(*self.git_tree.get_children())
        for line in output.strip().split("\n"):
            if not line:
                continue
            status_code = line[:2]
            path = line[3:]
            status_text = ""
            tag = ""

            if status_code[0] == "M":
                status_text = "Modified"
                tag = "modified"
            elif status_code[0] == "A":
                status_text = "Added"
                tag = "added"
            elif status_code[0] == "D":
                status_text = "Deleted"
                tag = "deleted"
            elif status_code[0] == "R":
                status_text = "Renamed"
                tag = "renamed"
            elif status_code[0] == "?":
                status_text = "Untracked"
                tag = "added"

            filename = Path(path).name
            self.git_tree.insert("", tk.END, text=filename, values=(status_text,), tag=tag)

    def _git_commit(self) -> None:
        if not self.git_repo_root:
            messagebox.showerror("Error", self._t("git_no_repo"))
            return

        msg = self.git_msg_text.get("1.0", tk.END).strip()
        if not msg or msg == self._t("git_commit_msg"):
            messagebox.showwarning("Warning", "Please enter a commit message")
            return

        try:
            # Stage all changes
            subprocess.run(
                ["git", "-C", str(self.git_repo_root), "add", "-A"],
                capture_output=True, timeout=5, check=False)

            # Commit
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "commit", "-m", msg],
                capture_output=True, text=True, timeout=5, check=False)

            if result.returncode == 0:
                self.git_msg_text.delete("1.0", tk.END)
                self.git_msg_text.insert("1.0", self._t("git_commit_msg"))
                self._refresh_git_status()
                messagebox.showinfo("Success", "Commit successful")
            else:
                error = result.stderr if result.stderr else "Commit failed"
                messagebox.showerror("Error", error)
        except Exception as e:
            messagebox.showerror("Error", f"Commit failed: {str(e)}")

    def _git_push(self) -> None:
        if not self.git_repo_root:
            messagebox.showerror("Error", self._t("git_no_repo"))
            return

        try:
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "push"],
                capture_output=True, text=True, timeout=15, check=False)
            self._refresh_git_status()
            if result.returncode == 0:
                messagebox.showinfo("Success", "Push successful")
            else:
                error = result.stderr if result.stderr else "Push failed"
                messagebox.showerror("Error", error)
        except Exception as e:
            messagebox.showerror("Error", f"Push failed: {str(e)}")

    def _git_pull(self) -> None:
        if not self.git_repo_root:
            messagebox.showerror("Error", self._t("git_no_repo"))
            return

        try:
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "pull"],
                capture_output=True, text=True, timeout=15, check=False)
            self._refresh_git_status()
            if result.returncode == 0:
                messagebox.showinfo("Success", "Pull successful")
            else:
                messagebox.showerror("Error", result.stderr or "Pull failed")
        except Exception as e:
            messagebox.showerror("Error", f"Pull failed: {str(e)}")

    def _git_sync(self) -> None:
        if not self.git_repo_root:
            messagebox.showerror("Error", self._t("git_no_repo"))
            return

        try:
            # Pull first
            subprocess.run(
                ["git", "-C", str(self.git_repo_root), "pull"],
                capture_output=True, timeout=15, check=False)
            # Then push
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "push"],
                capture_output=True, text=True, timeout=15, check=False)
            self._refresh_git_status()
            if result.returncode == 0:
                messagebox.showinfo("Success", "Sync successful")
            else:
                messagebox.showerror("Error", result.stderr or "Sync failed")
        except Exception as e:
            messagebox.showerror("Error", f"Sync failed: {str(e)}")

    def _show_git_init_ui(self) -> None:
        # Clear existing content
        for child in self.git_content.winfo_children():
            child.destroy()

        # Show initialization message and button
        frame = ttk.Frame(self.git_content, style="Panel.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=40)

        ttk.Label(frame, text=self._t("git_no_repo"),
                 font=("Segoe UI", 11), foreground=FG_DIM,
                 style="Dim.TLabel").pack(pady=(0, 20))

        ttk.Button(frame, text="🔧 " + self._t("git_init"),
                  style="Accent.TButton",
                  command=self._git_init_repo).pack(fill=tk.X, pady=10)

    def _git_init_repo(self) -> None:
        try:
            result = subprocess.run(
                ["git", "init"],
                cwd=str(self.workspace_root),
                capture_output=True, text=True, timeout=5, check=False)

            if result.returncode == 0:
                self.git_repo_root = self.workspace_root
                self._refresh_git_status()
                messagebox.showinfo("Success", "Repository initialized")
            else:
                messagebox.showerror("Error", result.stderr or "Init failed")
        except Exception as e:
            messagebox.showerror("Error", f"Init failed: {str(e)}")

    # ── search panel ──────────────────────────────────────────────────────────
    def _build_search_panel(self, parent: ttk.Frame) -> None:
        # Header
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="SEARCH", font=("Segoe UI", 10, "bold"),
                 foreground=FG_DIM, style="Dim.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="⟲", width=3, style="Small.TButton",
                   command=self._search_clear).pack(side=tk.RIGHT)

        # Input area
        input_frame = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 4))
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            input_frame, textvariable=self.search_var,
            bg="#3c3c3c", fg=FG, insertbackground=FG,
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BLUE,
            font=("Segoe UI", 10))
        self.search_entry.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.search_entry.bind("<Return>", lambda _e: self._search_workspace())

        # Options
        opt = ttk.Frame(input_frame, style="Panel.TFrame")
        opt.grid(row=1, column=0, sticky="ew")
        self.search_case_var = tk.BooleanVar(value=False)
        self.search_regex_var = tk.BooleanVar(value=False)
        self.search_word_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="Aa", variable=self.search_case_var,
                      bg=PANEL, fg=FG_DIM, selectcolor=PANEL_3,
                      activebackground=PANEL, activeforeground=BLUE,
                      relief=tk.FLAT, borderwidth=0,
                      font=("Segoe UI", 8)).pack(side=tk.LEFT)
        tk.Checkbutton(opt, text="ʫw", variable=self.search_word_var,
                      bg=PANEL, fg=FG_DIM, selectcolor=PANEL_3,
                      activebackground=PANEL, activeforeground=BLUE,
                      relief=tk.FLAT, borderwidth=0,
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(2, 0))
        tk.Checkbutton(opt, text=".*", variable=self.search_regex_var,
                      bg=PANEL, fg=FG_DIM, selectcolor=PANEL_3,
                      activebackground=PANEL, activeforeground=BLUE,
                      relief=tk.FLAT, borderwidth=0,
                      font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(2, 0))
        ttk.Button(opt, text="Search", style="Small.TButton",
                  command=self._search_workspace).pack(side=tk.RIGHT)

        # Results
        result_frame = ttk.Frame(parent, style="Panel.TFrame")
        result_frame.grid(row=2, column=0, sticky="nsew")
        result_frame.rowconfigure(1, weight=1)
        result_frame.columnconfigure(0, weight=1)

        self.search_result_summary = ttk.Label(
            result_frame, text="", style="Dim.TLabel",
            font=("Segoe UI", 9), padding=(10, 4))
        self.search_result_summary.grid(row=0, column=0, sticky="ew")

        tree_container = ttk.Frame(result_frame, style="Panel.TFrame")
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        self.search_tree = ttk.Treeview(tree_container, show="tree",
                                        selectmode="browse")
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL,
                                command=self.search_tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.search_tree.configure(yscrollcommand=yscroll.set)
        self.search_tree.tag_configure("file_hdr", foreground=BLUE,
                                       font=("Segoe UI", 9, "bold"))
        self.search_tree.tag_configure("match", foreground=FG)
        self.search_tree.bind("<Double-1>", self._search_jump_to_match)

        # Track matches: item_id -> (path, line, col)
        self._search_matches: dict[str, tuple[Path, int, int]] = {}

    def _search_clear(self) -> None:
        self.search_var.set("")
        self.search_tree.delete(*self.search_tree.get_children())
        self.search_result_summary.configure(text="")
        self._search_matches.clear()

    def _search_workspace(self) -> None:
        query = self.search_var.get().strip()
        self.search_tree.delete(*self.search_tree.get_children())
        self._search_matches.clear()
        if not query:
            self.search_result_summary.configure(text="")
            return

        case_sensitive = self.search_case_var.get()
        use_regex = self.search_regex_var.get()
        word_only = self.search_word_var.get()

        try:
            if use_regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                if word_only:
                    pattern = re.compile(r"\b" + query + r"\b", flags)
                else:
                    pattern = re.compile(query, flags)
            else:
                escaped = re.escape(query)
                flags = 0 if case_sensitive else re.IGNORECASE
                if word_only:
                    pattern = re.compile(r"\b" + escaped + r"\b", flags)
                else:
                    pattern = re.compile(escaped, flags)
        except re.error as e:
            self.search_result_summary.configure(text=f"Regex error: {e}",
                                                 foreground=RED)
            return

        total_matches = 0
        total_files = 0
        for path in self._iter_searchable_files(self.workspace_root):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            file_matches = []
            for line_no, line in enumerate(text.splitlines(), 1):
                for m in pattern.finditer(line):
                    file_matches.append((line_no, m.start(), line))
                    if len(file_matches) > 50:
                        break
                if len(file_matches) > 50:
                    break
            if not file_matches:
                continue
            total_files += 1
            total_matches += len(file_matches)
            try:
                rel = path.relative_to(self.workspace_root)
            except ValueError:
                rel = path
            file_id = self.search_tree.insert(
                "", tk.END, text=f"▾ {rel}  ({len(file_matches)})",
                open=True, tags=("file_hdr",))
            for line_no, col, line in file_matches[:50]:
                snippet = line.strip()
                if len(snippet) > 80:
                    snippet = snippet[:77] + "..."
                mid = self.search_tree.insert(
                    file_id, tk.END,
                    text=f"  {line_no}: {snippet}", tags=("match",))
                self._search_matches[mid] = (path, line_no, col)
            if total_matches > 500:
                self.search_tree.insert("", tk.END,
                                        text="  (too many matches, truncated)")
                break

        self.search_result_summary.configure(
            text=f"{total_matches} results in {total_files} files",
            foreground=FG_DIM)

    def _iter_searchable_files(self, root: Path):
        skip_dirs = {"__pycache__", ".git", ".pytest_cache", ".pytest-tmp",
                    "node_modules", "nexa.egg-info", "out", ".venv", "venv"}
        skip_suffix = {".pyc", ".pyo", ".dll", ".so", ".exe", ".png", ".jpg",
                       ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz",
                       ".7z", ".bin", ".dot"}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix.lower() in skip_suffix:
                continue
            if path.stat().st_size > 1_000_000:
                continue
            yield path

    def _search_jump_to_match(self, _event=None) -> None:
        item = self.search_tree.focus()
        info = self._search_matches.get(item)
        if not info:
            return
        path, line, col = info
        if path != self.current_file:
            self._load_file(path)
        index = f"{line}.{col}"
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self.editor.see(index)
        self.editor.tag_remove("find_match", "1.0", tk.END)
        self.editor.tag_add("find_match", index,
                           f"{line}.{col}+{len(self.search_var.get())}c")

    # ── debug panel ───────────────────────────────────────────────────────────
    def _build_debug_panel(self, parent: ttk.Frame) -> None:
        # Header
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="RUN AND DEBUG", font=("Segoe UI", 10, "bold"),
                 foreground=FG_DIM, style="Dim.TLabel").pack(side=tk.LEFT)

        # Run controls
        run_frame = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 4))
        run_frame.grid(row=1, column=0, sticky="ew")

        ttk.Button(run_frame, text="▶ Start Debugging",
                  style="Accent.TButton",
                  command=lambda: self.compile_now(run=True, trace=True)).pack(
            fill=tk.X, pady=(2, 4))

        # Step controls
        step_frame = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 2))
        step_frame.grid(row=2, column=0, sticky="ew")
        for txt, tip, cmd in (
            ("⏵", "Continue", self._debug_continue),
            ("⏸", "Pause", self._debug_pause),
            ("⏹", "Stop", self._debug_stop),
            ("⤵", "Step Over", self._debug_step_over),
            ("⤷", "Step Into", self._debug_step_into),
            ("⤴", "Step Out", self._debug_step_out),
        ):
            b = tk.Button(step_frame, text=txt, font=("Segoe UI", 12),
                         fg=FG, bg=PANEL_2, relief=tk.FLAT,
                         padx=8, pady=2, command=cmd,
                         activebackground=ACCENT, activeforeground="#fff")
            b.pack(side=tk.LEFT, padx=2)
            _Tooltip(b, tip)

        # Variables section
        var_frame = ttk.Frame(parent, style="Panel.TFrame")
        var_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        var_frame.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        var_hdr = ttk.Frame(var_frame, style="Panel.TFrame", padding=(10, 4))
        var_hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(var_hdr, text="▾ VARIABLES",
                 font=("Segoe UI", 9, "bold"),
                 foreground=FG_DIM, style="Dim.TLabel").pack(side=tk.LEFT)

        self.debug_vars_tree = ttk.Treeview(
            var_frame, columns=("value",), show="tree headings", height=6)
        self.debug_vars_tree.heading("#0", text="Name")
        self.debug_vars_tree.heading("value", text="Value")
        self.debug_vars_tree.column("#0", width=120)
        self.debug_vars_tree.column("value", width=120)
        self.debug_vars_tree.grid(row=1, column=0, sticky="nsew",
                                  padx=(10, 0))
        var_frame.rowconfigure(1, weight=1)

        # Call stack section
        stack_frame = ttk.Frame(parent, style="Panel.TFrame")
        stack_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 0))
        stack_frame.columnconfigure(0, weight=1)
        parent.rowconfigure(4, weight=1)

        stack_hdr = ttk.Frame(stack_frame, style="Panel.TFrame", padding=(10, 4))
        stack_hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(stack_hdr, text="▾ CALL STACK",
                 font=("Segoe UI", 9, "bold"),
                 foreground=FG_DIM, style="Dim.TLabel").pack(side=tk.LEFT)

        self.debug_stack_list = tk.Listbox(
            stack_frame, bg=BG, fg=FG, relief=tk.FLAT,
            highlightthickness=0, selectbackground=SEL_BG,
            font=("Consolas", 10), height=5)
        self.debug_stack_list.grid(row=1, column=0, sticky="nsew",
                                   padx=(10, 0))
        stack_frame.rowconfigure(1, weight=1)

        # Breakpoints section
        bp_frame = ttk.Frame(parent, style="Panel.TFrame")
        bp_frame.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        bp_frame.columnconfigure(0, weight=1)

        bp_hdr = ttk.Frame(bp_frame, style="Panel.TFrame", padding=(10, 4))
        bp_hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(bp_hdr, text="▾ BREAKPOINTS",
                 font=("Segoe UI", 9, "bold"),
                 foreground=FG_DIM, style="Dim.TLabel").pack(side=tk.LEFT)
        ttk.Button(bp_hdr, text="🗑", style="Small.TButton", width=3,
                  command=self._debug_clear_breakpoints).pack(side=tk.RIGHT)

        self.debug_bp_list = tk.Listbox(
            bp_frame, bg=BG, fg=FG, relief=tk.FLAT,
            highlightthickness=0, selectbackground=SEL_BG,
            font=("Consolas", 10), height=4)
        self.debug_bp_list.grid(row=1, column=0, sticky="nsew",
                                padx=(10, 0))
        self.debug_bp_list.bind("<Double-1>", self._debug_jump_to_breakpoint)

        self._breakpoints: set[tuple[Path, int]] = set()
        self._refresh_debug_view()

    def _debug_log(self, msg: str) -> None:
        if hasattr(self, "bottom_text_views"):
            tv = self.bottom_text_views.get("Trace")
            if tv:
                tv.configure(state=tk.NORMAL)
                tv.insert(tk.END, msg + "\n")
                tv.see(tk.END)
                tv.configure(state=tk.DISABLED)

    def _debug_continue(self) -> None:
        self._debug_log("[debug] Continue → re-running with trace")
        self.compile_now(run=True, trace=True)
        self._refresh_debug_view()

    def _debug_pause(self) -> None:
        self._debug_log("[debug] Pause requested (interpreter is synchronous)")

    def _debug_stop(self) -> None:
        self._debug_log("[debug] Stop")
        if hasattr(self, "debug_vars_tree"):
            self.debug_vars_tree.delete(*self.debug_vars_tree.get_children())
        if hasattr(self, "debug_stack_list"):
            self.debug_stack_list.delete(0, tk.END)

    def _debug_step_over(self) -> None:
        self._debug_log("[debug] Step Over (single-step not yet wired)")

    def _debug_step_into(self) -> None:
        self._debug_log("[debug] Step Into (single-step not yet wired)")

    def _debug_step_out(self) -> None:
        self._debug_log("[debug] Step Out (single-step not yet wired)")

    def _refresh_debug_view(self) -> None:
        # Populate variables from last result symbols
        if not hasattr(self, "debug_vars_tree"):
            return
        self.debug_vars_tree.delete(*self.debug_vars_tree.get_children())
        self.debug_stack_list.delete(0, tk.END)
        self.debug_bp_list.delete(0, tk.END)

        result = self.last_result
        if result is not None:
            for sym in getattr(result, "symbols", []) or []:
                try:
                    name = getattr(sym, "name", str(sym))
                    typ = getattr(sym, "type", "") or ""
                    cat = getattr(sym, "category", "") or ""
                    self.debug_vars_tree.insert(
                        "", tk.END, text=str(name),
                        values=(f"{cat}: {typ}",))
                except Exception:
                    pass

            # Call stack from trace
            trace = getattr(result, "trace", None)
            if trace:
                for entry in (trace[-10:] if isinstance(trace, list) else []):
                    self.debug_stack_list.insert(tk.END, str(entry))

        # Breakpoints
        for path, line in sorted(self._breakpoints):
            try:
                rel = path.relative_to(self.workspace_root)
            except ValueError:
                rel = path
            self.debug_bp_list.insert(tk.END, f"{rel}:{line}")

    def _toggle_breakpoint_at_cursor(self) -> None:
        if not self.current_file:
            return
        line_no = int(self.editor.index(tk.INSERT).split(".")[0])
        key = (self.current_file, line_no)
        if key in self._breakpoints:
            self._breakpoints.remove(key)
            self._debug_log(f"[bp] removed at {self.current_file.name}:{line_no}")
        else:
            self._breakpoints.add(key)
            self._debug_log(f"[bp] added at {self.current_file.name}:{line_no}")
        self._refresh_debug_view()
        self._highlight_breakpoint_gutter()

    def _highlight_breakpoint_gutter(self) -> None:
        if not hasattr(self, "line_numbers"):
            return
        self.line_numbers.tag_remove("bp", "1.0", tk.END)
        self.line_numbers.tag_configure("bp", foreground=RED,
                                        background="#3d1f1f")
        if not self.current_file:
            return
        for path, line in self._breakpoints:
            if path == self.current_file:
                self.line_numbers.tag_add("bp", f"{line}.0", f"{line}.end")

    def _debug_clear_breakpoints(self) -> None:
        self._breakpoints.clear()
        self._refresh_debug_view()
        self._highlight_breakpoint_gutter()

    def _debug_jump_to_breakpoint(self, _event=None) -> None:
        sel = self.debug_bp_list.curselection()
        if not sel:
            return
        text = self.debug_bp_list.get(sel[0])
        if ":" not in text:
            return
        rel, line = text.rsplit(":", 1)
        try:
            path = (self.workspace_root / rel).resolve()
            line_no = int(line)
        except (ValueError, OSError):
            return
        if path != self.current_file and path.exists():
            self._load_file(path)
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, f"{line_no}.0")
        self.editor.see(f"{line_no}.0")

    # ── git commit graph ──────────────────────────────────────────────────────
    def _build_git_graph(self, parent: ttk.Frame) -> None:
        # Container with scrollable canvas
        graph_frame = ttk.Frame(parent, style="Panel.TFrame")
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=(8, 0))
        graph_frame.rowconfigure(1, weight=1)
        graph_frame.columnconfigure(0, weight=1)

        lbl = ttk.Label(graph_frame, text="▾ COMMIT GRAPH",
                       font=("Segoe UI", 9, "bold"),
                       foreground=FG_DIM, style="Dim.TLabel",
                       padding=(8, 4))
        lbl.grid(row=0, column=0, sticky="ew")

        canvas_container = ttk.Frame(graph_frame, style="Panel.TFrame")
        canvas_container.grid(row=1, column=0, sticky="nsew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.git_graph_canvas = tk.Canvas(
            canvas_container, bg=BG, highlightthickness=0, height=300)
        self.git_graph_canvas.grid(row=0, column=0, sticky="nsew")
        gscroll = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL,
                               command=self.git_graph_canvas.yview)
        gscroll.grid(row=0, column=1, sticky="ns")
        self.git_graph_canvas.configure(yscrollcommand=gscroll.set)
        self.git_graph_canvas.bind("<MouseWheel>",
            lambda e: self.git_graph_canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))

    def _refresh_git_graph(self) -> None:
        if not hasattr(self, "git_graph_canvas") or not self.git_repo_root:
            return
        canvas = self.git_graph_canvas
        canvas.delete("all")

        try:
            # Get commit history with graph info
            result = subprocess.run(
                ["git", "-C", str(self.git_repo_root), "log",
                 "--all", "--pretty=format:%h\x1f%s\x1f%an\x1f%P\x1f%d",
                 "-30"],
                capture_output=True, text=True, timeout=5, check=False)
            if result.returncode != 0:
                return

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\x1f")
                if len(parts) < 4:
                    continue
                sha, msg, author, parents = parts[0], parts[1], parts[2], parts[3]
                refs = parts[4] if len(parts) > 4 else ""
                commits.append({
                    "sha": sha, "msg": msg, "author": author,
                    "parents": parents.split() if parents else [],
                    "refs": refs.strip()
                })

            if not commits:
                canvas.create_text(20, 20, anchor="nw", text="No commits",
                                  fill=FG_DIM, font=("Segoe UI", 9))
                return

            # Assign columns (simple lane assignment)
            sha_to_idx = {c["sha"]: i for i, c in enumerate(commits)}
            lanes: dict[int, int] = {}  # commit idx -> lane
            active_lanes: dict[int, str] = {}  # lane -> expected next sha

            def find_free_lane() -> int:
                for i in range(20):
                    if i not in active_lanes:
                        return i
                return len(active_lanes)

            for i, commit in enumerate(commits):
                sha = commit["sha"]
                # Find existing lane reserved for this commit
                lane = None
                for ln, expected in list(active_lanes.items()):
                    if expected == sha:
                        lane = ln
                        del active_lanes[ln]
                        break
                if lane is None:
                    lane = find_free_lane()
                lanes[i] = lane
                # Reserve lane for first parent
                if commit["parents"]:
                    active_lanes[lane] = commit["parents"][0]

            # Draw
            row_h = 28
            col_w = 18
            x_offset = 12
            text_x = x_offset + (max(lanes.values()) + 1) * col_w + 12

            colors = ["#4db8ff", "#52d97f", "#dcdcaa", "#ff9966", "#d99dff",
                     "#ff5555", "#86d4ff", "#b5cea8"]

            # Draw lines first (parent → child)
            for i, commit in enumerate(commits):
                lane_i = lanes[i]
                y_i = 16 + i * row_h
                for parent_sha in commit["parents"]:
                    if parent_sha in sha_to_idx:
                        j = sha_to_idx[parent_sha]
                        lane_j = lanes[j]
                        y_j = 16 + j * row_h
                        x_i = x_offset + lane_i * col_w
                        x_j = x_offset + lane_j * col_w
                        color = colors[lane_j % len(colors)]
                        if lane_i == lane_j:
                            canvas.create_line(x_i, y_i, x_j, y_j,
                                              fill=color, width=2)
                        else:
                            # Diagonal merge line
                            canvas.create_line(
                                x_i, y_i, x_i, y_i + row_h // 2,
                                x_j, y_i + row_h // 2, x_j, y_j,
                                fill=color, width=2, smooth=True)

            # Draw nodes
            for i, commit in enumerate(commits):
                lane = lanes[i]
                y = 16 + i * row_h
                x = x_offset + lane * col_w
                color = colors[lane % len(colors)]

                # Node circle
                canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                  fill=color, outline=BG, width=2)

                # Refs (branches/tags)
                ref_text = ""
                refs = commit["refs"]
                if refs:
                    # refs is like " (HEAD -> main, origin/main, tag: v1.0)"
                    ref_text = refs.strip("()").strip()

                # Commit message
                msg = commit["msg"]
                if len(msg) > 35:
                    msg = msg[:32] + "..."

                # Format: refs (if any) + message + author
                tx = text_x
                if ref_text:
                    for ref in ref_text.split(", "):
                        ref_clean = ref.strip()
                        is_head = "HEAD" in ref_clean
                        ref_color = BLUE if is_head else GREEN
                        # Draw ref badge
                        text_id = canvas.create_text(
                            tx, y, anchor="w", text=f" {ref_clean} ",
                            fill="#fff" if is_head else BG,
                            font=("Segoe UI", 8, "bold"))
                        bbox = canvas.bbox(text_id)
                        if bbox:
                            canvas.create_rectangle(
                                bbox[0], bbox[1], bbox[2], bbox[3],
                                fill=ref_color, outline=ref_color)
                            canvas.delete(text_id)
                            canvas.create_text(
                                (bbox[0] + bbox[2]) / 2, y, text=f" {ref_clean} ",
                                fill="#fff" if is_head else "#000",
                                font=("Segoe UI", 8, "bold"))
                            tx = bbox[2] + 4

                canvas.create_text(tx, y, anchor="w",
                                  text=msg, fill=FG,
                                  font=("Segoe UI", 9))
                canvas.create_text(tx, y + 12, anchor="w",
                                  text=f"{commit['author']} · {commit['sha']}",
                                  fill=FG_DIM, font=("Segoe UI", 8))

            # Update scroll region
            total_h = 16 + len(commits) * row_h + 20
            canvas.configure(scrollregion=(0, 0, 600, total_h))

        except Exception as e:
            canvas.create_text(20, 20, anchor="nw",
                              text=f"Graph error: {e}",
                              fill=RED, font=("Segoe UI", 9))

    # ── editor header ─────────────────────────────────────────────────────────
    def _build_editor_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Panel.TFrame", padding=(10, 6))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["source"] = ttk.Label(
            header, text="Source", font=("Segoe UI", 10, "bold"))
        self.static_labels["source"].pack(side=tk.LEFT)
        self.breadcrumb = ttk.Label(header, text="untitled.nx — 1:1",
                                    style="Dim.TLabel")
        self.breadcrumb.pack(side=tk.RIGHT)

    # ── editor ────────────────────────────────────────────────────────────────
    def _build_editor(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, style="Root.TFrame")
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self.line_numbers = tk.Text(
            frame, width=5, padx=8, pady=8,
            bg=PANEL, fg=FG_DIM, relief=tk.FLAT,
            highlightthickness=0, state=tk.DISABLED,
            font=self._effective_code_font(), takefocus=False,
        )
        self.line_numbers.grid(row=0, column=0, sticky="ns")

        self.editor = tk.Text(
            frame, wrap="none", font=self._effective_code_font(),
            undo=True, bg=BG, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, relief=tk.FLAT,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=BLUE, padx=10, pady=8,
            insertwidth=2,
        )
        self.editor.grid(row=0, column=1, sticky="nsew")

        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                command=self._on_editor_scrollbar)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL,
                                command=self.editor.xview)
        yscroll.grid(row=0, column=2, sticky="ns")
        xscroll.grid(row=1, column=1, sticky="ew")
        self.editor.configure(
            yscrollcommand=lambda f, l: self._on_editor_scroll(f, l, yscroll),
            xscrollcommand=xscroll.set,
        )

        # Syntax highlight tags
        self.editor.tag_configure("keyword",          foreground=BLUE)
        self.editor.tag_configure("type",             foreground=GREEN)
        self.editor.tag_configure("number",           foreground=ORANGE)
        self.editor.tag_configure("string",           foreground=ORANGE)
        self.editor.tag_configure("comment",          foreground=FG_DIM)
        self.editor.tag_configure("operator",         foreground=FG)
        self.editor.tag_configure("escape",           foreground=YELLOW)
        self.editor.tag_configure("function",         foreground=YELLOW)
        self.editor.tag_configure("current_line",     background="#242424")
        self.editor.tag_configure("bracket_match",    background="#515c6a")
        self.editor.tag_configure("definition_target",background=SEL_BG)
        self.editor.tag_configure("diagnostic_error", underline=True, foreground=RED)
        self.editor.tag_configure("find_match",
                                   background="#613214", foreground="#ffffff")

    # ── output notebook (all tabs visible) ────────────────────────────────────
    def _build_notebook(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        # Tab visibility toolbar
        tab_bar = ttk.Frame(parent, style="Toolbar.TFrame", padding=(8, 4))
        tab_bar.grid(row=0, column=0, sticky="ew")

        ttk.Label(tab_bar, text="View:", style="Dim.TLabel",
                 background=PANEL_2).pack(side=tk.LEFT, padx=(0, 6))

        self._tab_group_var = tk.StringVar(value="全部")
        self._tab_group_var.trace_add("write",
            lambda *_: self._apply_tab_visibility())
        group_cb = ttk.Combobox(tab_bar, textvariable=self._tab_group_var,
                                values=("主要", "前端", "后端", "全部"),
                                state="readonly", width=6)
        group_cb.pack(side=tk.LEFT)

        # Custom tab pickers (chips) for each output
        ttk.Separator(tab_bar, orient=tk.VERTICAL).pack(
            side=tk.LEFT, padx=8, fill=tk.Y)

        self._tab_visible_vars: dict[str, tk.BooleanVar] = {}
        for name in OUTPUT_ORDER:
            var = tk.BooleanVar(value=False)
            var.trace_add("write",
                lambda *_, n=name: self._apply_tab_visibility(manual=True))
            self._tab_visible_vars[name] = var
            cb = tk.Checkbutton(tab_bar, text=name, variable=var,
                               bg=PANEL_2, fg=FG_DIM, selectcolor=PANEL_3,
                               activebackground=PANEL_2, activeforeground=BLUE,
                               relief=tk.FLAT, borderwidth=0,
                               font=("Segoe UI", 8), padx=2)
            cb.pack(side=tk.LEFT, padx=1)

        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self._add_table_tab("Tokens",   ("#", "Kind", "Lexeme", "Line:Col"),
                            (50, 120, 260, 90))
        self._add_graph_text_tab("AST")
        self._add_table_tab("Symbols",
                            ("Name", "Category", "Type", "Scope", "Slot"),
                            (160, 110, 160, 80, 80))
        self._add_text_tab("HIR")
        self._add_graph_text_tab("CFG")
        self._add_text_tab("ASM")
        self._add_text_tab("LLVM")
        self._add_table_tab("Timeline", ("Stage", "Status", "Detail"),
                            (150, 90, 360))

        self._configure_code_tags()
        # Apply initial visibility
        self.after(50, lambda: self._apply_tab_visibility())

    def _apply_tab_visibility(self, manual: bool = False) -> None:
        if not hasattr(self, "notebook"):
            return

        groups = {
            "主要":  {"AST", "CFG", "ASM"},
            "前端":  {"Tokens", "AST", "Symbols", "HIR"},
            "后端":  {"CFG", "ASM", "LLVM", "Timeline"},
            "全部":  set(OUTPUT_ORDER),
        }

        if not manual:
            group = self._tab_group_var.get()
            target = groups.get(group, groups["全部"])
            # Update checkboxes without re-triggering
            for name, var in self._tab_visible_vars.items():
                want = name in target
                if var.get() != want:
                    var.set(want)
            return

        # Build set of visible tabs from checkboxes
        visible = {n for n, v in self._tab_visible_vars.items() if v.get()}
        if not visible:
            visible = {"AST"}

        # Show/hide tabs
        for name in OUTPUT_ORDER:
            frame = self.output_frames.get(name)
            if frame is None:
                continue
            try:
                if name in visible:
                    self.notebook.add(frame, text=self._output_label(name))
                else:
                    self.notebook.hide(frame)
            except tk.TclError:
                pass

    # ── bottom diagnostics ────────────────────────────────────────────────────
    def _build_diagnostics(self, parent: ttk.Frame) -> None:
        self.bottom_notebook = ttk.Notebook(parent)
        self.bottom_notebook.grid(row=0, column=0, sticky="nsew")

        # Problems tab
        problems = ttk.Frame(self.bottom_notebook, style="Panel.TFrame")
        problems.rowconfigure(1, weight=1)
        problems.columnconfigure(0, weight=1)
        self.bottom_notebook.add(problems, text=self._bottom_label("Problems"))
        self.bottom_frames["Problems"] = problems

        header = ttk.Frame(problems, style="Panel.TFrame", padding=(10, 5))
        header.grid(row=0, column=0, sticky="ew")
        self.static_labels["diagnostics"] = ttk.Label(
            header, text="Diagnostics", font=("Segoe UI", 10, "bold"))
        self.static_labels["diagnostics"].pack(side=tk.LEFT)
        self.diag_summary = ttk.Label(header, text="0 issues",
                                      style="Dim.TLabel")
        self.diag_summary.pack(side=tk.RIGHT)

        columns = ("Level", "Message", "Location")
        self.diag_table = ttk.Treeview(problems, columns=columns,
                                       show="headings", height=4)
        for col, w in zip(columns, (90, 900, 120)):
            self.diag_table.heading(col, text=col)
            self.diag_table.column(col, width=w, stretch=True)
        self.diag_table.tag_configure("error",   foreground=RED)
        self.diag_table.tag_configure("warning", foreground=YELLOW)
        self.diag_table.tag_configure("note",    foreground=FG_DIM)
        self.diag_table.grid(row=1, column=0, sticky="nsew")
        self.diag_table.bind("<Double-1>", self._jump_to_selected_diagnostic)

        self._add_bottom_text_tab("OutputLog")
        self._add_bottom_text_tab("Run")
        self._add_bottom_text_tab("Trace")

    # ── statusbar ─────────────────────────────────────────────────────────────
    def _build_statusbar(self) -> None:
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.grid(row=3, column=0, sticky="ew")
        bar.configure(style="Toolbar.TFrame")

        # Thin top border
        sep = ttk.Separator(bar, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, side=tk.TOP)

        inner = ttk.Frame(bar, style="Toolbar.TFrame", padding=(10, 3))
        inner.pack(fill=tk.X)

        self.status_left = ttk.Label(inner, text=self._t("ready"),
                                     style="Status.TLabel")
        self.status_left.pack(side=tk.LEFT)

        self.bottom_toggle = ttk.Button(inner, text=self._t("collapse_bottom"),
                                        style="Small.TButton",
                                        command=self._toggle_bottom_panel)
        self.bottom_toggle.pack(side=tk.RIGHT, padx=(6, 0))

        self.status_right = ttk.Label(inner, text="", style="Status.TLabel")
        self.status_right.pack(side=tk.RIGHT, padx=(0, 12))

        self.cursor_label = ttk.Label(inner, text="1:1", style="Status.TLabel")
        self.cursor_label.pack(side=tk.RIGHT, padx=(0, 16))

    def _set_status_right(self, text: str) -> None:
        if hasattr(self, "status_right"):
            self.status_right.configure(text=text)

    # ── key bindings ──────────────────────────────────────────────────────────
    def _bind_keys(self) -> None:
        self.bind("<Control-Return>",  lambda _e: self.compile_now(run=False, trace=False))
        self.bind("<F5>",              lambda _e: self.compile_now(run=True,  trace=True))
        self.bind("<F9>",              lambda _e: self._toggle_breakpoint_at_cursor())
        self.bind("<Control-Shift-F>", lambda _e: self._show_left_panel("search"))
        self.bind("<Control-e>",       lambda _e: self._show_left_panel("explorer"))
        self.bind("<Control-Shift-G>", lambda _e: self._show_left_panel("source_control"))
        self.bind("<Control-Shift-D>", lambda _e: self._show_left_panel("debug"))
        self.bind("<Control-n>",       lambda _e: self._new_file())
        self.bind("<Control-o>",       lambda _e: self.open_file())
        self.bind("<Control-Shift-O>", lambda _e: self.open_folder())
        self.bind("<Control-s>",       lambda _e: self.save_file())
        self.bind("<Control-Shift-S>", lambda _e: self.save_file_as())
        self.bind("<F12>",             lambda _e: self.goto_definition())
        self.bind("<F1>",              lambda _e: self._show_shortcuts())
        self.bind("<Control-f>",       lambda _e: self._toggle_find_bar(replace=False))
        self.bind("<Control-h>",       lambda _e: self._toggle_find_bar(replace=True))
        self.bind("<Control-equal>",   lambda _e: self._zoom_editor_font(1))
        self.bind("<Control-minus>",   lambda _e: self._zoom_editor_font(-1))
        self.bind("<Control-0>",       lambda _e: self._zoom_editor_font(0))
        self.bind("<Escape>",          lambda _e: self._close_find_bar()
                                       if self._find_visible else None)

        # Editor-specific
        self.editor.bind("<KeyRelease>",
                         lambda _e: (self._highlight_source_later(),
                                     self._update_breadcrumb()))
        self.editor.bind("<ButtonRelease-1>",
                         lambda _e: (self._highlight_current_line(),
                                     self._highlight_matching_bracket(),
                                     self._update_breadcrumb()))
        self.editor.bind("<Control-Button-1>", self._goto_definition_from_click)
        self.editor.bind("<Button-3>",         self._show_editor_context_menu)

        # Smart typing
        self.editor.bind("<Return>",   self._auto_indent)
        self.editor.bind("<Tab>",      self._insert_tab_spaces)
        for open_ch, close_ch in (("{", "}"), ("(", ")"), ("[", "]")):
            self.editor.bind(
                open_ch,
                lambda e, o=open_ch, c=close_ch: self._auto_close(e, o, c),
            )
            self.editor.bind(
                close_ch,
                lambda e, c=close_ch: self._skip_close_if_present(e, c),
            )

    # ── smart editor helpers ──────────────────────────────────────────────────
    def _auto_indent(self, event) -> str:
        line = self.editor.index(tk.INSERT).split(".")[0]
        line_text = self.editor.get(f"{line}.0", f"{line}.end")
        indent = re.match(r"^(\s*)", line_text).group(1)
        if line_text.rstrip().endswith("{"):
            indent += "    "
        self.editor.insert(tk.INSERT, "\n" + indent)
        self.editor.see(tk.INSERT)
        return "break"

    def _insert_tab_spaces(self, event) -> str:
        self.editor.insert(tk.INSERT, "    ")
        return "break"

    def _auto_close(self, event, open_ch: str, close_ch: str) -> str:
        self.editor.insert(tk.INSERT, open_ch + close_ch)
        pos = self.editor.index(tk.INSERT)
        line, col = pos.split(".")
        self.editor.mark_set(tk.INSERT, f"{line}.{int(col) - 1}")
        return "break"

    def _skip_close_if_present(self, event, close_ch: str) -> str | None:
        pos = self.editor.index(tk.INSERT)
        if self.editor.get(pos) == close_ch:
            self.editor.mark_set(tk.INSERT, f"{pos}+1c")
            return "break"
        return None

    def _toggle_word_wrap(self) -> None:
        mode = "word" if self._word_wrap_var.get() else "none"
        self.editor.configure(wrap=mode)

    # ── context menu ─────────────────────────────────────────────────────────
    def _build_editor_context_menu(self) -> None:
        self.editor_menu = tk.Menu(self, tearoff=False,
                                   bg=PANEL_2, fg=FG,
                                   activebackground="#094771",
                                   activeforeground="#ffffff")
        self._refresh_editor_context_menu()

    def _refresh_editor_context_menu(self) -> None:
        self.editor_menu.delete(0, tk.END)
        self.editor_menu.add_command(
            label=self._t("goto_definition"), command=self.goto_definition)
        self.editor_menu.add_separator()
        self.editor_menu.add_command(
            label=self._t("context_compile"),
            command=lambda: self.compile_now(run=False, trace=False))
        self.editor_menu.add_command(
            label=self._t("context_run"),
            command=lambda: self.compile_now(run=True, trace=True))
        self.editor_menu.add_separator()
        self.editor_menu.add_command(
            label=self._t("apply_fix"), command=self.apply_first_fix)
        self.editor_menu.add_separator()
        self.editor_menu.add_command(
            label=self._t("mi_find"),
            command=lambda: self._toggle_find_bar(replace=False))

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

    # ── language refresh ──────────────────────────────────────────────────────
    def _apply_language(self) -> None:
        for key, button in self.toolbar_buttons.items():
            button.configure(text=self._t(key))
        for key, label in self.static_labels.items():
            label.configure(text=self._t(key))
        if hasattr(self, "notebook"):
            for name, frame in self.output_frames.items():
                self.notebook.tab(frame, text=self._output_label(name))
        if hasattr(self, "bottom_notebook"):
            for name, frame in self.bottom_frames.items():
                self.bottom_notebook.tab(frame, text=self._bottom_label(name))
        if hasattr(self, "diag_summary"):
            if self.last_result:
                self._render_diagnostics(self.last_result)
            else:
                self.diag_summary.configure(
                    text="0 个问题" if self.lang.get() == "zh" else "0 issues")
        if hasattr(self, "status_left") and self.status_left.cget("text") in ("Ready", "就绪"):
            self.status_left.configure(text=self._t("ready"))
        if hasattr(self, "bottom_toggle"):
            self.bottom_toggle.configure(
                text=self._t("expand_bottom") if self._bottom_collapsed
                else self._t("collapse_bottom"))
        if hasattr(self, "editor_menu"):
            self._refresh_editor_context_menu()
        if hasattr(self, "_menubar"):
            self._rebuild_menubar()

    # ── tab helpers ───────────────────────────────────────────────────────────
    def _add_text_tab(self, name: str) -> None:
        frame = ttk.Frame(self.notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(
            frame, wrap="none", font=self._effective_code_font(),
            bg=BG, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, relief=tk.FLAT,
            highlightthickness=0, padx=10, pady=8,
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

        img_frame = ttk.Frame(pane, style="Root.TFrame")
        img_frame.rowconfigure(0, weight=1)
        img_frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(img_frame, bg=BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.create_text(16, 16, anchor="nw", text=self._t("graph_pending"),
                           fill=FG_DIM, font=FONT_UI)
        canvas.bind("<ButtonPress-1>", self._start_pan)
        canvas.bind("<B1-Motion>",     lambda e, n=name: self._pan_graph(e, n))
        canvas.bind("<Control-MouseWheel>",
                    lambda e, n=name: self._zoom_graph(e, n))
        pane.add(img_frame, weight=2)

        txt_frame = ttk.Frame(pane, style="Root.TFrame")
        txt_frame.rowconfigure(0, weight=1)
        txt_frame.columnconfigure(0, weight=1)
        text = tk.Text(
            txt_frame, wrap="none", font=self._effective_code_font(),
            bg=BG, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, relief=tk.FLAT,
            highlightthickness=0, padx=10, pady=8,
        )
        yscroll = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=text.yview)
        xscroll = ttk.Scrollbar(txt_frame, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        pane.add(txt_frame, weight=1)

        self.notebook.add(frame, text=self._output_label(name))
        self.output_frames[name] = frame
        self.text_views[name] = text
        self.graph_canvases[name] = canvas
        self._graph_scales[name] = 1.0

    def _add_table_tab(self, name: str, columns: tuple[str, ...],
                       widths: tuple[int, ...]) -> None:
        frame = ttk.Frame(self.notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=columns, show="headings")
        for col, w in zip(columns, widths):
            table.heading(col, text=col)
            table.column(col, width=w, stretch=True)
        for tag, color in (("ok", GREEN), ("warning", YELLOW),
                           ("failed", RED), ("skipped", FG_DIM), ("error", RED)):
            table.tag_configure(tag, foreground=color)
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=table.yview)
        xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=table.xview)
        table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.notebook.add(frame, text=self._output_label(name))
        self.output_frames[name] = frame
        self.tables[name] = table

    def _add_bottom_text_tab(self, name: str) -> None:
        frame = ttk.Frame(self.bottom_notebook, style="Root.TFrame")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(
            frame, wrap="none", font=self._effective_code_font(),
            bg=BG, fg=FG, insertbackground=FG,
            selectbackground=SEL_BG, relief=tk.FLAT,
            highlightthickness=0, padx=10, pady=8,
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

    def _configure_code_tags(self) -> None:
        for text in self.text_views.values():
            text.tag_configure("keyword", foreground=BLUE)
            text.tag_configure("type",    foreground=GREEN)
            text.tag_configure("number",  foreground=ORANGE)
            text.tag_configure("comment", foreground=FG_DIM)
            text.tag_configure("label",   foreground=YELLOW)
            text.tag_configure("branch",  foreground=RED)
            text.tag_configure("ok",      foreground=GREEN)
            text.tag_configure("warning", foreground=YELLOW)
            text.tag_configure("error",   foreground=RED)

    # ── text/table setters ────────────────────────────────────────────────────
    def _set_text(self, name: str, content: str,
                  highlighter: str | None = None) -> None:
        text = self.text_views[name]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        if highlighter:
            self._highlight_view(text, highlighter)
        text.configure(state=tk.DISABLED)

    def _set_table(self, name: str, rows: list[tuple],
                   tags: list[str] | None = None) -> None:
        table = self.tables[name]
        table.delete(*table.get_children())
        for i, row in enumerate(rows):
            tag = tags[i] if tags and i < len(tags) else ""
            table.insert("", tk.END, values=row, tags=(tag,) if tag else ())

    def _set_bottom_text(self, name: str, content: str) -> None:
        text = self.bottom_text_views[name]
        text.configure(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert("1.0", content)
        text.configure(state=tk.DISABLED)

    # ── syntax highlighters ───────────────────────────────────────────────────
    def _highlight_view(self, text: tk.Text, kind: str) -> None:
        for tag in ("keyword", "type", "number", "comment", "label", "branch",
                    "ok", "warning", "error"):
            text.tag_remove(tag, "1.0", tk.END)
        content = text.get("1.0", tk.END)
        patterns: dict[str, list] = {
            "llvm": [
                ("keyword", r"\b(define|declare|private|constant|ret|br|call|store|load|alloca)\b"),
                ("type",    r"\b(i32|i1|i8\*|double|void)\b"),
                ("label",   r"^[A-Za-z_][\w.]*:"),
                ("number",  r"%[\w.]+|@\w+"),
            ],
            "asm": [
                ("label",   r"^[A-Za-z_.$][\w.$]*:"),
                ("keyword", r"\b(mov|add|sub|imul|idiv|cmp|jne|jmp|call|ret|leave|"
                            r"push|cqo|sete|setne|setl|setle|setg|setge|movzx)\b"),
                ("type",    r"\b(r(?:ax|bx|cx|dx|bp|sp|di|si|1[0-5]|8|9)|e[a-d]x)\b"),
                ("comment", r";.*$"),
            ],
            "hir": [
                ("branch",  r"\b(BRANCH_TRUE|BRANCH_READY|JUMP)\b"),
                ("keyword", r"\b(CONST|MOVE|BIN|UNARY|ARG|CALL|RET|PARAM|LABEL|"
                            r"ARRAY_NEW|ARRAY_GET|ARRAY_SET|STRUCT_NEW|FIELD_GET|FIELD_SET)\b"),
                ("type",    r"\b(i32|f64|bool|str|Chan|Array)\b"),
            ],
        }
        for tag, pattern in patterns.get(kind, []):
            for match in re.finditer(pattern, content, flags=re.MULTILINE):
                text.tag_add(tag, f"1.0+{match.start()}c",
                             f"1.0+{match.end()}c")

    def _highlight_source_later(self) -> None:
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(120, self._highlight_source)

    def _highlight_source(self) -> None:
        self._highlight_job = None
        content = self.editor.get("1.0", tk.END)
        for tag in ("keyword", "type", "number", "string", "comment",
                    "operator", "escape", "function"):
            self.editor.tag_remove(tag, "1.0", tk.END)
        patterns = [
            ("comment",  r"/\*.*?\*/",              re.MULTILINE | re.DOTALL),
            ("comment",  r"//.*$",                  re.MULTILINE),
            ("string",   r'"(?:[^"\\]|\\.)*"',      re.MULTILINE),
            ("escape",   r'\\[nrt"\\]',              re.MULTILINE),
            ("function", r"\b[A-Za-z_]\w*(?=\s*\()", re.MULTILINE),
            ("keyword",  r"\b(import|pub|fn|let|return|if|else|while|for|in|"
                         r"break|continue|struct|impl|enum|match|macro|spawn|"
                         r"select|recv|send|default|true|false)\b", re.MULTILINE),
            ("type",     r"\b(i32|f64|bool|str|Chan|Ord)\b", re.MULTILINE),
            ("number",   r"\b\d+(?:\.\d+)?\b",      re.MULTILINE),
            ("operator", r"->|=>|==|!=|<=|>=|&&|\|\||[+\-*/%=<>!]", re.MULTILINE),
        ]
        for tag, pattern, flags in patterns:
            for match in re.finditer(pattern, content, flags=flags):
                self.editor.tag_add(
                    tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
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
            if ch in "([{}])":
                match = self._find_matching_bracket(pos, ch)
                if match:
                    self.editor.tag_add("bracket_match", pos,   f"{pos}+1c")
                    self.editor.tag_add("bracket_match", match, f"{match}+1c")
                return

    def _find_matching_bracket(self, pos: str, ch: str) -> str | None:
        forward = ch in "([{"
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
        file_name = (str(self.current_file) if self.current_file
                     else "untitled.nx")
        line, col = self.editor.index(tk.INSERT).split(".")
        self.breadcrumb.configure(text=f"{file_name} — {line}:{int(col)+1}")
        if hasattr(self, "cursor_label"):
            self.cursor_label.configure(text=f"Ln {line}, Col {int(col)+1}")

    # ── line numbers + scroll ─────────────────────────────────────────────────
    def _refresh_line_numbers(self) -> None:
        line_count = int(self.editor.index("end-1c").split(".")[0])
        numbers = "\n".join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.configure(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", numbers)
        self.line_numbers.configure(state=tk.DISABLED)

    def _on_editor_scroll(self, first: str, last: str,
                          scrollbar: ttk.Scrollbar) -> None:
        scrollbar.set(first, last)
        self.line_numbers.yview_moveto(first)

    def _on_editor_scrollbar(self, *args) -> None:
        self.editor.yview(*args)
        self.line_numbers.yview(*args)

    # ── file operations ───────────────────────────────────────────────────────
    def _new_file(self) -> None:
        self.editor.delete("1.0", tk.END)
        self.current_file = None
        self.file_label.configure(text="untitled.nx")
        self._highlight_source()

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Nexa source", "*.nx"), ("All files", "*.*")])
        if path:
            self._load_file(Path(path), keep_explorer=False)

    def open_folder(self) -> None:
        path = filedialog.askdirectory(initialdir=str(self.workspace_root))
        if not path:
            return
        self.workspace_root = Path(path)
        self._show_explorer()
        self._refresh_explorer()
        self.status_left.configure(
            text=f"{self._t('open_folder')}: {self.workspace_root}")

    def _load_file(self, target: Path, keep_explorer: bool = True) -> None:
        try:
            text = target.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            messagebox.showerror("Nexa Studio",
                                 f"Cannot open non-text file:\n{target}")
            return
        if not keep_explorer:
            self._hide_explorer()
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self.current_file = target
        self.file_label.configure(text=str(target))

        # Track open file
        if target not in self.open_files:
            self.open_files.append(target)
        self._refresh_open_editors()

        self._highlight_source()
        self.compile_now(run=False, trace=False)

    def save_file(self) -> None:
        if self.current_file is None:
            self.save_file_as()
            return
        self.current_file.write_text(self.editor.get("1.0", "end-1c"),
                                     encoding="utf-8")
        self.status_left.configure(
            text=f"{self._t('save')}: {self.current_file.name}")

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".nx",
            filetypes=[("Nexa source", "*.nx"), ("All files", "*.*")])
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
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML report", "*.html"), ("All files", "*.*")])
        if not path:
            return
        write_html_report(Path(path), self.last_result)
        self.status_left.configure(
            text=f"{self._t('report')}: {Path(path).name}")

    # ── compile ───────────────────────────────────────────────────────────────
    def compile_now(self, run: bool = False, trace: bool = False) -> None:
        self._highlight_source()
        self.status_left.configure(text=self._t("compiling"), foreground=FG_DIM)
        self.update_idletasks()

        t0 = time.perf_counter()
        source = self.editor.get("1.0", tk.END)
        res = compile_source(source, mode=self.mode.get(),
                             export_dir="out", run=run, trace=trace)
        elapsed = time.perf_counter() - t0
        self.last_result = res

        self._render_result(res)

        errors   = sum(1 for d in res.diagnostics if str(d.level) == "error")
        warnings = sum(1 for d in res.diagnostics if str(d.level) == "warning")
        is_zh = self.lang.get() == "zh"
        if errors:
            status_txt = (f"● 编译失败  {errors} 个错误  {warnings} 个警告"
                          if is_zh
                          else f"● Compile failed  {errors} error(s)  {warnings} warning(s)")
            self.status_left.configure(text=status_txt, foreground=RED)
        else:
            status_txt = (f"● 编译成功  {warnings} 个警告" if is_zh
                          else f"● Compiled OK  {warnings} warning(s)")
            self.status_left.configure(text=status_txt, foreground=GREEN)

        self._set_status_right(
            f"tokens {len(res.artifacts.token_rows)} | "
            f"symbols {len(res.artifacts.symbol_rows)} | "
            f"{elapsed * 1000:.0f} ms"
        )

    def _render_result(self, res: BuildResult) -> None:
        token_rows = [
            (i + 1, row["kind"], row["lexeme"], f'{row["line"]}:{row["col"]}')
            for i, row in enumerate(res.artifacts.token_rows)
        ]
        self._set_table("Tokens", token_rows)

        self._set_text("AST", res.artifacts.ast_text)
        self._set_table(
            "Symbols",
            [(r["name"], r["category"], r["type"], r["scope"], r["slot"])
             for r in res.artifacts.symbol_rows],
        )

        hir_lines = ["RAW HIR"]
        hir_lines.extend(self._format_hir_rows(res.artifacts.hir_raw_structured))
        hir_lines += ["", "OPTIMIZED HIR"]
        hir_lines.extend(self._format_hir_rows(res.artifacts.hir_opt_structured))
        self._set_text("HIR", "\n".join(hir_lines), "hir")

        cfg_lines: list[str] = []
        for fn, graph in res.artifacts.cfg_structured.items():
            cfg_lines.append(f"{fn}:")
            cfg_lines.append("  blocks:")
            for block in graph.get("blocks", []):
                cfg_lines.append(f"    [{block['id']}]")
                cfg_lines.extend(f"      {ins}" for ins in block.get("instrs", []))
            cfg_lines.append("  edges:")
            for edge in graph.get("edges", []):
                lbl = f" ({edge['label']})" if edge.get("label") else ""
                cfg_lines.append(f"    {edge['from']} -> {edge['to']}{lbl}")
            cfg_lines.append("")
        self._set_text("CFG", "\n".join(cfg_lines))

        self._set_text(
            "ASM",
            "\n\n".join(f"-- {n} --\n{t}"
                        for n, t in res.artifacts.asm.items()),
            "asm",
        )
        self._set_text("LLVM", res.artifacts.llvm_ir, "llvm")

        tl_tags = [stage.status for stage in res.timeline]
        self._set_table(
            "Timeline",
            [(s.name, s.status, s.detail) for s in res.timeline],
            tl_tags,
        )

        output_lines = [
            "Pipeline",
            *[f"{s.name:<12} {s.status:<8} {s.detail}" for s in res.timeline],
            "",
            f"tokens={len(res.artifacts.token_rows)}  "
            f"symbols={len(res.artifacts.symbol_rows)}  "
            f"diagnostics={len(res.diagnostics)}",
        ]
        if res.run_value is not None:
            output_lines.append(f"exit={res.run_value}")
        self._set_bottom_text("OutputLog", "\n".join(output_lines))

        run_lines = list(res.run_stdout)
        if res.run_value is not None:
            run_lines.append(f"exit={res.run_value}")
        self._set_bottom_text("Run",
                              "\n".join(run_lines) or self._t("run_disabled"))
        self._set_bottom_text(
            "Trace",
            "\n".join(
                f"#{i+1:04d} {f.fn}@{f.ip} {f.instr:<12} env={f.env}"
                for i, f in enumerate(res.vm_trace)
            ) or self._t("trace_disabled"),
        )

        self._render_diagnostics(res)
        self._render_graph_images()

    def _format_hir_rows(self, rows: list[dict]) -> list[str]:
        return [
            f"{r['fn']:<14} {r['index']:>3}  {r['kind']:<13} {r['text']}"
            for r in rows
        ]

    def _render_diagnostics(self, res: BuildResult) -> None:
        self.diag_table.delete(*self.diag_table.get_children())
        self.editor.tag_remove("diagnostic_error", "1.0", tk.END)
        for diag in res.diagnostics:
            level    = str(diag.level)
            location = f"{diag.span.line}:{diag.span.col}"
            item = self.diag_table.insert(
                "", tk.END, values=(level, diag.message, location),
                tags=(level,))
            self.diag_table.set(item, "Location", location)
            if level == "error":
                start = f"{diag.span.line}.{max(diag.span.col - 1, 0)}"
                self.editor.tag_add("diagnostic_error", start, f"{start}+1c")
        errors   = sum(1 for d in res.diagnostics if str(d.level) == "error")
        warnings = sum(1 for d in res.diagnostics if str(d.level) == "warning")
        if self.lang.get() == "zh":
            self.diag_summary.configure(
                text=f"{errors} 个错误，{warnings} 个警告")
        else:
            self.diag_summary.configure(
                text=f"{errors} error(s), {warnings} warning(s)")

    def _jump_to_selected_diagnostic(self, _event=None) -> None:
        selected = self.diag_table.selection()
        if not selected or self.last_result is None:
            return
        location = self.diag_table.item(selected[0], "values")[2]
        try:
            line, col = (int(p) for p in location.split(":", 1))
        except ValueError:
            return
        for diag in self.last_result.diagnostics:
            if diag.span.line == line and diag.span.col == col:
                self._jump_to_diagnostic(diag)
                return

    # ── graph rendering ───────────────────────────────────────────────────────
    def _render_graph_images(self) -> None:
        if Image is None or ImageTk is None:
            for canvas in self.graph_canvases.values():
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw",
                                   text=self._t("pillow_missing"),
                                   fill=YELLOW, font=FONT_UI)
            return
        dot_env = os.environ.get("GRAPHVIZ_DOT")
        dot = (dot_env if dot_env and Path(dot_env).exists()
               else shutil.which("dot"))
        if not dot:
            for canvas in self.graph_canvases.values():
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw",
                                   text=self._t("dot_missing"),
                                   fill=YELLOW, font=FONT_UI)
            return
        out_dir = Path("out")
        ast_dot = out_dir / "ast.dot"
        if ast_dot.exists():
            self._render_dot_file("AST", dot, ast_dot, out_dir / "ast.png")
        cfg_dot = (next(out_dir.glob("cfg_*.dot"), None)
                   if out_dir.exists() else None)
        if cfg_dot:
            self._render_dot_file("CFG", dot, cfg_dot,
                                  cfg_dot.with_suffix(".png"))

    def _render_dot_file(self, name: str, dot: str,
                         src: Path, dst: Path) -> None:
        try:
            subprocess.run([dot, "-Tpng", str(src), "-o", str(dst)],
                           check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            canvas = self.graph_canvases.get(name)
            if canvas:
                canvas.delete("all")
                canvas.create_text(16, 16, anchor="nw",
                                   text=f"{self._t('dot_failed')} {src.name}",
                                   fill=RED, font=FONT_UI)
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
        path  = self._graph_paths[name]
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
        canvas.configure(scrollregion=(0, 0,
                                       image.width + 24, image.height + 24))

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
        cur = self._graph_scales.get(name, 1.0)
        self._graph_scales[name] = (min(3.0, cur * 1.1) if event.delta > 0
                                    else max(0.25, cur / 1.1))
        self._show_graph_image(name)

    # ── go-to-definition ──────────────────────────────────────────────────────
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
        current_path = (self.current_file.resolve()
                        if self.current_file else None)
        base_dir = (current_path.parent if current_path
                    else self.workspace_root.resolve())
        index: dict[str, tuple[Path | None, int, int, str]] = {}
        self._scan_definitions(source, current_path, index)
        self._scan_import_definitions(source, base_dir, index, set())
        self.definition_index = index

    def _scan_import_definitions(self, source: str, base_dir: Path,
                                  index: dict, seen: set[Path]) -> None:
        for match in re.finditer(
                r'^\s*import\s+(?:"([^"]+)"|([A-Za-z_]\w*))\s*;',
                source, re.MULTILINE):
            raw = match.group(1) or match.group(2) or ""
            path = self._resolve_import_path_for_ide(raw, base_dir)
            index.setdefault(path.stem, (path, 1, 1, "module"))
            if path in seen or not path.exists():
                continue
            seen.add(path)
            try:
                imported = path.read_text(encoding="utf-8-sig")
            except OSError:
                continue
            self._scan_definitions(imported, path, index)
            self._scan_import_definitions(imported, path.parent, index, seen)

    def _scan_definitions(self, source: str, path: Path | None,
                          index: dict) -> None:
        for kind, pattern in (
            ("fn",     r"\bfn\s+([A-Za-z_]\w*)\s*\(([^)]*)"),
            ("struct", r"\bstruct\s+([A-Za-z_]\w*)\b"),
            ("let",    r"\blet\s+([A-Za-z_]\w*)\b"),
        ):
            for match in re.finditer(pattern, source):
                name = match.group(1)
                line, col = self._line_col_from_offset(source, match.start(1))
                index[name] = (path, line, col, kind)
                if kind == "fn":
                    params = match.group(2)
                    ps = match.start(2)
                    for p in re.finditer(r"\b([A-Za-z_]\w*)\s*:", params):
                        pname = p.group(1)
                        pl, pc = self._line_col_from_offset(source, ps + p.start(1))
                        if path == self.current_file or path is None:
                            index[pname] = (path, pl, pc, "param")

    def _identifier_at_index(self, index: str) -> str:
        start = self.editor.index(f"{index} wordstart")
        end   = self.editor.index(f"{index} wordend")
        word  = self.editor.get(start, end)
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
            self.status_left.configure(
                text=f"{self._t('definition_not_found')}: {symbol}")
            return
        path, line, col, kind = target
        if path is not None and (
                self.current_file is None
                or path.resolve() != self.current_file.resolve()):
            self._load_file(path, keep_explorer=self.explorer_visible)
        index = f"{line}.{max(col - 1, 0)}"
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self.editor.see(index)
        self.editor.tag_remove("definition_target", "1.0", tk.END)
        self.editor.tag_add("definition_target", index, f"{index}+{len(symbol)}c")
        self.status_left.configure(
            text=f"{self._t('goto_definition')}: {symbol} ({kind})")

    # ── shortcuts & about ─────────────────────────────────────────────────────
    def _show_shortcuts(self) -> None:
        messagebox.showinfo(self._t("shortcuts_title"), self._t("shortcuts"))

    def _show_about(self) -> None:
        messagebox.showinfo(self._t("about_title"), self._t("about_body"))

    # ── quick-fix panel ───────────────────────────────────────────────────────
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
        for diag in self.last_result.diagnostics:
            if not diag.fixits:
                continue
            code  = f"{diag.code} " if diag.code else ""
            where = f"{diag.span.line}:{diag.span.col}"
            for fix_text in diag.fixits:
                label = f"[{where}] {code}{diag.message} → {fix_text}"
                items.append((label, diag, fix_text))
        return items

    def _show_fix_panel(self, fixes: list[tuple[str, object, str]]) -> None:
        win = tk.Toplevel(self)
        win.title(self._t("quick_fixes"))
        win.configure(bg=PANEL)
        win.geometry("780x360")
        win.transient(self)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        frame = ttk.Frame(win, style="Panel.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        listbox = tk.Listbox(
            frame, bg=BG, fg=FG,
            selectbackground="#094771", selectforeground="#ffffff",
            activestyle="none", font=self._effective_code_font(),
            relief=tk.FLAT, highlightthickness=1,
            highlightbackground=BORDER,
        )
        yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                command=listbox.yview)
        listbox.configure(yscrollcommand=yscroll.set)
        listbox.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        for label, _, _ in fixes:
            listbox.insert(tk.END, label)
        listbox.selection_set(0)

        btn_row = ttk.Frame(frame, style="Panel.TFrame")
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        def _sel():
            s = listbox.curselection()
            return fixes[s[0]] if s else None

        def apply_selected() -> None:
            item = _sel()
            if item and self._apply_fixit(item[1], item[2]):
                win.destroy()
                self.compile_now()

        def jump_selected() -> None:
            item = _sel()
            if item:
                self._jump_to_diagnostic(item[1])

        def apply_safe() -> None:
            count = self._apply_all_safe_fixes(fixes)
            if count:
                win.destroy()
                self.compile_now()
                self.status_left.configure(
                    text=f"{self._t('safe_fixed')}: {count}")

        ttk.Button(btn_row, text=self._t("apply_selected"),
                   style="Accent.TButton", command=apply_selected).pack(
            side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=self._t("apply_all_safe"),
                   command=apply_safe).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=self._t("jump"),
                   command=jump_selected).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text=self._t("close"),
                   command=win.destroy).pack(side=tk.RIGHT)
        listbox.bind("<Double-1>", lambda _e: apply_selected())

    def _jump_to_diagnostic(self, diagnostic) -> None:
        index = f"{diagnostic.span.line}.{max(diagnostic.span.col - 1, 0)}"
        self.editor.focus_set()
        self.editor.mark_set(tk.INSERT, index)
        self.editor.see(index)

    def _apply_all_safe_fixes(self, fixes: list[tuple[str, object, str]]) -> int:
        semicolons: set[tuple[int, int]] = set()
        for _lbl, diag, fix_text in fixes:
            if self._is_semicolon_fix(diag, fix_text):
                semicolons.add((diag.span.line, max(diag.span.col - 1, 0)))
        for line, col in sorted(semicolons, reverse=True):
            index = f"{line}.{col}"
            if self.editor.get(index) != ";":
                self.editor.insert(index, ";")
        return len(semicolons)

    def _is_semicolon_fix(self, diagnostic, fix_text: str) -> bool:
        msg = diagnostic.message
        return (diagnostic.code == "E001" or ";" in fix_text
                or "semicolon" in msg.lower() or "分号" in msg)

    def _apply_fixit(self, diagnostic, fix_text: str) -> bool:
        msg  = diagnostic.message
        line = diagnostic.span.line
        col  = max(diagnostic.span.col - 1, 0)
        if self._is_semicolon_fix(diagnostic, fix_text):
            self.editor.insert(f"{line}.{col}", ";")
            return True
        decl = re.search(r"let\s+([A-Za-z_]\w*)\s*:\s*([A-Za-z0-9_]+)", fix_text)
        if decl or diagnostic.code == "E002" or "未声明" in msg:
            name = decl.group(1) if decl else self._extract_name(msg)
            ty   = decl.group(2) if decl else self._infer_fix_type(line)
            cur  = self.editor.get(f"{line}.0", f"{line}.end")
            indent = re.match(r"\s*", cur).group(0)
            self.editor.insert(
                f"{line}.0",
                f"{indent}let {name}: {ty} = {self._default_value(ty)};\n")
            return True
        tm = re.search(r"(?:改为|to|为)\s*([A-Za-z0-9_]+)", fix_text)
        if tm or diagnostic.code == "E003" or "类型不匹配" in msg:
            desired = tm.group(1) if tm else self._infer_fix_type(line)
            text    = self.editor.get(f"{line}.0", f"{line}.end")
            match   = re.search(r":\s*[A-Za-z0-9_]+", text)
            if match:
                self.editor.delete(f"{line}.{match.start()}",
                                   f"{line}.{match.end()}")
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
        if re.search(r"\d+\.\d+", text):  return "f64"
        if re.search(r"\b(true|false)\b", text): return "bool"
        if '"' in text: return "str"
        return "i32"

    def _default_value(self, ty: str) -> str:
        return {"f64": "0.0", "bool": "false", "str": '""'}.get(ty, "0")


def main() -> None:
    app = NexaStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
