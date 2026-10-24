"""Small runtime translation layer for Tkinter applications.

Chinese is the source language used by the existing UI code.  A language change
is persisted and applied on the next start, so the UI can be translated after it
has been constructed.  This keeps widget-building code simple and still covers
dynamic labels/status strings through a template-aware translator.
"""

from __future__ import annotations

import re
import string
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Iterable, List, Optional, Tuple

LANGUAGES: Dict[str, str] = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
}

_CURRENT = "zh"


EN: Dict[str, str] = {
    "Pixi 环境管理器": "Pixi Environment Manager",
    "Pixi 环境管理器 - {} [{}]": "Pixi Environment Manager - {} [{}]",
    "打开环境": "Open Environment",
    "最近打开  ▾": "Recent  ▾",
    "最近打开": "Recent",
    "环境": "Environment",
    "基础依赖": "Base dependencies",
    "基础": "Base",
    "作用域": "Scope",
    "说明": "Notes",
    "兼容更新": "Compatible update",
    "传递": "Transitive",
    "未安装": "Not installed",
    "环境:{}": "Environment: {}",
    "feature:{}": "feature: {}",
    "基础依赖 ({})": "Base dependencies ({})",
    "基础依赖 {} 个 · 所有环境共享": "{} base dependencies · shared by all environments",
    "基础依赖视图（所有环境共享） · Task/Python 使用 {} 环境": "Base-dependency view (shared) · Task/Python run in {}",
    "基础依赖视图：任务仍使用 {} 环境运行": "Base-dependency view: tasks still run in {}",
    "当前环境没有可显示的 task": "No tasks to display in this environment.",
    "基础依赖模式：此命令作用于所有环境。": "Base-dependency mode: this command affects all environments.",
    "基础依赖视图：Python 仍使用 {} 环境运行": "Base-dependency view: Python still runs in {}",
    "当前环境: default · add/remove 仅影响 default；共享依赖请切换到基础依赖": "Current environment: default · add/remove affects only default; switch to Base dependencies for shared dependencies",
    "删除作用域冲突": "Remove scope conflict",
    "删除基础依赖": "Remove base dependency",
    "同一命令不能同时删除基础依赖和环境专属依赖。": "A single command cannot remove both base and environment-only dependencies.",
    "基础依赖：{}": "Base dependencies: {}",
    "其他依赖：{}": "Other dependencies: {}",
    "该包不在基础依赖中：{}": "These packages are not base dependencies: {}",
    "{} 属于基础依赖，删除后所有环境都会受影响。\n\n是否从基础依赖中删除？": "{} is a base dependency. Removing it affects all environments.\n\nRemove it from the base dependencies?",
    "环境管理  ▾": "Environments  ▾",
    "新建 Pixi 工作区": "New Pixi Workspace",
    "新建工作区…": "New Workspace…",
    "新建工作区 {}": "Create workspace {}",
    "只会创建 pixi.toml；不安装依赖，创建后进入基础依赖视图。": "Creates only pixi.toml; dependencies are not installed. The workspace opens in the Base dependencies view.",
    "目录": "Directory",
    "选择目录…": "Choose Directory…",
    "工作区名称": "Workspace name",
    "频道": "Channels",
    "多个频道用逗号分隔，例如 conda-forge,bioconda。": "Separate multiple channels with commas, e.g. conda-forge,bioconda.",
    "平台": "Platforms",
    "至少选择一个平台；默认使用当前系统平台。": "Select at least one platform; the current platform is selected by default.",
    "Pixi 会同时创建 .gitignore 和 .gitattributes；工作区名称由目录名决定。": "Pixi also creates .gitignore and .gitattributes; the workspace name comes from the directory name.",
    "请选择一个目录。": "Choose a directory.",
    "目标路径已存在且不是目录。": "The target path exists and is not a directory.",
    "目录中已有 Pixi 清单，请直接打开。": "This directory already has a Pixi manifest; open it directly.",
    "目录中已有 pyproject.toml；新建向导只创建 pixi.toml。": "This directory already has pyproject.toml; the new-workspace wizard only creates pixi.toml.",
    "目录非空，创建时会追加 pixi.toml、.gitignore、.gitattributes。": "The directory is not empty; pixi.toml, .gitignore and .gitattributes will be added.",
    "目录为空，将创建 pixi.toml。": "The directory is empty; pixi.toml will be created.",
    "目录不存在，创建时会自动建立。": "The directory does not exist and will be created.",
    "请选择或输入工作区目录。": "Choose or enter a workspace directory.",
    "已有 Pixi 清单": "Pixi manifest already exists",
    "该目录已有 Pixi 清单，请直接打开。": "This directory already has a Pixi manifest; open it directly.",
    "已有 pyproject.toml": "pyproject.toml already exists",
    "新建向导只创建 pixi.toml。该目录已有 pyproject.toml，请换一个目录或直接打开现有清单。": "The new-workspace wizard only creates pixi.toml. This directory already has pyproject.toml; choose another directory or open the existing manifest.",
    "目录无效": "Invalid directory",
    "不能直接在磁盘根目录创建工作区。": "A workspace cannot be created directly in a disk root.",
    "频道为空": "No channels",
    "至少填写一个频道。": "Enter at least one channel.",
    "平台为空": "No platforms",
    "至少选择一个平台。": "Select at least one platform.",
    "目录非空": "Directory is not empty",
    "目录中已有文件。Pixi 会追加 .gitignore、.gitattributes 和 pixi.toml，但不会删除已有文件。\n\n继续创建吗？": "The directory already contains files. Pixi will add .gitignore, .gitattributes and pixi.toml without deleting existing files.\n\nContinue?",
    "没有 Pixi 清单": "No Pixi manifest",
    "该目录下没有 pixi.toml 或 pyproject.toml。\n\n是否创建新的 Pixi 工作区？": "This directory has no pixi.toml or pyproject.toml.\n\nCreate a new Pixi workspace?",
    "目录不存在": "Directory does not exist",
    "目录不存在：\n{}\n\n是否创建该目录并初始化 Pixi 工作区？": "The directory does not exist:\n{}\n\nCreate it and initialize a Pixi workspace?",
    "请先停止所有运行中的任务并等待刷新完成，再新建工作区。": "Stop all running tasks and wait for refresh before creating a workspace.",
    "请先保存或放弃当前清单的修改，再新建工作区。": "Save or discard changes to the current manifest before creating a workspace.",
    "正在创建 {}": "Creating {}",
    "初始化结束，但没有找到 {}": "Initialization finished, but {} was not found",
    "添加环境": "Add Environment",
    "添加环境…": "Add Environment…",
    "添加环境 {}": "Add environment {}",
    "删除环境": "Delete Environment",
    "删除环境 {}": "Delete environment {}",
    "删除当前环境…": "Delete Current Environment…",
    "当前环境不能删除": "Cannot delete the current environment",
    "default 是隐式环境，不能删除。": "default is implicit and cannot be deleted.",
    "请先保存或放弃 pixi.toml 的未保存修改，再管理环境。": "Save or discard changes to pixi.toml before managing environments.",
    "请先停止所有运行中的任务，再删除环境。": "Stop all running tasks before deleting an environment.",
    "请先停止所有运行中的任务并等待刷新完成，再添加环境。": "Stop all running tasks and wait for refresh before adding an environment.",
    "环境名称": "Environment name",

    "名称不能重复，default 是隐式环境，不能作为新名称。": "Names must be unique; default is implicit and cannot be used.",
    "包含 default feature": "Include default feature",
    "工作区没有其他 feature。": "This workspace has no other features.",
    "取消 default feature 时，必须至少选择一个其他 feature。": "When default is disabled, at least one other feature must be selected.",
    "Solve group（可选）": "Solve group (optional)",
    "创建后立即安装环境": "Install the environment after creation",
    "环境已存在": "Environment already exists",
    "环境“{}”已经存在。": "Environment “{}” already exists.",
    "环境名称不能包含空格、单引号或双引号。": "The environment name cannot contain spaces, single quotes or double quotes.",
    "请输入环境名称。": "Enter an environment name.",
    "default 是隐式环境，不能作为新环境名称。": "default is implicit and cannot be used as a new environment name.",
    "从清单中删除环境“{}”？": "Delete environment “{}” from the manifest?",
    "这会修改 pixi.toml / pyproject.toml，但不会自动更新 lock 文件。": "This modifies pixi.toml / pyproject.toml but does not update the lock file automatically.",
    "同时清理已安装的环境目录（pixi clean）": "Also clean the installed environment directory (pixi clean)",
    "该环境当前没有已安装的 .pixi 环境目录。": "This environment has no installed .pixi directory.",
    "刷新": "Refresh",
    "设置": "Settings",
    "设置已保存": "Settings saved",
    "设置无效": "Invalid settings",
    "语言": "Language",
    "语言设置已保存，重启程序后生效。": "Language saved. Restart the application to apply it.",
    "就绪": "Ready",
    "空闲": "Idle",
    "运行中": "Running",
    "运行中 {} 个": "{} running",
    "运行中 {} 个任务": "{} running",
    "完成": "Completed",
    "已停止": "Stopped",
    "失败（退出码 {}）": "Failed (exit code {})",
    "用时 {:.1f}s": "{:.1f}s",
    "[完成] 用时 {:.1f}s\n": "[done] {:.1f}s\n",
    "[失败] 退出码 {}，用时 {:.1f}s\n": "[failed] exit code {}, {:.1f}s\n",
    "[已停止] 用时 {:.1f}s\n": "[stopped] {:.1f}s\n",
    "[错误] ": "[error] ",
    "已保存": "Saved",
    "未保存": "Unsaved",
    "已保存（语法错误）": "Saved (syntax error)",
    "未打开文件": "No file",
    "未打开环境": "No environment",
    "未检查": "Not checked",
    "查询中…": "Checking…",
    "查询失败": "Check failed",
    "已是最新": "Up to date",
    "有更新": "Update available",
    "已安装更高": "Installed is newer",
    "可兼容更新": "Compatible update",
    "查询最新版本": "Check Latest Version",
    "查询选中最新": "Check Selected Latest",
    "查询此包最新版": "Check This Package",
    "检查兼容更新": "Check Compatible Updates",
    "检查更新": "Check for Updates",
    "检查兼容更新失败": "Compatible update check failed",
    "最新版本查询完成": "Latest-version check finished",
    "最新版本查询失败: ": "Latest-version check failed: ",
    "发现 {} 个兼容更新": "{} compatible updates found",
    "发现 {} 个包存在兼容范围内的更新": "{} packages have compatible updates",
    "兼容更新检查完成：{} 个更新": "Compatible update check finished: {} update(s)",
    "兼容范围内没有可更新的包": "No compatible updates",
    "兼容范围内没有可更新的包（或环境没有锁文件）": "No compatible updates (or no lock file)",
    "正在检查兼容更新…": "Checking compatible updates…",
    "正在检查兼容范围内的更新…": "Checking for compatible updates…",
    "正在查询 {} 个包的最新版本…": "Checking the latest version of {} package(s)…",
    "概览": "Overview",
    "库": "Packages",
    "任务": "Tasks",
    "命令": "Commands",
    "工作区概览": "Workspace Overview",
    "工作区": "Workspace",
    "清单": "Manifest",
    "目录": "Directory",
    "平台": "Platform",
    "锁文件": "Lock file",
    "命名环境": "Environments",
    "环境路径": "Environment path",
    "依赖数": "Dependencies",
    "安装 / 更新环境": "Install / Update",
    "安装 / 更新环境 {}": "Install / Update {}",
    "安装环境": "Install Environment",
    "重新锁定": "Relock",
    "重新锁定环境": "Relock Environment",
    "锁定环境": "Lock Environment",
    "清理环境": "Clean Environment",
    "清理环境…": "Clean Environment…",
    "重新安装环境": "Reinstall Environment",
    "打开目录": "Open Folder",
    "复制": "Copy",
    "复制路径": "Copy Path",
    "复制详情": "Copy Details",
    "复制包名": "Copy Package Name",
    "复制已安装版本": "Copy Installed Version",
    "复制环境路径": "Copy Environment Path",
    "复制命令": "Copy Command",
    "关闭": "Close",
    "取消": "Cancel",
    "创建": "Create",
    "保存": "Save",
    "保存  Ctrl+S": "Save  Ctrl+S",
    "查找": "Find",
    "查找  Ctrl+F": "Find  Ctrl+F",
    "重新加载": "Reload",
    "路径": "Path",
    "浏览…": "Browse…",
    "选择文件…": "Choose File…",
    "选择目录…": "Choose Folder…",
    "选择清单文件…": "Choose Manifest…",
    "选择工作区": "Open Workspace",
    "打开": "Open",
    "主题": "Theme",
    "界面语言": "Interface Language",
    "语言修改后需要重启程序生效。": "Language changes take effect after restarting the application.",
    "浅色": "Light",
    "深色": "Dark",
    "控制台最大行数": "Console max lines",
    "Pixi 可执行文件": "Pixi executable",
    "留空则自动从 PATH 查找；修改后下次刷新或重启生效。": "Leave blank to find Pixi on PATH; applies after refresh or restart.",
    "清空打开历史": "Clear Open History",
    "清空历史": "Clear History",
    "清空": "Clear",
    "自动滚动": "Auto-scroll",
    "全部停止": "Stop All",
    "关闭已完成": "Close Finished",
    "系统": "System",
    "系统消息": "System log",
    "输出": "Output",
    "停止": "Stop",
    "停止任务": "Stop Task",
    "正在停止…": "Stopping…",
    "正在停止：{}": "Stopping: {}",
    "正在停止所有任务…": "Stopping all tasks…",
    "全部停止": "Stop All",
    "关闭窗口会终止当前 {} 个运行中的任务，继续吗？": "Closing will terminate {} running task(s). Continue?",
    "任务正在运行": "Tasks are running",
    "确定停止“{}”及其子进程吗？": "Stop “{}” and its child processes?",
    "确定停止当前所有任务及其子进程吗？": "Stop all running tasks and their child processes?",
    "共 {} 个任务。": "{} task(s).",
    "运行中：{}": "Running: {}",
    "运行中：task {}": "Running task: {}",
    "Task: {}": "Task: {}",
    "Python: {}": "Python: {}",
    "Pixi task: {}": "Pixi task: {}",
    "Pixi 命令": "Pixi command",
    "清理环境 {}": "Clean environment {}",
    "{}：{}": "{}: {}",
    "{} 完成": "{} completed",
    "{} 已停止": "{} stopped",
    "{} 失败，退出码 {}": "{} failed with exit code {}",
    "运行任务": "Run Task",
    "运行任务 / 命令": "Run Task / Command",
    "运行任务：{}": "Run task: {}",
    "运行任务: {}": "Run task: {}",
    "附加参数": "Extra arguments",
    "参数会追加到 pixi run 命令末尾；包含空格的路径请加双引号。": "Arguments are appended to pixi run; wrap paths containing spaces in double quotes.",
    "打开 Pixi 环境": "Open Pixi Environment",
    "可以选 pixi.toml / pyproject.toml，也可以选工作区目录。": "Choose pixi.toml / pyproject.toml or a workspace directory.",
    "最近使用的工作区也可以在顶部“最近打开”菜单中快速切换。": "Recently used workspaces can also be switched from the “Recent” menu at the top.",
    "启动": "Run",
    "启动选中任务": "Run Selected Task",
    "带参数启动…": "Run with Arguments…",
    "在终端中运行": "Run in Terminal",
    "在终端运行": "Run in Terminal",
    "查看详情": "View Details",
    "任务详情": "Task Details",
    "名称": "Name",
    "命令": "Command",
    "工作目录": "Working Directory",
    "描述": "Description",
    "依赖": "Dependencies",
    "参数定义": "Argument schema",
    "有（启动时可填写参数）": "Available (enter at launch)",
    "无": "None",
    "当前环境": "Current environment",
    "当前环境: {}": "Environment: {}",
    "当前环境: {}  ·  已安装 {} 个包（用户显式 {} 个）  ·  {} 个 task  ·  {} 个命名环境": "Environment: {}  ·  {} package(s) installed ({} explicit)  ·  {} task(s)  ·  {} environment(s)",
    "{} 个 task（当前环境 {}）": "{} task(s) (environment {})",
    "⚠ pixi.toml 比 pixi.lock 新，锁文件可能已过期。": "⚠ pixi.toml is newer than pixi.lock; the lock file may be stale.",
    "快速任务": "Quick Tasks",
    "当前环境没有 task": "No tasks in this environment",
    "打开一个环境后显示可用 task": "Open an environment to see tasks",
    "Python 程序": "Python Programs",
    "还没有用此环境运行过 Python 程序": "No Python program has been run in this environment yet",
    "打开一个环境后显示运行历史": "Open an environment to see run history",
    "运行（使用保存的参数）": "Run (saved arguments)",
    "编辑参数…": "Edit Arguments…",
    "从历史中移除": "Remove from History",
    "从历史中移除这个程序吗？\n{}": "Remove this program from history?\n{}",
    "移除历史": "Remove History",
    "脚本路径": "Script path",
    "参数": "Arguments",
    "按 Windows 命令行习惯填写；包含空格的路径请加双引号。": "Use Windows command-line quoting; wrap paths containing spaces in double quotes.",
    "工作目录": "Working directory",
    "使用脚本目录": "Use Script Folder",
    "环境": "Environment",
    "命令预览": "Command Preview",
    "运行": "Run",
    "清空表单": "Clear Form",
    "提示：运行记录会出现在左侧“Python 程序”，保存本次参数后可以一键重复运行。": "Tip: runs appear under “Python Programs” on the left with their saved arguments.",
    "请选择或输入 Python 脚本路径。": "Choose or enter a Python script path.",
    "脚本不存在": "Script not found",
    "工作目录不存在": "Working directory not found",
    "找不到脚本：\n{}": "Script not found:\n{}",
    "找不到目录：\n{}": "Directory not found:\n{}",
    "环境尚未安装": "Environment not installed",
    "环境 {} 尚未安装。pixi run 可能会先安装环境，继续吗？": "Environment {} is not installed. pixi run may install it first. Continue?",
    "可能没有 Python": "Python may be missing",
    "环境 {} 中未找到 python.exe。仍要尝试运行吗？": "python.exe was not found in environment {}. Try anyway?",
    "已在新终端中运行 {}": "Running {} in a new terminal",
    "已在新终端打开：{}": "Opened in a new terminal: {}",
    "运行 Python": "Run Python",
    "程序": "Program",
    "命令中心": "Command Center",
    "Pixi CLI 文档": "Pixi CLI Docs",
    "命令帮助": "Command Help",
    "正在加载帮助…": "Loading help…",
    "手动命令": "Manual Command",
    "自动使用当前工作区": "Use current workspace",
    "直接输入 pixi 后面的参数，例如 add numpy；也可以粘贴完整 pixi 命令。命令按参数直接执行，不经过 shell。": "Enter arguments after pixi, e.g. add numpy; a full pixi command is also accepted. Commands run directly without a shell.",
    "请输入 pixi 命令。": "Enter a pixi command.",
    "（不指定）": "(not specified)",
    "全部": "All",
    "全部库": "All Packages",
    "仅用户安装": "User-installed",
    "仅用户安装 ({})": "User-installed ({})",
    "全部库 ({})": "All Packages ({})",
    "搜索": "Search",
    "类型": "Type",
    "名称": "Name",
    "已安装": "Installed",
    "最新版本": "Latest",
    "最新": "Latest",
    "版本": "Version",
    "状态": "Status",
    "请求约束": "Requested",
    "来源": "Source",
    "大小": "Size",
    "包详情": "Package Details",
    "完整详情…": "Full Details…",
    "包详情：{}": "Package details: {}",
    "构建": "Build",
    "许可证": "License",
    "文件": "File",
    "地址": "URL",
    "更新到兼容版本": "Update (compatible)",
    "升级到最新版本": "Upgrade to Latest",
    "查询最新版本": "Check Latest",
    "名称: {}": "Name: {}",
    "已安装版本: {}": "Installed: {}",
    "最新版本: {}": "Latest: {}",
    "状态: {}": "Status: {}",
    "类型: {}": "Type: {}",
    "构建: {}": "Build: {}",
    "请求约束: {}": "Requested: {}",
    "来源: {}": "Source: {}",
    "许可证: {}": "License: {}",
    "文件名: {}": "File: {}",
    "URL: {}": "URL: {}",
    "运行依赖:": "Runtime dependencies:",
    "约束:": "Constraints:",
    "兼容范围内可更新到: ": "Compatible update: ",
    "最新版本查询失败: ": "Latest-version check failed: ",
    "查询失败: ": "Check failed: ",
    "读取失败：{}  （可点击“安装环境”或“刷新”）": "Read failed: {} (try Install Environment or Refresh)",
    "显示 {} / {} 个包 · 用户显式依赖 {} 个": "Showing {} / {} packages · {} explicit dependencies",
    "正在读取 {} 的库列表…": "Reading packages for {}…",
    "正在读取环境 {} 的库列表…": "Reading packages for environment {}…",
    "读取环境库列表失败": "Failed to read environment packages",
    "请先选择一个或多个包。": "Select one or more packages first.",
    "请先在列表或详情中选择一个包。": "Select a package in the list or details first.",
    "更新包": "Update Package",
    "包名": "Package name",
    "包规格": "Package specification",
    "包规格 *": "Package specification *",
    "启用": "Enabled",
    "仅 PyPI：以 editable 方式添加本地包。": "PyPI only: add a local package in editable mode.",
    "仅 PyPI：自定义 index URL。": "PyPI only: custom index URL.",
    "例如 win-64、linux-64；留空使用默认平台。": "For example win-64 or linux-64; leave blank for the default platform.",
    "写入指定 feature，留空为 default。": "Write to a specific feature; leave blank for default.",
    "只写清单不安装": "Manifest only (no install)",
    "对应 --no-install。": "Corresponds to --no-install.",
    "添加 pypi 依赖而不是 conda 依赖。": "Add a PyPI dependency instead of a conda dependency.",
    "空格分隔，例如 numpy pandas 或 numpy=2.0；PyPI 包可写 pkg==1.2。": "Space-separated, e.g. numpy pandas or numpy=2.0; PyPI packages may use pkg==1.2.",
    "要操作/使用的命名环境。": "Named environment to use or modify.",
    "空格分隔的包名。": "Space-separated package names.",
    "只看计划（dry-run）": "Plan only (dry-run)",
    "留空更新全部；多个包用空格分隔。": "Leave blank to update all; separate multiple packages with spaces.",
    "留空升级全部；多个包用空格分隔。": "Leave blank to upgrade all; separate multiple packages with spaces.",
    "包名 *": "Package name *",
    "严格使用 lock 文件，不更新锁文件。": "Use the lock file strictly; do not update it.",
    "检查 lock 文件是否最新，否则失败。": "Check that the lock file is current; fail otherwise.",
    "只检查是否需要更新": "Check only",
    "只计算不写入": "Compute only, do not write",
    "只清理激活缓存": "Activation cache only",
    "只重装这些包；留空重装整个环境。": "Reinstall only these packages; leave blank for the whole environment.",
    "所有环境": "All environments",
    "指定包": "Specific packages",
    "重新安装全部环境，忽略“环境”字段。": "Reinstall all environments, ignoring the Environment field.",
    "Task / 命令 *": "Task / command *",
    "只打印不执行": "Print only, do not execute",
    "可以直接写 task 名，也可以写 python script.py 等命令。": "Enter a task name or a command such as python script.py.",
    "忽略当前 shell 环境变量。": "Ignore the current shell environment.",
    "跳过任务依赖": "Skip task dependencies",
    "Task 名称 *": "Task name *",
    "例如 pytest -q 或 python build.py。": "For example pytest -q or python build.py.",
    "依赖 Task": "Depends on tasks",
    "命令 *": "Command *",
    "相对于 workspace 根目录。": "Relative to the workspace root.",
    "空格分隔的 task 名。": "Space-separated task names.",
    "空格分隔。": "Space-separated.",
    "包含缓存和环境大小": "Include cache and environment sizes",
    "例如 win-64；留空由 Pixi 决定。": "For example win-64; leave blank for Pixi to decide.",
    "新工作区目录，建议使用绝对路径。": "New workspace directory; an absolute path is recommended.",
    "格式": "Format",
    "路径 *": "Path *",
    "搜索包": "Search Packages",
    "频道": "Channel",
    "版本数": "Version count",
    "显示的版本数量，默认 5。": "Number of versions to show (default 5).",
    "可选，例如 conda-forge。": "Optional, e.g. conda-forge.",
    "使用 PyPI": "Use PyPI",
    "PyPI 索引": "PyPI index",
    "添加依赖": "Add Dependency",
    "移除依赖": "Remove Dependency",
    "升级依赖（最新版本）": "Upgrade (latest)",
    "更新依赖（兼容范围）": "Update (compatible)",
    "添加 Task": "Add Task",
    "移除 Task": "Remove Task",
    "环境信息": "Environment Info",
    "打开 Pixi Shell": "Open Pixi Shell",
    "初始化工作区": "Initialize Workspace",
    "向 workspace 添加 conda 或 PyPI 依赖。": "Add conda or PyPI dependencies to the workspace.",
    "从 workspace 中移除依赖。": "Remove dependencies from the workspace.",
    "在现有版本约束内更新依赖并写入 lock 文件。": "Update dependencies within current constraints and write the lock file.",
    "放宽版本约束，把依赖升级到更新版本。可能修改 pixi.toml。": "Relax constraints and upgrade dependencies. This may modify pixi.toml.",
    "在配置的 conda 频道中搜索包。": "Search packages in configured conda channels.",
    "根据清单和 lock 文件安装或更新环境。": "Install or update the environment from the manifest and lock file.",
    "求解环境并更新 pixi.lock，但不安装环境。": "Solve the environment and update pixi.lock without installing.",
    "删除 .pixi 中的环境目录；不会删除 manifest 或 lock 文件。": "Remove the environment directory under .pixi; manifest and lock files are kept.",
    "更新 lock 文件并重新安装所选环境。": "Update the lock file and reinstall the selected environment.",
    "在选中环境中运行 task 或任意命令。": "Run a task or arbitrary command in the selected environment.",
    "向 workspace 添加一个 task。": "Add a task to the workspace.",
    "从 workspace 中移除 task。": "Remove a task from the workspace.",
    "显示 Pixi、workspace 和环境信息。": "Show Pixi, workspace and environment information.",
    "在新终端中激活环境并打开 shell。": "Activate the environment and open a shell in a new terminal.",
    "创建一个新的 Pixi 工作区。": "Create a new Pixi workspace.",
    "清单编辑器": "Manifest Editor",
    "未打开文件": "No file open",
    "已保存 ": "Saved ",
    "已保存（语法错误）": "Saved (syntax error)",
    "语法错误": "Syntax error",
    "TOML 语法 OK": "TOML syntax OK",
    "TOML 语法错误": "TOML syntax error",
    "文件存在语法错误：\n\n{}\n\n仍然保存吗？": "The file has a syntax error:\n\n{}\n\nSave anyway?",
    "文件已被修改": "File changed",
    "该文件已被其他程序修改。\n仍然覆盖保存吗？": "The file was changed by another program.\nOverwrite anyway?",
    "未保存的修改": "Unsaved changes",
    "{} 有未保存的修改。\n\n是否先保存？": "{} has unsaved changes.\n\nSave first?",
    "保存失败": "Save failed",
    "无法保存文件：\n{}": "Could not save file:\n{}",
    "重新加载": "Reload",
    "重新加载会丢弃未保存的修改，继续吗？": "Reloading will discard unsaved changes. Continue?",
    "读取失败": "Read failed",
    "无法读取：\n{}\n\n{}": "Could not read:\n{}\n\n{}",
    "全选": "Select All",
    "撤销": "Undo",
    "重做": "Redo",
    "剪切": "Cut",
    "粘贴": "Paste",
    "上一个": "Previous",
    "下一个": "Next",
    "打开环境后显示命令": "Open an environment to see the command",
    "选择 Python 脚本后显示命令": "Choose a Python script to see the command",
    "（打开环境后显示命令）": "(Open an environment to see the command)",
    "（选择 Python 脚本后显示命令）": "(Choose a Python script to see the command)",
    "打开一个 pixi.toml / pyproject.toml": "Open a pixi.toml / pyproject.toml",
    "工作区": "Workspace",
    "当前环境尚未安装，库列表和运行功能可能不可用。": "The current environment is not installed; packages and run functions may be unavailable.",
    "还没有 pixi.lock，建议执行一次“安装 / 更新环境”。": "No pixi.lock yet. Run Install / Update first.",
    "pixi.toml 比 pixi.lock 新，锁文件可能已过期。": "pixi.toml is newer than pixi.lock; the lock file may be stale.",
    "清单比 pixi.lock 新（建议重新锁定）": "Manifest is newer than pixi.lock (relock recommended)",
    "锁文件存在（无法确认是否最新）": "Lock file exists (freshness could not be verified)",
    "pixi.lock 已过期，建议重新锁定环境。": "pixi.lock is stale; relock the environment.",
    "无法确认 pixi.lock 是否最新，建议重新锁定。": "Could not verify whether pixi.lock is current; relocking is recommended.",
    "不存在（尚未安装 / 锁定）": "Missing (not installed/locked)",
    "环境已打开，但库列表读取失败": "Environment opened, but packages could not be read",
    "读取库列表失败: ": "Failed to read packages: ",
    "读取 task 失败: ": "Failed to read tasks: ",
    "读取 task 失败：": "Failed to read tasks: ",
    "读取库列表失败：": "Failed to read packages: ",
    "刷新失败": "Refresh failed",
    "正在刷新环境信息 …": "Refreshing environment…",
    "已刷新": "Refreshed",
    "已刷新，但库列表读取失败": "Refreshed, but packages could not be read",
    "已切换到环境 {}": "Switched to environment {}",
    "已清空最近打开记录": "Recent environments cleared",
    "已移除 Python 历史": "Python history entry removed",
    "清单已保存，正在刷新环境信息…": "Manifest saved; refreshing environment…",
    "打开环境失败": "Could not open environment",
    "正在打开 {} …": "Opening {}…",
    "已打开 {} / {}": "Opened {} / {}",
    "已打开工作区: {}  [{}]": "Workspace opened: {}  [{}]",
    "失败": "Failed",
    "错误": "Error",
    "操作失败": "Operation failed",
    "无法启动命令": "Could not start command",
    "无法启动 task": "Could not start task",
    "无法运行 Python": "Could not run Python",
    "无法打开终端": "Could not open terminal",
    "找不到 Pixi": "Pixi not found",
    "找不到 Pixi 清单": "Pixi manifest not found",
    "找不到清单": "Manifest not found",
    "找不到 pixi 可执行文件。请在“设置”中指定 pixi.exe，或把 Pixi 加入 PATH。": "Pixi executable not found. Set pixi.exe in Settings or add Pixi to PATH.",
    "找不到 pixi。请点击“设置”指定 pixi.exe。": "Pixi not found. Click Settings to choose pixi.exe.",
    "请先在“设置”中指定 pixi.exe，或把 Pixi 加入 PATH。": "Set pixi.exe in Settings or add Pixi to PATH first.",
    "该路径下没有 pixi.toml 或 pyproject.toml。": "This path has no pixi.toml or pyproject.toml.",
    "路径下没有 pixi.toml 或 pyproject.toml：\n{}": "No pixi.toml or pyproject.toml under:\n{}",
    "路径为空": "Empty path",
    "请选择或输入工作区路径。": "Choose or enter a workspace path.",
    "路径不存在": "Path not found",
    "该历史环境已不存在：\n{}\n\n是否从历史中移除？": "This recent environment no longer exists:\n{}\n\nRemove it from history?",
    "（暂无最近记录）": "(no recent environments)",
    "清除历史": "Clear History",
    "确定清空最近打开的环境记录吗？": "Clear the recent-environment list?",
    "确定清空最近打开的环境记录吗？Python 程序历史不会被删除。": "Clear the recent-environment list? Python program history will be kept.",
    "需要环境": "Environment required",
    "请先打开一个 Pixi 环境。": "Open a Pixi environment first.",
    "请先打开环境。": "Open an environment first.",
    "请先打开一个环境。": "Open an environment first.",
    "请先选择一个 task。": "Select a task first.",
    "请填写 task 名称或命令。": "Enter a task name or command.",
    "请填写包名。": "Enter a package name.",
    "请填写新工作区路径。": "Enter a new workspace path.",
    "请填写要添加的包。": "Enter package(s) to add.",
    "请填写要移除的 task 名称。": "Enter task name(s) to remove.",
    "请填写要移除的包。": "Enter package(s) to remove.",
    "命令参数": "Command arguments",
    "已有修改环境的命令": "Environment command already running",
    "同一时间只允许一个会修改环境/清单的 pixi 命令。\n请等待当前修改命令完成。": "Only one pixi command that modifies the environment/manifest may run at a time.\nWait for the current command to finish.",
    "确认操作": "Confirm Operation",
    "即将执行可能修改环境的操作：\n\n{}\n\n继续吗？": "This operation may modify the environment:\n\n{}\n\nContinue?",
    "编辑器有未保存修改": "Unsaved editor changes",
    "当前 pixi.toml 有未保存修改，执行该命令可能同时修改清单。\n继续吗？": "pixi.toml has unsaved changes and this command may modify it.\nContinue?",
    "清理环境": "Clean Environment",
    "这会删除环境 {} 的 .pixi 环境目录，但不会删除 pixi.toml 或 pixi.lock。\n\n继续吗？": "This removes the .pixi environment directory for {}; pixi.toml and pixi.lock are kept.\n\nContinue?",
    "当前工作区还没有 pixi.lock。请先安装/锁定环境，再检查兼容更新。": "This workspace has no pixi.lock yet. Install/lock the environment before checking compatible updates.",
    "该包来自自定义 PyPI 源，无法通过 pypi.org 公共 API 检查最新版本。": "This package comes from a custom PyPI source; its latest version cannot be checked via the public pypi.org API.",
    "在配置的频道中找不到包“{}”。": "Package “{}” was not found in the configured channels.",
    "pixi 命令失败": "pixi command failed",
    "pixi 命令超时（{} 秒）": "pixi command timed out after {} seconds",
    "无法启动 pixi：{}": "Could not start pixi: {}",
    "无法运行 pixi：{}": "Could not run pixi: {}",
    "pixi 返回了无法解析的 JSON：{}": "pixi returned invalid JSON: {}",
    "pixi info 返回的数据格式不正确。": "pixi info returned an unexpected data format.",
    "pixi search 返回的数据格式不正确。": "pixi search returned an unexpected data format.",
    "命令没有返回 JSON 输出": "Command returned no JSON output",
    "无法从输出中解析 JSON": "Could not parse JSON from output",
    "PyPI 上找不到包“{}”。": "Package “{}” was not found on PyPI.",
    "PyPI 查询失败（HTTP {}）。": "PyPI query failed (HTTP {}).",
    "PyPI 查询失败：{}": "PyPI query failed: {}",
    "PyPI 返回的数据中没有版本号。": "PyPI returned no version number.",
    "控制台最大行数必须是整数。": "Console max lines must be an integer.",
    "Pixi: 未找到": "Pixi: not found",
    "Pixi: 检查中…": "Pixi: checking…",
    "Pixi: 无法运行": "Pixi: cannot run",
    "未知版本": "Unknown version",
    "Pixi: 未知版本": "Pixi: unknown version",
    "查看详情": "View Details",
    "打开终端": "Open Terminal",
    "全部": "All",
    "（尚未安装）": "(not installed)",
    "（无参数）": "(no arguments)",
    "（无命令）": "(no command)",
    "（无脚本）": "(no script)",
    "参数: （无）": "Arguments: (none)",
    "参数: ": "Arguments: ",
    "工作目录: ": "Working directory: ",
    "上次运行: ": "Last run: ",
    "所属: ": "Feature: ",
    "依赖: ": "Depends on: ",
    "目录: ": "Directory: ",
    "⚠ 脚本文件不存在": "⚠ Script file not found",
    "任务": "Task",
    "任务 ": "Task ",
    "环境": "Environment",
    "运行": "Run",
    "停止": "Stop",
    "关闭": "Close",
    "是": "Yes",
    "否": "No",
    "确定": "OK",
}

