# Nexa 语言语法规则与使用说明

本文档说明 Nexa 教学语言当前支持的语法、类型、内置函数和编译器使用方式。Nexa 是一个用于编译原理课程设计的小型语言，语法风格接近 Rust/Go，重点用于展示词法分析、语法分析、语义分析、中间代码、优化、控制流图、寄存器分配和目标代码生成等阶段。

## 1. 程序结构

一个 Nexa 源文件由若干顶层定义组成。当前支持三类顶层定义：

```text
函数定义 fn
结构体定义 struct
宏定义 macro
```

示例：

```nx
struct Pair { x: i32, y: i32 }

fn main() -> i32 {
    return 0;
}
```

程序入口约定为：

```nx
fn main() -> i32 {
    ...
}
```

使用 `--run` 运行时，编译器会执行 `main` 函数并输出返回值。

## 2. 词法规则

### 2.1 标识符

标识符由字母、数字和下划线组成，但不能以数字开头。

```nx
name
max_value
foo123
```

### 2.2 整数常量

当前整数常量支持十进制整数：

```nx
0
42
10086
```

### 2.3 字符串常量

字符串使用双引号：

```nx
"hello"
"bad"
```

支持常见转义：

```text
\n
\t
\"
\\
```

### 2.4 注释

当前支持单行注释：

```nx
// this is a comment
```

### 2.5 关键字

当前关键字包括：

```text
import fn let return if else while struct macro spawn
select recv send default true false
```

## 3. 类型系统

### 3.1 基本类型

当前内置基本类型：

```text
i32   32 位整数
f64   双精度浮点数
bool  布尔值
str   字符串
void  无返回值
```

示例：

```nx
let a: i32 = 1;
let pi: f64 = 3.14;
let ok: bool = true;
let msg: str = "hello";
```

### 3.2 数组类型

数组类型写作：

```nx
Array[i32]
Array[f64]
```

数组字面量使用方括号：

```nx
let xs: Array[i32] = [1, 2, 3];
let fs: Array[f64] = [1.5, 2.25, 3.0];
```

数组支持按下标读取和赋值，下标类型必须是 `i32`：

```nx
let x: i32 = xs[0];
xs[1] = xs[0] + xs[2];
```

数组元素类型必须一致。当前空数组 `[]` 暂时不能自动推断元素类型。

### 3.3 通道类型

当前支持教学型通道类型：

```nx
Chan[i32]
```

示例：

```nx
let ch: Chan[i32] = chan(1);
send(ch, 42);
let x: i32 = recv(ch);
```

当前内置运行时主要支持 `Chan[i32]`。

### 3.4 结构体类型

可以声明结构体：

```nx
struct Pair { x: i32, y: i32 }
```

结构体可以作为变量、参数和返回值类型使用，也支持结构体字面量、字段访问和字段赋值。

结构体构造：

```nx
let p: Pair = Pair { x: 1, y: 2 };
```

字段读取：

```nx
let a: i32 = p.x;
```

字段赋值：

```nx
p.x = p.x + 1;
```

结构体构造时需要完整初始化所有字段，字段名必须存在，字段值类型必须与结构体声明一致。

## 4. 函数定义

函数定义格式：

```nx
fn 函数名(参数列表) -> 返回类型 {
    语句列表
}
```

示例：

```nx
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}
```

如果没有显式返回类型，默认返回 `void`：

```nx
fn hello() {
    print(1);
}
```

函数调用：

```nx
let x: i32 = add(1, 2);
```

当前只支持直接函数调用，即被调用对象应为函数名。

### 4.1 文件导入

Nexa 支持第一版文件导入语法：

```nx
import "math.nx";
```

导入路径相对于当前源文件所在目录解析。被导入文件中的函数会被加入本次编译，入口文件可以直接调用：

```nx
// math.nx
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}
```

```nx
// main.nx
import "math.nx";

fn main() -> i32 {
    return add(1, 2);
}
```

为了避免多文件链接时函数名冲突，编译器会在内部给导入函数增加模块名前缀。例如 `math.nx` 中的 `add` 会变成 Nexa 内部函数名 `math__add`，最终汇编符号为 `nx_math__add`。入口函数 `main` 保持为运行时入口。

当前导入系统仍是第一版：

```text
支持 import "file.nx";
导入函数直接暴露给入口文件调用
入口文件中的同名函数优先
暂不提供完整模块命名空间、包版本、依赖解析和循环导入处理
```

## 5. 泛型函数

