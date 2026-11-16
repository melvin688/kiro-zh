# 变更记录

## 0.3.0 — 2026-11-16

- 额度补丁增加版本自适应回退：精确串失配时，改按稳定文案与接口字段定位，在函数体窗口内用正则改写「赠送 / 超额 / 主额度」三处模板。
- 主额度分支就地插入百分比与十格进度条，不新增外层变量，避免与压缩作用域冲突。
- 找不到锚点则原样返回并记一条「未命中」，不会把文件改坏。
- 新增 3 条单测：换符号名可命中、幂等、无锚点不动；CI 用例 6 → 9。

## 0.2.1 — 2026-11-16

- 补译聊天面板：`See all`、`(optional)`、`New Session`、`Plan` 及其描述、响应风格 `Default`。
- 重启步骤除 `clp` 外一并清理 `Cache` / `Code Cache` / `GPUCache`，避免 webview 继续用旧 bundle。
- README 增加实机截图（空项目截取，无个人信息）。
- 新增 `scripts/io_util.py`：所有写文件走 `with`，避免写完立刻重启时缓冲未落盘。
- 新增 `tests/test_core.py`（6 条离线用例）并接入 CI。

## 0.2.0 — 2026-11-16

- 新增 `asar_tool.py`：解析 `node_modules.asar` 头部、列出条目里的可见文案、对指定条目做**等长字节替换**（中文短则补空格，保证 asar 结构不变）。
- 欢迎页 / 登录页（`@kiro/sign-in-page`）6 条文案汉化：`An agentic IDE…`、`Get started`、`Open a project`、`Recent projects`、`Clone repository`、`Connect to`。
- `apply.py` 增加第 2 步「欢迎页（asar）」，`verify.py` 增加 asar 文案检查。
- 修复扩展清单汉化每次都判为「已改」的计数问题（值相同不再写入）。

## 0.1.0 — 2026-11-16

首个可用版本，基于 Kiro 1.4.178（内嵌 VS Code 1.131.0）实测。

新增：
- `apply.py` 一键流程：界面汉化 → NLS 烘焙 → 校验值回填 → 清缓存 → 重启。
- `patch_ui.py`：菜单、聊天面板、权限模式、内置模式、规格入口、状态栏、沙箱、额度百分比与进度条、行距密度、扩展清单（视图名 / 命令标题 / 设置项说明与枚举说明）。
- `localize_nls.py`：把语言包中文按内容烘焙进 `out/nls.messages.json` 与 `out/nls.messages.js`（覆盖 96%+ 核心字符串），并清理 `clp` 缓存。
- `fix_checksums.py`：重算 `product.json` 的 `checksums`，消除「安装似乎损坏」。
- `translate_missing.py`：导出语言包缺失条目为分块，合并译文并校验占位符。
- `restore.py` / `verify.py`：回滚与冒烟验收。

已知限制：
- 额度百分比补丁依赖具体 minified 符号，换版本可能未命中（会提示，不影响其它汉化）。
- `3 tool calls`、模型生成的会话标题属后端文本，需靠 steering 约束。
- 仅 Windows。