JA: Dict[str, str] = {
    "Pixi 环境管理器": "Pixi 環境マネージャー",
    "Pixi 环境管理器 - {} [{}]": "Pixi 環境マネージャー - {} [{}]",
    "打开环境": "環境を開く",
    "最近打开  ▾": "最近  ▾",
    "最近打开": "最近",
    "环境": "環境",
    "基础依赖": "基礎依存関係",
    "基础": "基礎",
    "作用域": "スコープ",
    "说明": "説明",
    "兼容更新": "互換更新",
    "传递": "推移的",
    "未安装": "未インストール",
    "环境:{}": "環境: {}",
    "feature:{}": "feature: {}",
    "基础依赖 ({})": "基礎依存関係 ({})",
    "基础依赖 {} 个 · 所有环境共享": "基礎依存関係 {} 個 · すべての環境で共有",
    "基础依赖视图（所有环境共享） · Task/Python 使用 {} 环境": "基礎依存関係ビュー（共有） · Task/Python は {} 環境で実行",
    "基础依赖视图：任务仍使用 {} 环境运行": "基礎依存関係ビュー: タスクは {} 環境で実行されます",
    "当前环境没有可显示的 task": "この環境に表示できるタスクはありません。",
    "基础依赖模式：此命令作用于所有环境。": "基礎依存関係モード: このコマンドはすべての環境に影響します。",
    "基础依赖视图：Python 仍使用 {} 环境运行": "基礎依存関係ビュー: Python は {} 環境で実行されます",
    "当前环境: default · add/remove 仅影响 default；共享依赖请切换到基础依赖": "現在の環境: default · add/remove は default のみに影響します。共有依存関係は「基礎依存関係」に切り替えてください",
    "删除作用域冲突": "削除スコープの競合",
    "删除基础依赖": "基礎依存関係を削除",
    "同一命令不能同时删除基础依赖和环境专属依赖。": "1 つのコマンドで基礎依存関係と環境専用依存関係を同時に削除できません。",
    "基础依赖：{}": "基礎依存関係: {}",
    "其他依赖：{}": "その他の依存関係: {}",
    "该包不在基础依赖中：{}": "これらのパッケージは基礎依存関係ではありません: {}",
    "{} 属于基础依赖，删除后所有环境都会受影响。\n\n是否从基础依赖中删除？": "{} は基礎依存関係です。削除するとすべての環境に影響します。\n\n基礎依存関係から削除しますか？",
    "环境管理  ▾": "環境管理  ▾",
    "新建 Pixi 工作区": "新しい Pixi ワークスペース",
    "新建工作区…": "新しいワークスペース…",
    "新建工作区 {}": "ワークスペース {} を作成",
    "只会创建 pixi.toml；不安装依赖，创建后进入基础依赖视图。": "pixi.toml のみを作成します。依存関係はインストールせず、作成後は基礎依存関係ビューを開きます。",
    "目录": "ディレクトリ",
    "选择目录…": "ディレクトリを選択…",
    "工作区名称": "ワークスペース名",
    "频道": "チャネル",
    "多个频道用逗号分隔，例如 conda-forge,bioconda。": "複数のチャネルはカンマで区切ります（例: conda-forge,bioconda）。",
    "平台": "プラットフォーム",
    "至少选择一个平台；默认使用当前系统平台。": "少なくとも 1 つのプラットフォームを選択してください。既定では現在のシステムです。",
    "Pixi 会同时创建 .gitignore 和 .gitattributes；工作区名称由目录名决定。": "Pixi は .gitignore と .gitattributes も作成します。ワークスペース名はディレクトリ名になります。",
    "请选择一个目录。": "ディレクトリを選択してください。",
    "目标路径已存在且不是目录。": "指定されたパスは存在しますが、ディレクトリではありません。",
    "目录中已有 Pixi 清单，请直接打开。": "このディレクトリには既に Pixi マニフェストがあります。直接開いてください。",
    "目录中已有 pyproject.toml；新建向导只创建 pixi.toml。": "このディレクトリには pyproject.toml があります。新規作成ウィザードは pixi.toml のみを作成します。",
    "目录非空，创建时会追加 pixi.toml、.gitignore、.gitattributes。": "ディレクトリは空ではありません。pixi.toml、.gitignore、.gitattributes を追加します。",
    "目录为空，将创建 pixi.toml。": "ディレクトリは空です。pixi.toml を作成します。",
    "目录不存在，创建时会自动建立。": "ディレクトリが存在しません。作成時に自動的に作成します。",
    "请选择或输入工作区目录。": "ワークスペースのディレクトリを選択または入力してください。",
    "已有 Pixi 清单": "Pixi マニフェストが既にあります",
    "该目录已有 Pixi 清单，请直接打开。": "このディレクトリには既に Pixi マニフェストがあります。直接開いてください。",
    "已有 pyproject.toml": "pyproject.toml が既にあります",
    "新建向导只创建 pixi.toml。该目录已有 pyproject.toml，请换一个目录或直接打开现有清单。": "新規作成ウィザードは pixi.toml のみを作成します。このディレクトリには pyproject.toml があるため、別のディレクトリを選ぶか既存のマニフェストを開いてください。",
    "目录无效": "無効なディレクトリ",
    "不能直接在磁盘根目录创建工作区。": "ディスクのルート直下にはワークスペースを作成できません。",
    "频道为空": "チャネルがありません",
    "至少填写一个频道。": "少なくとも 1 つのチャネルを入力してください。",
    "平台为空": "プラットフォームがありません",
    "至少选择一个平台。": "少なくとも 1 つのプラットフォームを選択してください。",
    "目录非空": "ディレクトリが空ではありません",
    "目录中已有文件。Pixi 会追加 .gitignore、.gitattributes 和 pixi.toml，但不会删除已有文件。\n\n继续创建吗？": "ディレクトリには既にファイルがあります。Pixi は .gitignore、.gitattributes、pixi.toml を追加しますが、既存ファイルは削除しません。\n\n作成を続けますか？",
    "没有 Pixi 清单": "Pixi マニフェストがありません",
    "该目录下没有 pixi.toml 或 pyproject.toml。\n\n是否创建新的 Pixi 工作区？": "このディレクトリには pixi.toml も pyproject.toml もありません。\n\n新しい Pixi ワークスペースを作成しますか？",
    "目录不存在": "ディレクトリが存在しません",
    "目录不存在：\n{}\n\n是否创建该目录并初始化 Pixi 工作区？": "ディレクトリが存在しません:\n{}\n\n作成して Pixi ワークスペースを初期化しますか？",
    "请先停止所有运行中的任务并等待刷新完成，再新建工作区。": "ワークスペースを作成する前に、実行中のタスクをすべて停止し、更新完了を待ってください。",
    "请先保存或放弃当前清单的修改，再新建工作区。": "ワークスペースを作成する前に、現在のマニフェストの変更を保存または破棄してください。",
    "正在创建 {}": "{} を作成中",
    "初始化结束，但没有找到 {}": "初期化は終了しましたが、{} が見つかりません",
    "添加环境": "環境を追加",
    "添加环境…": "環境を追加…",
    "添加环境 {}": "環境 {} を追加",
    "删除环境": "環境を削除",
    "删除环境 {}": "環境 {} を削除",
    "删除当前环境…": "現在の環境を削除…",
    "当前环境不能删除": "現在の環境は削除できません",
    "default 是隐式环境，不能删除。": "default は暗黙の環境のため削除できません。",
    "请先保存或放弃 pixi.toml 的未保存修改，再管理环境。": "環境を管理する前に pixi.toml の変更を保存または破棄してください。",
    "请先停止所有运行中的任务，再删除环境。": "環境を削除する前に実行中のタスクをすべて停止してください。",
    "请先停止所有运行中的任务并等待刷新完成，再添加环境。": "環境を追加する前に実行中のタスクを停止し、更新完了を待ってください。",
    "环境名称": "環境名",
    "名称不能重复，default 是隐式环境，不能作为新名称。": "名前は重複できません。default は暗黙の環境なので使用できません。",
    "包含 default feature": "default feature を含める",
    "工作区没有其他 feature。": "このワークスペースには他の feature がありません。",
    "取消 default feature 时，必须至少选择一个其他 feature。": "default を無効にする場合は、他の feature を 1 つ以上選択してください。",
    "Solve group（可选）": "Solve group（任意）",
    "创建后立即安装环境": "作成後に環境をインストール",
    "环境已存在": "環境が既に存在します",
    "环境“{}”已经存在。": "環境「{}」は既に存在します。",
    "环境名称不能包含空格、单引号或双引号。": "環境名にスペース、一重引用符、二重引用符は使用できません。",
    "请输入环境名称。": "環境名を入力してください。",
    "default 是隐式环境，不能作为新环境名称。": "default は暗黙の環境のため、新しい環境名には使用できません。",
    "从清单中删除环境“{}”？": "マニフェストから環境「{}」を削除しますか？",
    "这会修改 pixi.toml / pyproject.toml，但不会自动更新 lock 文件。": "pixi.toml / pyproject.toml を変更しますが、lock ファイルは自動更新しません。",
    "同时清理已安装的环境目录（pixi clean）": "インストール済み環境ディレクトリもクリーンする（pixi clean）",
    "该环境当前没有已安装的 .pixi 环境目录。": "この環境にはインストール済みの .pixi ディレクトリがありません。",
    "（打开环境后显示命令）": "（環境を開くとコマンドが表示されます）",
    "（选择 Python 脚本后显示命令）": "（Python スクリプトを選択するとコマンドが表示されます）",
    "刷新": "更新",
    "设置": "設定",
    "设置已保存": "設定を保存しました",
    "语言": "言語",
    "语言设置已保存，重启程序后生效。": "言語設定を保存しました。再起動後に反映されます。",
    "就绪": "準備完了",
    "空闲": "アイドル",
    "运行中": "実行中",
    "运行中 {} 个": "{} 件実行中",
    "运行中 {} 个任务": "{} 件実行中",
    "完成": "完了",
    "已停止": "停止済み",
    "失败（退出码 {}）": "失敗（終了コード {}）",
    "用时 {:.1f}s": "{:.1f} 秒",
    "[完成] 用时 {:.1f}s\n": "[完了] {:.1f} 秒\n",
    "[失败] 退出码 {}，用时 {:.1f}s\n": "[失敗] 終了コード {}、{:.1f} 秒\n",
    "[已停止] 用时 {:.1f}s\n": "[停止] {:.1f} 秒\n",
    "[错误] ": "[エラー] ",
    "已保存": "保存済み",
    "未保存": "未保存",
    "未打开文件": "ファイルなし",
    "未打开环境": "環境なし",
    "未检查": "未確認",
    "查询中…": "確認中…",
    "查询失败": "確認失敗",
    "已是最新": "最新です",
    "有更新": "更新あり",
    "已安装更高": "インストール版が新しい",
    "可兼容更新": "互換更新あり",
    "查询最新版本": "最新版を確認",
    "查询选中最新": "選択項目の最新版",
    "查询此包最新版": "このパッケージの最新版",
    "检查兼容更新": "互換更新を確認",
    "检查更新": "更新を確認",
    "检查兼容更新失败": "互換更新の確認に失敗",
    "最新版本查询完成": "最新版の確認が完了",
    "发现 {} 个兼容更新": "{} 件の互換更新",
    "发现 {} 个包存在兼容范围内的更新": "{} 個のパッケージに互換更新があります",
    "兼容更新检查完成：{} 个更新": "互換更新の確認完了：{} 件",
    "兼容范围内没有可更新的包": "互換範囲内の更新はありません",
    "兼容范围内没有可更新的包（或环境没有锁文件）": "互換更新なし（またはロックファイルなし）",
    "正在检查兼容更新…": "互換更新を確認中…",
    "正在检查兼容范围内的更新…": "互換更新を確認中…",
    "正在查询 {} 个包的最新版本…": "{} 個のパッケージの最新版を確認中…",
    "概览": "概要",
    "库": "パッケージ",
    "任务": "タスク",
    "添加 Task": "タスクを追加",
    "移除 Task": "タスクを削除",
    "更新依赖（兼容范围）": "更新（互換）",
    "升级依赖（最新版本）": "アップグレード（最新）",
    "命令": "コマンド",
    "工作区概览": "ワークスペース概要",
    "工作区": "ワークスペース",
    "清单": "マニフェスト",
    "目录": "ディレクトリ",
    "平台": "プラットフォーム",
    "锁文件": "ロックファイル",
    "命名环境": "環境",
    "环境路径": "環境パス",
    "依赖数": "依存数",
    "安装 / 更新环境": "インストール / 更新",
    "安装 / 更新环境 {}": "{} をインストール / 更新",
    "安装环境": "環境をインストール",
    "重新锁定": "再ロック",
    "重新锁定环境": "環境を再ロック",
    "锁定环境": "環境をロック",
    "锁文件存在（无法确认是否最新）": "ロックファイルは存在します（最新か確認できません）",
    "pixi.lock 已过期，建议重新锁定环境。": "pixi.lock が古いため、環境の再ロックを推奨します。",
    "无法确认 pixi.lock 是否最新，建议重新锁定。": "pixi.lock が最新か確認できません。再ロックを推奨します。",
    "清理环境": "環境をクリーン",
    "清理环境…": "環境をクリーン…",
    "重新安装环境": "環境を再インストール",
    "打开目录": "フォルダーを開く",
    "复制": "コピー",
    "复制路径": "パスをコピー",
    "复制详情": "詳細をコピー",
    "复制包名": "パッケージ名をコピー",
    "复制已安装版本": "インストール版をコピー",
    "名称: {}": "名前：{}",
    "已安装版本: {}": "インストール版：{}",
    "最新版本: {}": "最新版：{}",
    "复制环境路径": "環境パスをコピー",
    "复制命令": "コマンドをコピー",
    "关闭": "閉じる",
    "取消": "キャンセル",
    "创建": "作成",
    "保存": "保存",
    "保存  Ctrl+S": "保存  Ctrl+S",
    "查找": "検索",
    "查找  Ctrl+F": "検索  Ctrl+F",
    "重新加载": "再読み込み",
    "路径": "パス",
    "浏览…": "参照…",
    "选择文件…": "ファイルを選択…",
    "选择目录…": "フォルダーを選択…",
    "选择清单文件…": "マニフェストを選択…",
    "选择工作区": "ワークスペースを開く",
    "打开": "開く",
    "主题": "テーマ",
    "界面语言": "表示言語",
    "语言修改后需要重启程序生效。": "言語の変更はアプリの再起動後に反映されます。",
    "浅色": "ライト",
    "深色": "ダーク",
    "控制台最大行数": "コンソール最大行数",
    "Pixi 可执行文件": "Pixi 実行ファイル",
    "清空打开历史": "履歴を消去",
    "清空历史": "履歴を消去",
    "清空": "クリア",
    "自动滚动": "自動スクロール",
    "全部停止": "すべて停止",
    "关闭已完成": "完了分を閉じる",
    "系统": "システム",
    "系统消息": "システムログ",
    "输出": "出力",
    "停止": "停止",
    "停止任务": "タスクを停止",
    "正在停止…": "停止中…",
    "正在停止：{}": "停止中：{}",
    "正在停止所有任务…": "すべてのタスクを停止中…",
    "运行中：{}": "実行中：{}",
    "运行中：task {}": "タスク実行中：{}",
    "Task: {}": "タスク：{}",
    "Python: {}": "Python：{}",
    "Pixi task: {}": "Pixi タスク：{}",
    "Pixi 命令": "Pixi コマンド",
    "清理环境 {}": "環境 {} をクリーン",
    "{}：{}": "{}：{}",
    "{} 完成": "{} 完了",
    "{} 已停止": "{} 停止",
    "{} 失败，退出码 {}": "{} 失敗（終了コード {}）",
    "运行任务": "タスクを実行",
    "运行任务 / 命令": "タスク / コマンドを実行",
    "运行任务：{}": "タスク実行：{}",
    "运行任务: {}": "タスク実行：{}",
    "附加参数": "追加引数",
    "参数会追加到 pixi run 命令末尾；包含空格的路径请加双引号。": "引数は pixi run の末尾に追加されます。空白を含むパスは二重引用符で囲んでください。",
    "打开 Pixi 环境": "Pixi 環境を開く",
    "可以选 pixi.toml / pyproject.toml，也可以选工作区目录。": "pixi.toml / pyproject.toml、またはワークスペースフォルダーを選択できます。",
    "最近使用的工作区也可以在顶部“最近打开”菜单中快速切换。": "最近使ったワークスペースは上部の「最近」メニューから切り替えられます。",
    "启动": "実行",
    "启动选中任务": "選択タスクを実行",
    "带参数启动…": "引数付きで実行…",
    "在终端中运行": "ターミナルで実行",
    "在终端运行": "ターミナルで実行",
    "查看详情": "詳細を表示",
    "任务详情": "タスク詳細",
    "名称": "名前",
    "命令": "コマンド",
    "工作目录": "作業ディレクトリ",
    "描述": "説明",
    "依赖": "依存関係",
    "参数定义": "引数定義",
    "有（启动时可填写参数）": "あり（実行時に指定可能）",
    "无": "なし",
    "当前环境": "現在の環境",
    "当前环境: {}": "環境：{}",
    "快速任务": "クイックタスク",
    "当前环境没有 task": "この環境にタスクはありません",
    "打开一个环境后显示可用 task": "環境を開くとタスクが表示されます",
    "Python 程序": "Python プログラム",
    "还没有用此环境运行过 Python 程序": "この環境で実行した Python プログラムはありません",
    "打开一个环境后显示运行历史": "環境を開くと実行履歴が表示されます",
    "运行（使用保存的参数）": "実行（保存した引数）",
    "编辑参数…": "引数を編集…",
    "从历史中移除": "履歴から削除",
    "移除历史": "履歴を削除",
    "脚本路径": "スクリプトパス",
    "参数": "引数",
    "按 Windows 命令行习惯填写；包含空格的路径请加双引号。": "Windows のコマンドライン形式で入力してください。空白を含むパスは二重引用符で囲みます。",
    "使用脚本目录": "スクリプトのフォルダーを使用",
    "命令预览": "コマンドプレビュー",
    "运行": "実行",
    "清空表单": "フォームをクリア",
    "运行 Python": "Python を実行",
    "程序": "プログラム",
    "命令中心": "コマンドセンター",
    "Pixi CLI 文档": "Pixi CLI ドキュメント",
    "命令帮助": "コマンドヘルプ",
    "正在加载帮助…": "ヘルプを読み込み中…",
    "手动命令": "手動コマンド",
    "自动使用当前工作区": "現在のワークスペースを使用",
    "请输入 pixi 命令。": "pixi コマンドを入力してください。",
    "（不指定）": "（指定なし）",
    "全部": "すべて",
    "全部库": "すべてのパッケージ",
    "仅用户安装": "ユーザーインストール",
    "仅用户安装 ({})": "ユーザーインストール ({})",
    "全部库 ({})": "すべてのパッケージ ({})",
    "搜索": "検索",
    "类型": "種類",
    "已安装": "インストール済み",
    "最新版本": "最新版",
    "最新": "最新",
    "版本": "バージョン",
    "状态": "状態",
    "当前环境: {}  ·  已安装 {} 个包（用户显式 {} 个）  ·  {} 个 task  ·  {} 个命名环境": "環境：{}  ·  インストール済み {} パッケージ（明示 {}）  ·  タスク {} 件  ·  環境 {} 件",
    "{} 个 task（当前环境 {}）": "タスク {} 件（環境 {}）",
    "⚠ pixi.toml 比 pixi.lock 新，锁文件可能已过期。": "⚠ pixi.toml が pixi.lock より新しく、ロックファイルが古い可能性があります。",
    "包规格 *": "パッケージ仕様 *",
    "启用": "有効",
    "仅 PyPI：以 editable 方式添加本地包。": "PyPI のみ：ローカルパッケージを editable で追加します。",
    "仅 PyPI：自定义 index URL。": "PyPI のみ：カスタム index URL。",
    "例如 win-64、linux-64；留空使用默认平台。": "例：win-64、linux-64。空欄の場合は既定のプラットフォーム。",
    "写入指定 feature，留空为 default。": "指定 feature に書き込みます。空欄は default。",
    "只写清单不安装": "マニフェストのみ（インストールなし）",
    "对应 --no-install。": "--no-install に対応。",
    "添加 pypi 依赖而不是 conda 依赖。": "conda ではなく PyPI 依存として追加します。",
    "空格分隔，例如 numpy pandas 或 numpy=2.0；PyPI 包可写 pkg==1.2。": "スペース区切り（例：numpy pandas、numpy=2.0）。PyPI は pkg==1.2 も可。",
    "要操作/使用的命名环境。": "使用・変更する名前付き環境。",
    "空格分隔的包名。": "スペース区切りのパッケージ名。",
    "只看计划（dry-run）": "計画のみ（dry-run）",
    "留空更新全部；多个包用空格分隔。": "空欄ならすべて更新。複数はスペース区切り。",
    "留空升级全部；多个包用空格分隔。": "空欄ならすべてアップグレード。複数はスペース区切り。",
    "包名 *": "パッケージ名 *",
    "严格使用 lock 文件，不更新锁文件。": "lock ファイルを厳密に使用し、更新しません。",
    "检查 lock 文件是否最新，否则失败。": "lock ファイルが最新か確認し、古い場合は失敗します。",
    "只检查是否需要更新": "確認のみ",
    "只计算不写入": "計算のみ（書き込みなし）",
    "只清理激活缓存": "アクティベーションキャッシュのみ",
    "只重装这些包；留空重装整个环境。": "指定パッケージのみ再インストール。空欄なら環境全体。",
    "所有环境": "すべての環境",
    "指定包": "指定パッケージ",
    "重新安装全部环境，忽略“环境”字段。": "「環境」フィールドを無視してすべての環境を再インストール。",
    "Task / 命令 *": "タスク / コマンド *",
    "只打印不执行": "表示のみ（実行なし）",
    "可以直接写 task 名，也可以写 python script.py 等命令。": "タスク名、または python script.py などのコマンドを入力できます。",
    "忽略当前 shell 环境变量。": "現在のシェル環境変数を無視します。",
    "跳过任务依赖": "タスク依存をスキップ",
    "Task 名称 *": "タスク名 *",
    "例如 pytest -q 或 python build.py。": "例：pytest -q、python build.py。",
    "依赖 Task": "依存タスク",
    "命令 *": "コマンド *",
    "相对于 workspace 根目录。": "ワークスペースルートからの相対パス。",
    "空格分隔的 task 名。": "スペース区切りのタスク名。",
    "空格分隔。": "スペース区切り。",
    "包含缓存和环境大小": "キャッシュと環境サイズを含める",
    "例如 win-64；留空由 Pixi 决定。": "例：win-64。空欄なら Pixi が決定します。",
    "新工作区目录，建议使用绝对路径。": "新しいワークスペースのディレクトリ。絶対パスを推奨。",
    "格式": "形式",
    "路径 *": "パス *",
    "请求约束": "要求仕様",
    "来源": "ソース",
    "大小": "サイズ",
    "包详情": "パッケージ詳細",
    "完整详情…": "完全な詳細…",
    "构建": "ビルド",
    "许可证": "ライセンス",
    "文件": "ファイル",
    "地址": "URL",
    "更新到兼容版本": "互換バージョンに更新",
    "升级到最新版本": "最新版にアップグレード",
    "查询最新版本": "最新版を確認",
    "读取失败": "読み込み失敗",
    "刷新失败": "更新失敗",
    "打开环境失败": "環境を開けませんでした",
    "需要环境": "環境が必要です",
    "请先打开一个 Pixi 环境。": "先に Pixi 環境を開いてください。",
    "请先打开环境。": "先に環境を開いてください。",
    "请先打开一个环境。": "先に環境を開いてください。",
    "请先选择一个 task。": "先にタスクを選択してください。",
    "请先选择一个或多个包。": "先にパッケージを選択してください。",
    "请填写包名。": "パッケージ名を入力してください。",
    "确定": "OK",
    "是": "はい",
    "否": "いいえ",
}


