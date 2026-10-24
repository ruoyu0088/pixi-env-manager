# Pixi 环境管理器

一个用 **Python 标准库 + Tkinter** 编写的 Pixi 工作区管理 GUI。无需安装第三方
Python 包，任何带有 Tk 8.6 的 Python 3.9+ 环境都可以直接运行。

## 功能

- **打开 Pixi 环境**：选择 `pixi.toml`、`pyproject.toml` 或工作区目录。
- **最近打开**：顶部环境管理条记录工作区 + 环境名，下次启动自动恢复最近环境。
- **环境切换**：识别工作区中的所有命名环境，在顶部下拉框切换。
- **新建工作区**：可以从空目录直接创建新的 `pixi.toml` 工作区；支持指定频道和平台，
  创建后自动进入基础依赖视图。
- **基础依赖视图**：顶部还可以选择“基础依赖”（default feature），只列出
  `[dependencies]` / `[pypi-dependencies]` 中的共享依赖；默认环境视图则显示完整环境，
  并在“作用域”列标出基础、feature、环境专属和传递依赖。
- **环境管理**：顶部“环境管理”菜单可以添加/删除命名环境；添加时可选择 features、
  solve group，并默认勾选安装；删除时可选择同时清理 `.pixi` 环境目录。
- **库列表**：
  - 仅用户安装（`is_explicit = true` 的显式依赖）
  - 全部已安装包（含传递依赖）
  - 按名称搜索、按类型/状态过滤、按列排序
  - 显示已安装版本、最新版本、更新状态、请求约束、来源、大小
  - 详情面板显示关键字段；“完整详情”对话框显示依赖、约束、URL 等全部信息
- **版本检查**：
  - 选中包后查询 conda / PyPI 最新版本
  - conda 查询同时合并所选平台与 `noarch` 记录，避免纯 Python 包误报旧版本
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
- **多任务输出**：
  - Task 和 Python 程序可以同时运行多个
  - 下方每个任务一个输出标签页，各自带停止、复制、清空、关闭按钮
  - 完成/失败/停止的标签页保留，手动关闭或“关闭已完成”
  - 会修改环境/清单的 pixi 命令同一时间只允许运行一个
- **主题**：浅色 / 深色切换。
- **语言**：中文 / English / 日本語，在设置中切换，重启后生效。
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
- `打开环境`：
  - 选择已有 `pixi.toml` / `pyproject.toml` 或工作区目录直接打开
  - 选择没有清单的空目录或输入不存在的目录时，会提示创建新 Pixi 工作区
  - `新建工作区…` 按钮可以直接打开创建向导
  - 新建向导只创建 `pixi.toml`，支持多个频道和平台；工作区名称由目录名决定
  - 创建过程在输出标签页中显示，成功后自动打开并进入基础依赖视图
- `环境` 下拉框：切换命名环境；切换后左侧任务和 Python 历史会同步过滤。
  - `基础依赖`：只显示共享的基础依赖，`add` / `remove` 不带 `--environment`，
    作用于所有环境；Task/Python 仍使用 default 环境运行。
  - `default` / `test`：显示该环境的完整库列表；`add` / `remove` 带
    `--environment`，只影响该环境。default 视图下添加的是
    `[environments.default.dependencies]` 专属依赖，其他环境看不到；要添加共享依赖
    请切换到“基础依赖”。
  - 基础依赖模式按工作区持久化，重新打开同一工作区时恢复。
- `环境管理` 菜单：
  - `添加环境…`：输入名称、选择 features、可选 solve group；默认勾选“创建后立即安装”
  - `删除当前环境…`：`default` 不能删除；可选同时清理已安装的 `.pixi` 环境目录
  - 添加/删除都会保留 `pixi.toml` 原有注释；删除只移除清单定义，不自动改 lock
- `刷新`：重新读取环境、包列表和 task。
- `设置`：Pixi 路径、终端程序、界面语言、主题、控制台最大行数、清空历史。
  - 终端留空时使用 PowerShell
  - 可填 `powershell.exe`、`pwsh.exe`、`cmd.exe`、`wt.exe` 或完整路径
  - 也支持模板，例如 `wt.exe -d "{cwd}" powershell.exe -NoExit -Command {command}`

