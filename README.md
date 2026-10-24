# Pixi 环境管理器

一个用 **Python 标准库 + Tkinter** 编写的 Pixi 工作区管理 GUI。无需安装第三方
Python 包，任何带有 Tk 8.6 的 Python 3.9+ 环境都可以直接运行。

## 功能

- **打开 Pixi 环境**：选择 `pixi.toml`、`pyproject.toml` 或工作区目录。
- **最近打开**：顶部环境管理条记录工作区 + 环境名，下次启动自动恢复最近环境。
- **环境切换**：识别工作区中的所有命名环境，在顶部下拉框切换。
- **库列表**：
  - 仅用户安装（`is_explicit = true` 的显式依赖）
  - 全部已安装包（含传递依赖）
  - 按名称搜索、按类型/状态过滤、按列排序
  - 显示已安装版本、最新版本、更新状态、请求约束、来源、大小
  - 详情面板显示关键字段；“完整详情”对话框显示依赖、约束、URL 等全部信息
- **版本检查**：
  - 选中包后查询 conda / PyPI 最新版本
  - 一键检查当前版本约束内的兼容更新（`pixi update --dry-run --json`，不修改文件）
  - 右键可更新到兼容版本或升级到最新版本
- **`pixi.toml` 编辑器**：
  - 行号、当前行高亮、TOML 语法高亮（自实现，零依赖）
  - 保存、撤销/重做、查找、重新加载
  - 未保存提示、外部修改检测、原子写入
  - 保存后用 `tomllib` 检查语法；刷新工作区信息
- **Task 快速启动**：
  - 左侧“快速任务”列表，一键启动
  - 带参数启动、在独立终端运行
  - 完整 Task 页面显示命令、目录、feature、依赖
- **Python 程序运行**：
  - 文件对话框选择或直接输入绝对路径
  - 在选中 Pixi 环境中运行
  - 支持参数和工作目录
  - 左侧按“工作区 + 环境”记录最近运行的程序和参数，一键重复运行
- **命令中心**：
  - `add`、`remove`、`update`、`upgrade`、`search`、`install`、`lock`、
    `clean`、`reinstall`、`run`、`task add`、`task remove`、`info`、`shell`、`init`
  - 每个命令有中文说明、参数表单、实时命令预览和完整 `--help`
  - 手动命令输入栏
- **输出控制台**：实时 stdout/stderr、退出码、耗时、停止进程树、复制/清空。
- **主题**：浅色 / 深色切换。
- **历史与设置**：保存在 `%APPDATA%\PixiEnvManager\state.json`。

## 运行

### 双击启动

双击项目根目录的 `start.bat`。

启动脚本会依次尝试：

1. 环境变量 `PIXI_ENV_MANAGER_PYTHON` 指定的 `pythonw.exe`
2. 本机默认 Pixi 环境 `C:\pixi_env\.pixi\envs\default\pythonw.exe`
3. `%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe`
4. `C:\Python3*\pythonw.exe`
5. PATH 上的 `pythonw`

如果都没有，会提示安装 Python 或设置环境变量。启动脚本会先验证候选解释器
能导入 Tkinter，避免 Windows Python Launcher 指向失效环境时静默失败。

### 命令行启动

```powershell
py -3 .\pixi_env_manager.py
# 或者直接打开某个工作区
py -3 .\pixi_env_manager.py C:\pixi_env\pixi.toml
```

也可以使用任意 Python 3.9+：

```powershell
C:\some\python.exe .\pixi_env_manager.py
```

## 使用说明

### 顶部环境管理条

- `打开环境`：选择清单文件或工作区目录。
- `最近打开`：历史工作区 + 环境，点击直接切换。
- 当前工作区名称 / 路径：点击路径可复制。
- `环境` 下拉框：切换命名环境；切换后左侧任务和 Python 历史会同步过滤。
- `刷新`：重新读取环境、包列表和 task。
- `设置`：Pixi 路径、主题、控制台最大行数、清空历史。

### 左侧快速启动

- **快速任务**：当前环境的 task，点击 `▶` 直接运行；右键可带参数或在终端运行。
- **Python 程序**：只显示用当前工作区 + 当前环境运行过的脚本。点击 `▶` 用保存的
  参数运行；单击条目会把脚本、参数、工作目录加载到 Python 页，方便修改。

每个“环境 + 脚本路径”保留最近一次参数。修改参数后再次运行会覆盖保存的参数。

### 库列表

“仅用户安装”是清单中显式声明的 conda / PyPI 依赖，不是所有曾经安装过的包。
传递依赖只在“全部库”中显示。

“检查兼容更新”不会修改任何文件。单包“查询最新版本”会：

- conda 包：调用 `pixi search <包名> --json`
- PyPI 包：访问 `https://pypi.org/pypi/<包名>/json`

如果 PyPI 包来自自定义索引，GUI 会提示无法通过公共 API 检查，而不会伪造结果。

### 编辑器

- `Ctrl+S` 保存，`Ctrl+F` 查找，`Ctrl+R` 重新加载。
- 保存前会用标准库 `tomllib` 检查语法（Python 3.11+）。有语法错误时会询问是否
  仍然保存，避免打断编辑。
- 保存采用临时文件 + `os.replace` 的原子写入方式。
- 同一文件被外部程序修改时，保存前会提示覆盖风险。

### 命令中心

表单只覆盖常用参数；高级参数可以使用下方的手动命令，或者参考右侧完整 `--help`。

手动命令：

- 输入 `add numpy` 或完整 `pixi add numpy`
- 自动附加当前工作区的 `--manifest-path`（可取消勾选）
- 按参数直接执行，不经过 shell；管道/重定向请使用独立终端

## 环境要求

- Windows 10/11
- Python 3.9+（需要 Tkinter；Windows 官方安装包默认包含）
- Pixi 0.82+（其他较新版本通常也可以；JSON 字段变化时会给出错误提示）
- 不需要 `pip install` 任何包

## 测试

```powershell
C:\pixi_env\.pixi\envs\default\python.exe -m unittest discover -s tests -v
```

测试覆盖版本比较、状态持久化、TOML 高亮、Pixi JSON 解析和 Windows 参数拆分。
GUI 本身使用标准 Tkinter，不做无显示器的单元测试。

## 项目结构

```
pixi-env-manager/
  pixi_env_manager.py      入口
  start.bat                双击启动
  app/
    state.py                设置、环境历史、Python 运行历史
    pixi.py                 Pixi CLI 封装
    models.py               数据模型
    jobs.py                 后台命令、输出流、停止进程树
    versions.py             版本比较
    toml_highlight.py       TOML 词法高亮
    util.py                 参数拆分、路径显示等
    ui/
      main_window.py        主窗口和集成逻辑
      sidebar.py            左侧快速任务/Python 历史
      overview_tab.py
      libraries_tab.py
      tasks_tab.py
      python_tab.py
      commands_tab.py
      editor_tab.py
      console_panel.py
      dialogs.py
      theme.py
      widgets.py
  tests/
```

## 已知限制

- 版本比较实现了常见 PEP 440 / conda 规则，但极端版本字符串可能只能做自然排序。
  此时界面仍会显示原始最新版本，不会隐藏数据。
- 只有 `pypi.org` 的 PyPI 包能自动查最新版本；私有索引会提示不支持。
- 交互式 task（例如 Jupyter Lab）建议使用“在终端中运行”，GUI 控制台适合构建类任务。
- 关闭窗口会终止 GUI 启动的子进程树；在独立终端中启动的程序不受影响。