def current_language() -> str:
    return _CURRENT


def set_language(code: str) -> None:
    global _CURRENT
    code = (code or "zh").lower()
    _CURRENT = code if code in LANGUAGES else "zh"
    _clear_cache()


def language_display_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def _catalog() -> Dict[str, str]:
    if _CURRENT == "en":
        return EN
    if _CURRENT == "ja":
        return JA
    return {}


def _fallback_catalog() -> Dict[str, str]:
    if _CURRENT == "ja":
        return EN
    return {}


def _lookup(text: str) -> Optional[str]:
    catalog = _catalog()
    if text in catalog:
        return catalog[text]
    fallback = _fallback_catalog()
    return fallback.get(text)


def _format_template(template: str, values: Iterable[str]) -> str:
    values_iter = iter(values)
    pieces: List[str] = []
    try:
        parsed = string.Formatter().parse(template)
    except ValueError:
        return template
    for literal, field_name, format_spec, conversion in parsed:
        pieces.append(literal)
        if field_name is not None:
            try:
                pieces.append(next(values_iter))
            except StopIteration:
                pieces.append("")
    return "".join(pieces)


_TEMPLATE_CACHE: List[Tuple[str, re.Pattern, str]] = []
_PREFIX_CACHE: List[Tuple[str, str]] = []
_CACHE_LANG: Optional[str] = None


