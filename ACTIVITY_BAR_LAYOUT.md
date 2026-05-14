# VSCode-Style Activity Bar Layout

## 📐 布局结构

现在IDE采用真正的VSCode双栏布局：

```
┌────────────────────────────────────────────────────────────────┐
│ 菜单栏 (File, Edit, View, Run, Help)                           │
├────────────────────────────────────────────────────────────────┤
│ 工具栏 (Run, Compile, New, Open, Save, etc.)                   │
├────────────────────────────────────────────────────────────────┤
│ 查找栏 (可选，Ctrl+F 显示)                                      │
├──────┬──────────────────────────────────────────┬──────────────┤
│      │                                          │              │
│  📁  │  OPEN EDITORS                            │              │
│  🔍  │  ▼ main.nx                               │   编辑器     │
│  ⚡  │  🐍 config.py                            │   区域       │
│  🐛  │                                          │              │
│      │  BIANYIYUANLI-MAIN                       │              │
│  ─── │  ▾ bianyiyuanli/                         │              │
│      │    ◆ main.nx                             │              │
│  🧩  │    ▸ nexa/                               │              │
│      │      🐍 __init__.py                      │              │
│      │      📁 compiler/                        │              │
│      │    📝 README.md                          │              │
│      │    ⚙ pyproject.toml                      │              │
│      │                                          │              │
│      │                                          │  输出/编译   │
│      │                                          │  结果 tabs   │
├──────┼──────────────────────────────────────────┼──────────────┤
│ 状态栏 (Ready | Line:Col | Compile time)                       │
└──────┴──────────────────────────────────────────┴──────────────┘
```

## 🎯 Activity Bar (左侧竖列)

最左边是一个**固定50px宽**的竖列图标栏：

| 图标 | 名称 | 快捷键 | 功能 |
|------|------|--------|------|
| 📁 | Explorer | Ctrl+E | 文件浏览器 |
| 🔍 | Search | — | 全文搜索（待实现） |
| ⚡ | Source Control | Ctrl+Shift+G | Git面板 |
| 🐛 | Debug | — | 调试器（待实现） |
| ─── | Separator | — | 视觉分隔符 |
| 🧩 | Extensions | — | 扩展（待实现） |

### Activity Bar 特点
- **竖列排列** - 所有功能图标竖向堆叠
- **固定宽度** - 50px，不随窗口大小变化
- **颜色反馈** - 点击时变成蓝色 (#4db8ff)
- **Tooltip提示** - 悬停显示功能名
- **快捷键** - 支持Ctrl+E、Ctrl+Shift+G等

## 📂 Side Panel (Activity Bar 右侧)

点击Activity Bar中的图标，右侧显示对应的内容：

### 📁 Explorer (文件浏览)
```
OPEN EDITORS
▼ main.nx
  🐍 config.py

BIANYIYUANLI-MAIN
▾ bianyiyuanli/
  ◆ main.nx
  ▸ nexa/
    🐍 __init__.py
    📁 compiler/
    📁 ide/
  📝 README.md
  ⚙ pyproject.toml
```

### 🔍 Search (搜索)
```
[搜索框] [匹配大小写] [正则表达式]
[替换框] [替换] [全部替换]

搜索结果列表...
```
*待实现*

### ⚡ Source Control (Git)
```
当前分支: main ↑2↓0

Pull | Push | Sync

CHANGES
▾ Modified
  🟨 src/main.py
  🟨 README.md

提交信息输入框...
✓ Commit
```

## 🔄 切换面板

**点击Activity Bar图标** → **Side Panel自动显示对应内容**

```python
# 用户点击 📁 → Explorer显示
# 用户点击 ⚡ → Git面板显示
# 用户点击 🔍 → Search面板显示（待实现）
```

## 💅 样式细节

### Activity Bar 按钮
- **未激活** - 图标灰色 (#858585)，背景深灰 (#2d2d30)
- **激活** - 图标蓝色 (#4db8ff)，背景更深 (#3c3c3c)
- **悬停** - 背景变成强调色 (#0078d4)

### 按钮大小
- 宽度：50px (固定)
- 高度：50px (每个图标)
- 字体：Segoe UI, 16pt
- 内边距：12px 横向, 10px 纵向

### 分隔符
- 位置：在 Debug 和 Extensions 之间
- 样式：水平线，占满宽度
- 颜色：边框色 (#3c3c3c)
- 高度：1px，上下各8px外边距

## 🎨 实现细节

### 代码结构
```python
work_pane (horizontal PanedWindow)
├── activity_bar (fixed 50px)  ← 新增！
│   └── icon_frame
│       ├── explorer_icon_btn (📁)
│       ├── search_icon_btn (🔍)
│       ├── git_icon_btn (⚡)
│       ├── debug_icon_btn (🐛)
│       ├── separator
│       └── extensions_icon_btn (🧩)
│
├── left_panel (flexible width)
│   └── left_content (content switcher)
│       ├── explorer_panel (当 mode="explorer")
│       ├── git_panel (当 mode="source_control")
│       └── search_panel (待实现，当 mode="search")
│
├── editor_panel (weight=42)
│   └── editor (code editing area)
│
└── output_panel (weight=42)
    └── notebook (Tokens, AST, Symbols, etc.)
```

### 核心方法
```python
_build_activity_bar()              # 创建Activity Bar
_update_activity_bar_buttons()     # 更新按钮外观
_show_left_panel(mode)             # 切换Side Panel内容
```

## 📊 尺寸配置

| 组件 | 宽度 | 说明 |
|------|------|------|
| Activity Bar | 50px | 固定，不可拖动 |
| Side Panel | 可变 | 可通过拖动调整 |
| Editor | 可变 | 可通过拖动调整 |
| Output | 可变 | 可通过拖动调整 |

初始比例：
- Side Panel：16% of width
- Editor：56% of width
- Output：28% of width

## ⌨️ 快捷键

```
Ctrl+E              切换到 Explorer
Ctrl+Shift+G        切换到 Source Control
Ctrl+Shift+F        切换到 Search (待实现)
```

## 🚀 特性列表

✅ **已实现**
- Activity Bar 竖列图标栏
- Explorer 文件浏览
- Source Control Git 面板
- 打开编辑器列表
- 文件类型图标
- 右键上下文菜单
- 活动按钮视觉反馈

⏳ **待实现**
- Search 全文搜索面板
- Debug 调试器
- Extensions 扩展面板
- 拖放重排
- 自定义 Activity Bar 排序

## 🎓 用户指南

### 打开文件
1. 点击左侧 📁 (Explorer)
2. 双击文件打开

### 查看Git状态
1. 点击左侧 ⚡ (Source Control)
2. 查看修改和分支信息

### 快速切换
1. 直接点击Activity Bar图标
2. Side Panel 立即显示对应内容
3. 打开编辑器列表顶部可快速切换文件

## 📝 技术备注

- Activity Bar 使用 tk.Button（不是 ttk.Button），以支持颜色自定义
- Side Panel 通过 grid_forget/grid 切换，内存高效
- 所有图标使用 emoji，跨平台兼容
- 宽度约束使用 pack_propagate(False)

---

**布局版本**: 2.0 (VSCode-style)  
**实现完成**: 2026-05-14  
**状态**: ✅ 完整可用