Nexa 支持教学型泛型函数：

```nx
fn max[T: Ord](a: T, b: T) -> T {
    if a > b { return a; }
    return b;
}
```

调用时由参数类型推断泛型实参：

```nx
let x: i32 = max(10, 20);
```

当前支持的泛型约束主要用于课程展示，例如 `Ord`。语义检查中，`i32`、`bool`、`str` 可满足 `Ord` 约束。

## 6. 变量声明与赋值

### 6.1 变量声明

变量声明格式：

```nx
let 变量名: 类型 = 表达式;
```

示例：

```nx
let a: i32 = 1;
let b: bool = a > 0;
```

类型标注可以省略，此时由初始值推断：

```nx
let a = 1;
```

如果既没有类型标注，也没有初始值，会产生语义错误：

```nx
let a; // 错误：缺少类型信息
```

### 6.2 赋值语句

赋值格式：

```nx
变量名 = 表达式;
```

示例：

```nx
let x: i32 = 1;
x = x + 1;
```

当前赋值左侧应为简单变量名。

## 7. 语句

### 7.1 返回语句

```nx
return 表达式;
return;
```

示例：

```nx
fn main() -> i32 {
    return 0;
}
```

返回表达式类型必须与函数声明的返回类型一致。

### 7.2 表达式语句

函数调用、宏调用等可以作为表达式语句：

```nx
print(1);
panic("bad");
```

### 7.3 块语句

块由 `{}` 包围：

```nx
{
    let x: i32 = 1;
    print(x);
}
```

块会形成新的作用域。

### 7.4 if 语句

格式：

```nx
if 条件 {
    ...
}
```

或：

```nx
if 条件 {
    ...
} else {
    ...
}
```

示例：

```nx
if a > b {
    return a;
} else {
    return b;
}
```

`if` 条件必须为 `bool` 类型。

### 7.5 while 语句

格式：

```nx
while 条件 {
    ...
}
```

示例：

```nx
fn sum(n: i32) -> i32 {
    let i: i32 = 0;
    let s: i32 = 0;
    while i < n {
        s = s + i;
        i = i + 1;
    }
    return s;
}
```

`while` 条件必须为 `bool` 类型。

### 7.6 spawn 语句

语法上支持：

```nx
spawn 表达式;
```

该功能属于扩展展示特性。当前后端和运行路径对并发执行支持有限，课程演示中建议优先使用 `chan`、`send`、`recv`、`select` 的教学子集。

## 8. 表达式

### 8.1 字面量

```nx
1
true
false
"hello"
```

### 8.2 变量引用

```nx
a
result
```

### 8.3 一元表达式

```nx
-a
!ok
```

规则：

```text
-  作用于 i32，结果为 i32
!  作用于 bool，结果为 bool
```

### 8.4 二元表达式

算术运算：

```nx
a + b
a - b
a * b
a / b
a % b
```

比较运算：

```nx
a == b
a != b
a < b
a <= b
a > b
a >= b
```

逻辑运算：

```nx
a && b
a || b
```

运算优先级从低到高：

```text
||
&&
== !=
< <= > >=
+ -
* / %
一元 ! -
函数调用
```

### 8.5 括号表达式

```nx
(a + b) * c
```

### 8.6 块表达式

块也可以作为表达式使用，最后一个表达式语句作为块的值：

```nx
let x: i32 = {
    let a: i32 = 1;
    a + 2;
};
```

注意最后的 `a + 2;` 是表达式语句，它的类型作为块表达式类型。

## 9. 宏

宏定义格式：

```nx
macro 宏名(参数列表) {
    语句列表
}
```

示例：

```nx
macro unless(cond, body) {
    if !cond { body; }
}
```

宏调用示例：

```nx
unless(ans == 42, { panic("bad"); });
```

宏属于 AST 级展开。宏参数可以是表达式，也可以传入块表达式。宏展开时会对宏内部声明的局部变量做简单重命名，减少变量名冲突。

宏只在 `full` 模式下启用：

```bash
python nexa_cli.py example.nx --mode full
```

在 `core` 模式下，宏展开关闭。

## 10. select 表达式

Nexa 支持教学型 `select` 表达式，用于展示通道相关控制流。

当前支持两种子集：

```nx
select {
    recv(ch) => { 42; }
    default => { 0; }
}
```

或：

```nx
select {
    send(ch, 1) => { 1; }
    default => { 0; }
}
```

限制：