def _clear_cache() -> None:
    global _CACHE_LANG
    _TEMPLATE_CACHE.clear()
    _PREFIX_CACHE.clear()
    _CACHE_LANG = None


def _build_cache() -> None:
    global _CACHE_LANG
    if _CACHE_LANG == _CURRENT:
        return
    _TEMPLATE_CACHE.clear()
    _PREFIX_CACHE.clear()
    catalog = _catalog()
    fallback = _fallback_catalog()
    for source, translated in list(catalog.items()) + [
        (key, value) for key, value in fallback.items() if key not in catalog
    ]:
        if "{" in source:
            try:
                parsed = list(string.Formatter().parse(source))
            except ValueError:
                continue
            pattern_parts: List[str] = ["^"]
            for literal, field_name, _spec, _conversion in parsed:
                pattern_parts.append(re.escape(literal))
                if field_name is not None:
                    pattern_parts.append("(.*?)")
            pattern_parts.append("$")
            try:
                regex = re.compile("".join(pattern_parts), re.DOTALL)
            except re.error:
                continue
            _TEMPLATE_CACHE.append((source, regex, translated))
        elif source.endswith(("：", ":", "： ", ": ", " ", "…")):
            _PREFIX_CACHE.append((source, translated))
    _TEMPLATE_CACHE.sort(key=lambda item: len(item[0]), reverse=True)
    _PREFIX_CACHE.sort(key=lambda item: len(item[0]), reverse=True)
    _CACHE_LANG = _CURRENT


