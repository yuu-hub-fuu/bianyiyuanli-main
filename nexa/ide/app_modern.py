# 现代化UI改进模块 - 在app.py中调用这些方法替换旧的

def _build_activity_bar(self) -> None:
    """左侧活动栏 - VS Code风格"""
    self.activity_bar = tk.Frame(self, bg="#1e1e1e", width=48)
    self.activity_bar.grid(row=0, rowspan=4, column=0, sticky="ns")
    self.activity_bar.columnconfigure(0, weight=1)
    
    # 活动栏按钮
    activities = [
        ("📁", "Explorer", lambda: self._toggle_panel("explorer")),
        ("🔍", "Search", lambda: self._toggle_panel("search")),
        ("📊", "Output", lambda: self._toggle_panel("output")),
        ("⚙", "Settings", lambda: self._toggle_panel("settings")),
    ]
    
    for i, (icon, label, cmd) in enumerate(activities):
        btn = tk.Label(
            self.activity_bar, text=icon, font=("Segoe UI", 20),
            fg="#858585", bg="#1e1e1e", cursor="hand2",
            width=6, height=3
        )
        btn.grid(row=i, column=0, sticky="ew")
        btn.bind("<Button-1>", lambda e, c=cmd: c())
        btn.bind("<Enter>", lambda e, l=label: self._show_activity_tooltip(e, l))
        btn.bind("<Leave>", self._hide_tooltip)

def _build_top_bar(self) -> None:
    """顶部栏 - 菜单+工具栏集成"""
    top = tk.Frame(self, bg="#252526", height=52)
    top.grid(row=0, column=1, sticky="ew")
    top.columnconfigure(1, weight=1)
    
    # 左侧：文件操作
    left = tk.Frame(top, bg="#252526")
    left.grid(row=0, column=0, sticky="w", padx=6, pady=6)
    
    def _icon_btn(parent, icon, cmd, tooltip=""):
        b = tk.Label(parent, text=icon, font=("Segoe UI", 12), fg="#d4d4d4",
                     bg="#252526", cursor="hand2", padx=8, pady=4)
        b.pack(side=tk.LEFT, padx=2)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: self._show_tooltip_at_widget(e, tooltip) if tooltip else None)
        return b
    
    _icon_btn(left, "🆕", self._new_file, "新建文件 (Ctrl+N)")
    _icon_btn(left, "📂", self.open_folder, "打开文件夹 (Ctrl+Shift+O)")
    _icon_btn(left, "💾", self.save_file, "保存 (Ctrl+S)")
    
    tk.Frame(left, bg="#3c3c3c", width=1, height=24).pack(side=tk.LEFT, padx=4, fill=tk.Y)
    
    # 中央：主操作按钮
    center = tk.Frame(top, bg="#252526")
    center.grid(row=0, column=1, sticky="w", padx=6, pady=6)
    
    # 编译按钮（优秀的视觉）
    compile_btn = tk.Label(
        center, text="⚙  编译", font=("Segoe UI", 10, "bold"),
        fg="#ffffff", bg="#0078d4", padx=12, pady=4, cursor="hand2",
        relief=tk.FLAT, bd=0
    )
    compile_btn.pack(side=tk.LEFT, padx=4)
    compile_btn.bind("<Button-1>", lambda e: self.compile_now(run=False, trace=False))
    compile_btn.bind("<Enter>", lambda e: compile_btn.config(bg="#1f8ad4"))
    compile_btn.bind("<Leave>", lambda e: compile_btn.config(bg="#0078d4"))
    
    # 运行按钮
    run_btn = tk.Label(
        center, text="▶  运行", font=("Segoe UI", 10),
        fg="#d4d4d4", bg="#2d2d30", padx=12, pady=4, cursor="hand2",
        relief=tk.FLAT, bd=0
    )
    run_btn.pack(side=tk.LEFT, padx=2)
    run_btn.bind("<Button-1>", lambda e: self.compile_now(run=True, trace=True))
    run_btn.bind("<Enter>", lambda e: run_btn.config(bg="#3a3a3d"))
    run_btn.bind("<Leave>", lambda e: run_btn.config(bg="#2d2d30"))
    
    # 右侧：模式 + 语言 + 缩放
    right = tk.Frame(top, bg="#252526")
    right.grid(row=0, column=2, sticky="e", padx=8, pady=6)
    
    tk.Label(right, text="模式:", font=("Segoe UI", 9), fg="#858585", bg="#252526").pack(side=tk.LEFT, padx=(0, 4))
    mode_cb = ttk.Combobox(right, textvariable=self.mode, values=("full", "core"),
                           width=6, state="readonly", font=("Segoe UI", 9))
    mode_cb.pack(side=tk.LEFT, padx=(0, 12))
    
    _icon_btn(right, "🔤", lambda: self._zoom_editor_font(1), "放大 (Ctrl+=)")
    _icon_btn(right, "◀", lambda: self._zoom_editor_font(-1), "缩小 (Ctrl+-)")
    
    self.toolbar_buttons["mode_box"] = mode_cb

def _build_editor_tabs(self, parent: ttk.Frame) -> None:
    """编辑器标签页 - 显示打开的文件"""
    tabs_frame = tk.Frame(parent, bg="#2d2d30", height=32)
    tabs_frame.grid(row=0, column=0, sticky="ew")
    tabs_frame.columnconfigure(0, weight=1)
    
    self.editor_tabs_container = tk.Frame(tabs_frame, bg="#2d2d30")
    self.editor_tabs_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    self.open_files = {}  # {tab_id: Path}
    self._add_editor_tab("untitled.nx", None)

def _add_editor_tab(self, name: str, path: Path | None) -> None:
    """添加编辑器标签页"""
    tab_id = len(self.open_files)
    self.open_files[tab_id] = path
    
    tab = tk.Label(
        self.editor_tabs_container, text=f"  {name}  ",
        font=("Segoe UI", 9), fg="#858585", bg="#2d2d30",
        padx=8, pady=6, cursor="hand2"
    )
    tab.pack(side=tk.LEFT)
    tab.bind("<Button-1>", lambda e, tid=tab_id: self._select_editor_tab(tid))
    tab.bind("<Button-3>", lambda e, tid=tab_id: self._close_editor_tab(tid))
    tab.bind("<Enter>", lambda e: tab.config(fg="#d4d4d4"))
    tab.bind("<Leave>", lambda e: tab.config(fg="#858585"))

def _select_editor_tab(self, tab_id: int) -> None:
    """选择编辑器标签页"""
    if tab_id in self.open_files:
        path = self.open_files[tab_id]
        if path:
            self._load_file(path)

def _close_editor_tab(self, tab_id: int) -> None:
    """关闭编辑器标签页"""
    if tab_id in self.open_files:
        del self.open_files[tab_id]

def _show_tooltip_at_widget(self, event, text: str) -> None:
    """在widget处显示tooltip"""
    if not hasattr(self, '_tooltip_label'):
        self._tooltip_label = tk.Label(
            self, text=text, bg="#3c3c3c", fg="#d4d4d4",
            font=("Segoe UI", 9), padx=8, pady=4,
            relief=tk.FLAT, bd=0
        )
    self._tooltip_label.config(text=text)
    self._tooltip_label.place(x=event.x_root - 20, y=event.y_root + 20)

def _hide_tooltip(self, event=None) -> None:
    """隐藏tooltip"""
    if hasattr(self, '_tooltip_label'):
        self._tooltip_label.place_forget()

def _toggle_panel(self, panel: str) -> None:
    """切换左侧面板"""
    if panel == "explorer":
        self._toggle_explorer()
    # 其他panel的处理...

