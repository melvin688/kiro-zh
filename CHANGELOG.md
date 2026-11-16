# 变更记录

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