def translate_dynamic(text: str) -> str:
    if not text or _CURRENT == "zh":
        return text
    _build_cache()
    direct = _lookup(text)
    if direct is not None:
        return direct
    if text.startswith("⚠ "):
        return "⚠ " + translate_dynamic(text[2:])
    for _source, regex, translated in _TEMPLATE_CACHE:
        match = regex.match(text)
        if match:
            return _format_template(translated, match.groups())
    for source, translated in _PREFIX_CACHE:
        if text.startswith(source):
            return translated + text[len(source) :]
    return text


def t(text: str, *args: Any, **kwargs: Any) -> str:
    translated = translate_dynamic(text)
    if args or kwargs:
        try:
            return translated.format(*args, **kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


def localize_widget_tree(widget: tk.Misc) -> None:
    if _CURRENT == "zh":
        return
    _localize(widget)


def _localize(widget: tk.Misc) -> None:
    try:
        if isinstance(widget, tk.Menu):
            _localize_menu(widget)
        elif isinstance(widget, ttk.Notebook):
            for tab_id in widget.tabs():
                try:
                    text = widget.tab(tab_id, "text")
                    translated = translate_dynamic(str(text))
                    if translated != text:
                        widget.tab(tab_id, text=translated)
                except tk.TclError:
                    pass
        elif isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                try:
                    text = widget.heading(column, "text")
                    translated = translate_dynamic(str(text))
                    if translated != text:
                        widget.heading(column, text=translated)
                except tk.TclError:
                    pass
        elif isinstance(widget, (tk.Toplevel, tk.Tk)):
            try:
                title = widget.title()
                translated = translate_dynamic(title)
                if translated != title:
                    widget.title(translated)
            except tk.TclError:
                pass
    except tk.TclError:
        pass

    if not isinstance(widget, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Listbox)):
        try:
            keys = widget.keys()
        except (tk.TclError, AttributeError):
            keys = []
        if "text" in keys:
            try:
                text = widget.cget("text")
                translated = translate_dynamic(str(text))
                if translated != text:
                    widget.configure(text=translated)
            except tk.TclError:
                pass
        if "textvariable" in keys and not isinstance(widget, (ttk.Treeview,)):
            try:
                var_name = widget.cget("textvariable")
                if var_name:
                    value = widget.getvar(var_name)
                    if value is not None:
                        translated = translate_dynamic(str(value))
                        if translated != str(value):
                            widget.setvar(var_name, translated)
            except tk.TclError:
                pass

    try:
        for child in widget.winfo_children():
            _localize(child)
    except tk.TclError:
        pass


