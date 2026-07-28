# Code2Copyright

一个本地运行的软著源代码文档生成器。选择项目目录后，工具会自动扫描、
排序和编号源码，并生成符合常见软件著作权材料整理习惯的 Word 文档。

整个处理过程在本机完成，不会将源码上传到第三方服务。

## 功能特性

- 浏览器图形界面，无需手动复制、粘贴源码
- 每页固定 50 行，全项目使用连续行号
- 支持导出全部源码，或自动截取前 30 页和后 30 页
- 源码不足 60 页时自动导出全部内容
- 可调整 `backend`、`front`、`opensource` 等顶层模块的拼接顺序
- 自动生成带软件名称的页眉、页码和文件分隔标记
- 自动忽略依赖、构建产物、版本控制目录和压缩代码
- 生成标准 `.docx` 文件，可使用 Microsoft Word、WPS Office 或
  LibreOffice 打开
- 核心功能仅使用 Python 标准库，无第三方运行时依赖

## 环境要求

- Python 3.9 或更高版本
- Chrome、Edge 或其他支持目录选择功能的现代浏览器

## 快速开始

克隆项目：

```bash
git clone https://github.com/<your-name>/Code2Copyright.git
cd Code2Copyright
```

启动应用：

```bash
python3 app.py
```

应用会尝试自动打开浏览器。如果浏览器没有自动启动，请手动访问：

```text
http://127.0.0.1:8765/
```

停止应用时，在终端按 `Control+C`。

## 使用方法

1. 填写软件名称，例如“智能数据管理系统 V1.0”。
2. 选择需要整理的源码项目根目录。
3. 使用“上移”和“下移”调整顶层模块的拼接顺序。
4. 选择“前 30 页＋后 30 页”或“全部源码”。
5. 点击“导出 Word 文档”。

模块列表越靠上，其源码越靠近文档开头。例如模块顺序为
`backend → front → opensource` 时，源码会按该顺序拼接。前后 30 页模式
截取的是拼接后源码的前 1500 行和后 1500 行，并不保证每个模块恰好占
30 页。

## 支持的文件

当前支持：

- Python：`.py`、`.pyw`
- Java/JVM：`.java`、`.kt`、`.kts`、`.scala`、`.gradle`
- Web：`.vue`、`.js`、`.jsx`、`.ts`、`.tsx`、`.html`、`.css`、
  `.scss`、`.less`
- C/C++：`.c`、`.h`、`.cc`、`.cpp`、`.cxx`、`.hpp`、`.hh`
- 其他：Go、SQL、PHP、C#、Rust、Ruby、Swift、Shell、YAML、XML、
  JSON 和 properties

工具会忽略 `.git`、`node_modules`、`venv`、`build`、`dist`、`target`
等目录，以及压缩后的 JavaScript/CSS、source map 和依赖锁文件。

## 文档生成规则

- 每个源码文件前插入一行文件路径标记
- 文件路径标记和源码内容统一参与连续编号
- 每页固定排列 50 行，不足部分留空
- “前 30 页＋后 30 页”模式最多输出 3000 行
- 项目总行数不超过 3000 行时输出全部源码
- 同一模块内按照相对文件路径排序

## 运行测试

```bash
python3 -m unittest -v
```

## 项目结构

```text
Code2Copyright/
├── app.py             # 本地 Web 服务与操作界面
├── generator.py       # 源码扫描、排序、分页与 DOCX 生成
├── test_generator.py  # 自动化测试
└── README.md
```

## 隐私说明

服务仅监听本机地址 `127.0.0.1`。浏览器选择的源码会发送给本机 Python
进程用于生成文档，生成期间使用的临时文件会在请求结束后自动清理。
