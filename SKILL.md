---
name: kiro-zh
description: Use when 汉化 Kiro IDE 界面或修 Kiro 中文显示问题。
---

# Kiro 汉化

把 Kiro 自绘 UI 改成简体中文，或在 Kiro 升级后恢复汉化。项目位置：`D:\PSB\项目\Skills\kiro 汉化`。

## 什么时候用

- 用户要求「把 Kiro 汉化」「界面还是英文」「设置里的说明是英文」。
- Kiro 升级后中文消失、额度百分比消失。
- Kiro 弹「安装似乎损坏」。

## 三层来源，别只改一处

1. 语言包 `~/.kiro/extensions/ms-ceintl.vscode-language-pack-zh-hans-*/translations/main.i18n.json` —— 只管按「模块 + key」取文案的代码。
2. NLS 数组 `resources/app/out/nls.messages.json` —— workbench/sessions 渲染进程读的扁平数组，必须把中文烘焙进去，且要删 `%APPDATA%/Kiro/clp` 缓存才生效。
3. minified bundle 里的字面量 —— 聊天面板、权限模式、额度文案、状态栏，只能按内容替换。
4. `node_modules.asar` 里的欢迎页/登录页 —— 容器里的文件必须**等长**替换（用 `asar_tool.py`），改长度会破坏 asar。

## 操作

```bash
python scripts/apply.py --dry-run          # 先看路径对不对
python scripts/apply.py                    # 汉化并重启
python scripts/restore.py --restore        # 回滚
python scripts/verify.py                   # 验收
```

## 铁律

- 每个文件首次改写前必须有 `.zhbak` 备份，没有备份不动手。
- 改过 `out/` 下被校验的文件，必须跑 `fix_checksums.py`，否则用户会看到「安装似乎损坏」。
- NLS 数组**按内容替换**，不要按索引写：sessions 与 workbench 的数组顺序不一致，按索引会串行错位。
- 只替换展示字符串，不碰逻辑、不碰 key 名、不碰配置键。
- Kiro 升级后所有补丁失效属预期，先重跑 `apply.py`，不要重新发明流程。

## 已知残留

`3 tool calls`、模型生成的会话标题属后端文本，本地改不了；用 `assets/steering/zh-ui.md` 作为全局 steering 让模型输出中文标题。