def _localize_menu(menu: tk.Menu) -> None:
    try:
        end = menu.index("end")
    except tk.TclError:
        return
    if end is None:
        return
    for index in range(end + 1):
        try:
            label = menu.entrycget(index, "label")
        except tk.TclError:
            continue
        translated = translate_dynamic(str(label))
        if translated != label:
            try:
                menu.entryconfigure(index, label=translated)
            except tk.TclError:
                pass


def localize_menu(menu: tk.Menu) -> None:
    if _CURRENT != "zh":
        _localize_menu(menu)


def install_messagebox_translation() -> None:
    """Translate standard message-box titles/messages without touching callers."""
    if getattr(messagebox, "_pixi_i18n_installed", False):
        return
    originals = {
        "showinfo": messagebox.showinfo,
        "showwarning": messagebox.showwarning,
        "showerror": messagebox.showerror,
        "askyesno": messagebox.askyesno,
        "askyesnocancel": messagebox.askyesnocancel,
        "askokcancel": messagebox.askokcancel,
        "askquestion": messagebox.askquestion,
    }

    def wrap(original):
        def wrapped(title=None, message=None, *args, **kwargs):
            if title is not None:
                title = translate_dynamic(str(title))
            if message is not None:
                message = translate_dynamic(str(message))
            return original(title, message, *args, **kwargs)

        return wrapped

    for name, original in originals.items():
        setattr(messagebox, name, wrap(original))
    messagebox._pixi_i18n_installed = True  # type: ignore[attr-defined]