### 左侧快速启动

- **快速任务**：当前环境的 task，点击 `▶` 在输出栏运行，点击 `>_` 在独立终端运行；
  右键可带参数或在终端运行。
- **Python 程序**：只显示用当前工作区 + 当前环境运行过的脚本。点击 `▶` 用保存的
  参数在输出栏运行，点击 `>_` 在独立终端运行；单击条目会把脚本、参数、工作目录
  加载到 Python 页，方便修改。

每个“环境 + 脚本路径”保留最近一次参数。修改参数后再次运行会覆盖保存的参数。

### 库列表

“仅用户安装”是清单中显式声明的 conda / PyPI 依赖，不是所有曾经安装过的包。
传递依赖只在“全部库”中显示。

“检查兼容更新”不会修改任何文件。单包“查询最新版本”会：

- conda 包：调用 `pixi search <包名> --json`，合并当前平台和 `noarch` 的结果
- PyPI 包：访问 `https://pypi.org/pypi/<包名>/json`

如果 PyPI 包来自自定义索引，GUI 会提示无法通过公共 API 检查，而不会伪造结果。

### 多任务与输出

Task 和 Python 程序可以连续启动多个，不会因为已有任务运行而被阻塞。底部输出区
会为每个任务创建独立标签页：

- 每个标签页有自己的“停止”按钮，只终止该任务及其子进程树
- 任务完成后，标签页保留输出，可手动关闭
- “全部停止”用于一次性停止所有 GUI 任务
- 修改环境/清单的 pixi 命令（add、install、update、clean 等）会串行执行，避免
  同时写 lock 文件或环境目录

### 界面语言

在“设置 → 界面语言”中选择中文、English 或 日本語，保存后重启程序生效。
Pixi 自身的 `--help` 和命令输出保持原语言；少量较不常用的提示在日文模式下会
回退为英文。

### 布局与快捷键

- 侧面栏和下方输出栏的宽高会在关闭时保存，下次启动恢复。
- `Ctrl+B` 折叠/展开侧面栏。
- `Ctrl+J` 折叠/展开下方输出栏。
- 折叠状态也会保存；再次展开时恢复折叠前的尺寸。

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

测试覆盖版本比较、状态持久化、TOML 高亮、Pixi JSON 解析（含 noarch 合并）、
Windows 参数拆分、国际化模板和多任务命令分类。GUI 本身使用标准 Tkinter，
不做无显示器的单元测试。

## 项目结构

```
pixi-env-manager/
  pixi_env_manager.py      入口
  start.bat                双击启动
  app/
    state.py                设置、环境历史、Python 运行历史
    i18n.py                 中文/英文/日文翻译层
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
- 切换界面语言需要重启程序；正在运行的输出标签不会跨重启保留。
- 日文界面中少量不常用提示会回退英文，Pixi CLI 原始输出不翻译。
- 删除环境时“同时清理目录”会先执行 `pixi clean`，再删除清单定义；如果后续删除
  定义失败，目录可能已经被清理。添加/删除环境不会自动更新 lock，之后请按提示
  lock/install。
- 基础依赖模式只显示 `[dependencies]` / `[pypi-dependencies]` 中直接声明的包，
  不显示传递依赖；要看完整 default 环境请切换到 default。
- 删除基础依赖会提示“所有环境受影响”；从 default/test 视图删除基础依赖时，
  GUI 会改为不带 `--environment` 的基础依赖删除命令。
- 命令中心的 Environment 选项与顶部选择同步；在基础依赖模式下，add/remove
  的 Environment 固定为“不指定”，其他命令仍使用 default。
- 新建工作区只支持 `pixi.toml`。已有 `pyproject.toml` 的目录不会用新建向导覆盖；
  已有 Pixi 清单时请直接打开。
- `pixi init` 会追加 `.gitignore`、`.gitattributes` 和 `pixi.toml`，不会删除目录中
  已有文件；非空目录会先提示确认。