```text
必须且只能有一个 default 分支
只支持一个 recv 分支加 default，或一个 send 分支加 default
当前主要面向 i32 通道教学演示
```

完整示例：

```nx
fn main() -> i32 {
    let ch: Chan[i32] = chan(1);
    send(ch, 42);
    let ans: i32 = select {
        recv(ch) => { 42; }
        default => { 0; }
    };
    return ans;
}
```

## 11. 内置函数

当前语义检查器预置以下内置函数：

```text
print(value) -> void      // 支持 i32、f64、bool、str
panic(str) -> void
read_i32() -> i32
read_f64() -> f64
len(Array[T]) -> i32
chan(i32) -> Chan[i32]
send(Chan[i32], i32) -> void
recv(Chan[i32]) -> i32
```

示例：

```nx
print(123);
print("hello");
panic("bad");

let a: i32 = read_i32();
let b: f64 = read_f64();
let xs: Array[i32] = [1, 2, 3];
let n: i32 = len(xs);

let ch: Chan[i32] = chan(1);
send(ch, 42);
let x: i32 = recv(ch);
```

`read_i32` 和 `read_f64` 是简化输入函数，每次从标准输入读取一个对应类型的值。它们不是 C 语言 `scanf` 那样的格式化输入接口。

## 12. 完整示例

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

## 13. 编译器使用

### 13.1 查看帮助

```bash
python nexa_cli.py --help
```

### 13.2 编译并运行

```bash
python nexa_cli.py example.nx --run
```

当前运行路径使用 HIR 虚拟机执行优化后的中间代码，不依赖汇编器和链接器。

### 13.3 输出词法结果

```bash
python nexa_cli.py example.nx --dump tokens
python nexa_cli.py example.nx --dump tables
```

可查看：

```text
Token 序列
关键字表
界符表
标识符表
常量表
符号表
四元式表
```

### 13.4 输出 AST

```bash
python nexa_cli.py example.nx --dump ast
```

### 13.5 输出 HIR

```bash
python nexa_cli.py example.nx --dump hir
```

会输出：

```text
优化前 HIR
优化后 HIR
```

HIR 可作为课程设计中的四元式或三地址码展示。

### 13.6 输出 CFG

```bash
python nexa_cli.py example.nx --dump cfg
```

### 13.7 输出教学型汇编

```bash
python nexa_cli.py example.nx --dump asm
```

当前汇编是 Win64 x86-64 Intel 语法文本。只使用 `--dump asm` 时会把汇编作为阶段产物输出；如果需要真正生成 `.exe`，使用 `--build`，编译器会调用 GCC/MinGW64 完成汇编、链接并生成本机可执行文件。

```bash
python nexa_cli.py example.nx --mode full --build
python nexa_cli.py example.nx --mode full --build --run-exe
```

### 13.8 输出 LLVM IR

```bash
python nexa_cli.py example.nx --emit-llvm
```

### 13.9 导出 AST/CFG 图

```bash
python nexa_cli.py example.nx --export-dir out
```

会生成类似：

```text
out/ast.dot
out/cfg_main.dot
```

如果安装了 Graphviz Python 包和相关工具，还会尝试生成 SVG。

### 13.10 生成 HTML 报告

```bash
python nexa_cli.py example.nx --mode full --dump all --run --trace --export-dir out --report out/report.html
```

报告中包含词法表、符号表、四元式、CFG、运行结果、诊断信息等内容，适合课程设计答辩展示。

## 14. core 模式与 full 模式

### core 模式

```bash
python nexa_cli.py example.nx --mode core
```

适合展示基础编译流程：

```text
变量
表达式
if/while
函数
符号表
HIR
CFG
教学型 ASM
```

### full 模式

```bash
python nexa_cli.py example.nx --mode full
```

在基础功能上启用扩展特性：

```text
宏展开
泛型单态化
select/channel 教学运行时
更完整的课程展示报告
```

默认模式为 `full`。

## 15. 当前限制

当前 Nexa 是课程设计语言，不是完整工业语言。主要限制包括：

```text
当前 import 是第一版功能，暂不支持完整模块命名空间、包版本和依赖解析
没有完整的堆对象生命周期管理，数组和结构体主要依赖简单运行时模型
没有格式化 scanf 接口，只提供 read_i32() 和 read_f64()
channel/select 是教学子集
spawn 并发执行支持有限
LLVM IR 后端不是所有扩展特性都适合直接生成本机程序
```

这些限制不影响其作为编译原理课程设计展示完整编译流程。
