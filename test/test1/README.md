# test1 — IDE 测试沙盒

这个目录是 Nexa Studio IDE 启动后默认打开的工作区，用于测试各项 IDE 功能。

## 文件清单

| 文件 | 用途 |
|------|------|
| `main.nx`       | 主程序，import 了 math 和 utils，测试 **import 解析 / 跨文件跳转** |
| `math.nx`       | 数学函数模块（add/sub/mul/square） |
| `utils.nx`      | 通用工具（max/min/abs），用 `import as u` 别名导入 |
| `loop_demo.nx`  | 循环 / while / if 嵌套，测试 **AST / CFG 可视化** |
| `error_demo.nx` | 故意带语法错误，测试 **Problems 诊断面板 / 错误下划线** |

## 测试建议

- **Explorer**：左侧应能看到这 5 个 `.nx` 文件 + 本 README
- **打开编辑器列表**：双击多个文件后顶部 OPEN EDITORS 区会列出来
- **Source Control**：在此目录新建 / 改文件后，左侧 ⚡ 面板应显示变更
- **Search (Ctrl+Shift+F)**：试试搜 `print`，应匹配多个文件
- **F12 跳转定义**：在 main.nx 里点 `add` / `mul`，应跳到 math.nx
- **编译**：选中 main.nx 按 Ctrl+Enter，观察右侧 Tokens / AST / CFG / ASM tab