def untranslated_static_texts(root: tk.Misc) -> List[str]:
    """Development helper: list visible strings still containing Chinese."""
    found: List[str] = []

    def visit(widget: tk.Misc) -> None:
        if isinstance(widget, tk.Menu):
            try:
                end = widget.index("end")
            except tk.TclError:
                end = None
            if end is not None:
                for index in range(end + 1):
                    try:
                        label = str(widget.entrycget(index, "label"))
                    except tk.TclError:
                        continue
                    if _has_cjk(label):
                        found.append(label)
        elif isinstance(widget, ttk.Notebook):
            for tab_id in widget.tabs():
                try:
                    label = str(widget.tab(tab_id, "text"))
                    if _has_cjk(label):
                        found.append(label)
                except tk.TclError:
                    pass
        elif isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                try:
                    label = str(widget.heading(column, "text"))
                    if _has_cjk(label):
                        found.append(label)
                except tk.TclError:
                    pass
        elif isinstance(widget, (tk.Toplevel, tk.Tk)):
            try:
                title = widget.title()
                if _has_cjk(title):
                    found.append(title)
            except tk.TclError:
                pass

        if not isinstance(widget, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Listbox)):
            try:
                keys = widget.keys()
            except (tk.TclError, AttributeError):
                keys = []
            if "text" in keys:
                try:
                    text = str(widget.cget("text"))
                    if _has_cjk(text):
                        found.append(text)
                except tk.TclError:
                    pass
            if "textvariable" in keys:
                try:
                    var_name = widget.cget("textvariable")
                    if var_name:
                        value = widget.getvar(var_name)
                        if value is not None and _has_cjk(str(value)):
                            found.append(str(value))
                except tk.TclError:
                    pass
        for child in widget.winfo_children():
            visit(child)

    visit(root)
    return sorted(set(found))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
