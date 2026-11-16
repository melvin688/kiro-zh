# -*- coding: utf-8 -*-
"""Kiro 界面汉化：把自绘 UI 里的英文字面量替换成中文。

只动展示用字符串，不碰逻辑；每个文件首次改写前生成同名 .zhbak 备份。
可重复执行：已经替换过的条目会跳过。

用法：
    python scripts/patch_ui.py --app <resources/app> [--dry-run]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
from pathlib import Path

from kiro_paths import (
    chat_assets,
    chat_dist,
    enable_utf8,
    find_app_root,
    kiro_agent_dir,
    session_assets,
    session_dist,
)

# ---------------------------------------------------------------- 替换工具

REPORT: list[tuple[str, str, int, int]] = []  # (状态, 文件, 替换数, 未命中数)


def _backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".zhbak")
    if not bak.exists():
        shutil.copy2(path, bak)


def patch_text(path: Path, pairs: list[tuple[str, str]], label: str | None = None) -> int:
    """按顺序替换字面量；new 已存在视为已打过，old 缺失记为未命中。"""
    name = label or path.name
    if not path.exists():
        REPORT.append(("缺文件", name, 0, 0))
        return 0
    text = io.open(path, encoding="utf-8", errors="surrogateescape").read()
    orig = text
    done = miss = 0
    for old, new in pairs:
        if new and new in text:
            continue
        if old in text:
            n = text.count(old)
            text = text.replace(old, new)
            done += n
        else:
            miss += 1
    if text != orig:
        _backup(path)
        io.open(path, "w", encoding="utf-8", errors="surrogateescape", newline="").write(text)
    REPORT.append(("已改" if text != orig else "无变化", name, done, miss))
    return done


def patch_json(path: Path, mutate, label: str | None = None) -> int:
    """mutate(doc) -> 改动计数；为 0 时不落盘。"""
    name = label or path.name
    if not path.exists():
        REPORT.append(("缺文件", name, 0, 0))
        return 0
    doc = json.load(io.open(path, encoding="utf-8"))
    n = mutate(doc)
    if n:
        _backup(path)
        io.open(path, "w", encoding="utf-8", newline="").write(
            json.dumps(doc, ensure_ascii=False, indent=2)
        )
    REPORT.append(("已改" if n else "无变化", name, n, 0))
    return n


def patch_all_bundles(folders: list[Path], pairs: list[tuple[str, str]], prefix: str = "mermaid-") -> None:
    for folder in folders:
        if not folder.is_dir():
            continue
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.name.startswith(prefix) and f.suffix == ".js":
                patch_text(f, pairs)


# ---------------------------------------------------------------- 顶部菜单

MENU_MAP = {
    "File": "文件",
    "Edit": "编辑",
    "Selection": "选择",
    "View": "查看",
    "Go": "转到",
    "Help": "帮助",
    "Preferences": "首选项",
    "Terminal": "终端",
}


def patch_menus(app: Path) -> None:
    pairs = [
        (f'title:{{value:"{en}",original:"{en}",', f'title:{{value:"{zh}",original:"{zh}",')
        for en, zh in MENU_MAP.items()
    ]
    for rel in ("out/vs/workbench/workbench.desktop.main.js", "out/vs/sessions/sessions.desktop.main.js"):
        patch_text(app / Path(*rel.split("/")), pairs, label=rel.split("/")[-1])


# ---------------------------------------------------------------- 聊天面板

CHAT_LITERALS = [
    # 输入区 / 空状态
    ('const uve="When Kiro wants to act"', 'const uve="当 Kiro 要执行操作时"'),
    ('const gEe="Ask a question or describe a task..."', 'const gEe="提问或描述任务..."'),
    ('"Ask a question or describe a task..."', '"提问或描述任务..."'),
    ('"Let\'s build"', '"开始构建"'),
    ('"Plan, search, or build anything"', '"规划、检索，或构建任何内容"'),
    ('"Select Model"', '"选择模型"'),
    ('"Start with a built-in agent"', '"从内置 agent 开始"'),
    ('"Message this step\'s agent"', '"给这一步的 agent 发消息"'),
    # 权限模式
    ('{supervised:{label:"Supervised",gloss:"Kiro pauses after each turn that edits files so you can '
     'accept or reject each change."},autopilot:{label:"Accept file changes",gloss:"Kiro creates, edits, '
     'and deletes files without asking. It asks before it runs commands."},approveForMe:{label:'
     '"Approve for me",gloss:"For actions your rules don\'t cover, a model approves ones deemed safe, '
     'blocks ones deemed unsafe, and asks you when it\'s unsure."}}',
     '{supervised:{label:"逐项确认",gloss:"Kiro 每次改动文件后都会暂停，由你接受或拒绝。"},'
     'autopilot:{label:"自动接受文件修改",gloss:"Kiro 直接创建、修改、删除文件，不再询问；执行命令前仍会确认。"},'
     'approveForMe:{label:"自动批准",gloss:"你的规则没覆盖的操作由模型判断：安全的自动放行，不安全的拦下，拿不准时问你。"}}'),
    # 用量 / 产物
    ('"Elapsed time: "', '"耗时："'),
    ('"Est. Credits Used: "', '"预估消耗积分："'),
    ('"Est. Credits Used"', '"预估消耗积分"'),
    ('{workflows:"Workflows",artifacts:"Artifacts"}', '{workflows:"工作流",artifacts:"产物"}'),
    ('children:"Artifacts"', 'children:"产物"'),
    ('label:"Artifacts"', 'label:"产物"'),
    ('title:"Artifacts"', 'title:"产物"'),
    ('"aria-label":"Artifacts"', '"aria-label":"产物"'),
    # 步骤与检查点
    ('"View changes ("', '"查看更改 ("'),
    ('"Revert changes ("', '"还原更改 ("'),
    ('"Reverting..."', '"正在还原..."'),
    ('"Thinking":"Thought complete"', '"思考中":"思考完成"'),
    ('?"file changed":"files changed"', '?"个文件已更改":"个文件已更改"'),
    ('"Cannot restore while the agent is working"', '"agent 正在工作时无法还原"'),
    ('children:"Checkpoint"', 'children:"检查点"'),
    ('"See all"', '"查看全部"'),
    ('children:"(optional)"', 'children:"（可选）"'),
    ('children:"Restore"', 'children:"还原"'),
    ('"aria-label":"Restore"', '"aria-label":"还原"'),
    ('"Included Steering"', '"生效的 Steering"'),
]

# 权限模式还有一处独立定义，标签单独出现
HOST_CAPABILITY_LITERALS = [
    ('supervised:{label:"Supervised",locksMode:!1,locksModel:!1}',
     'supervised:{label:"逐项确认",locksMode:!1,locksModel:!1}'),
    ('autopilot:{label:"Autopilot",locksMode:!1,locksModel:!1}',
     'autopilot:{label:"自动接受文件修改",locksMode:!1,locksModel:!1}'),
    ('approveForMe:{label:"Approve for me",locksMode:!1,locksModel:!1}',
     'approveForMe:{label:"自动批准",locksMode:!1,locksModel:!1}'),
    ('autonomous:{label:"Autonomous",locksMode:!0,locksModel:!0}',
     'autonomous:{label:"自主执行",locksMode:!0,locksModel:!0}'),
]


def patch_chat(app: Path) -> None:
    patch_all_bundles([chat_assets(app), session_assets(app)], CHAT_LITERALS)
    for f in chat_assets(app).glob("HostCapabilitiesProvider-*.js"):
        patch_text(f, HOST_CAPABILITY_LITERALS)


# ---------------------------------------------------------------- 扩展宿主

# 1.4.178 实测的额度文案函数；版本变动后此处可能未命中，属预期
QUOTA_OLD = (
    'function Zug(e,t){let{currency:n,currentOverages:r,currentUsage:o,freeTrialUsage:s,'
    'overageCharges:a,usageLimit:l}=t,u=y7l(e);return s&&s.currentUsage<s.usageLimit?'
    '`${u} Bonus ${s.currentUsage} / ${s.usageLimit} (${s.daysRemaining} days left)`:'
    'r>0||a>0?`${u} Overage ${r} (${n.symbol}${a.toFixed(2)})`:`${u} ${o} / ${l}`}'
)
QUOTA_NEW = (
    'function Zug(e,t){let{currency:n,currentOverages:r,currentUsage:o,freeTrialUsage:s,'
    'overageCharges:a,usageLimit:l}=t,u=y7l(e);'
    'let pc=l>0?Math.min(100,Math.round(o/l*100)):0,'
    'full=Math.max(0,Math.min(10,Math.round(pc/10))),'
    'mk=()=>"\\u25B0".repeat(full)+"\\u25B1".repeat(10-full),'
    'tag=mk()+" "+pc+"%";'
    'return s&&s.currentUsage<s.usageLimit?'
    '`${u} 赠送 ${s.currentUsage} / ${s.usageLimit}（剩 ${s.daysRemaining} 天）`:'
    'r>0||a>0?`${u} 超额 ${r}（${n.symbol}${a.toFixed(2)}）· ${tag} · ${o} / ${l}`:'
    '`${u} ${tag} · ${o} / ${l}`}'
)

EXT_LITERALS = [
    # 相对时间 / 抓取时间
    ('return r<1?"just now":r<60?`${r}m ago`:o<24?`${o}h ago`:`${Math.floor(o/24)}d ago`',
     'return r<1?"刚刚":r<60?`${r} 分钟前`:o<24?`${o} 小时前`:`${Math.floor(o/24)} 天前`'),
    ('`${l} updated ${Xug(r)}`', '`${l} 更新于 ${Xug(r)}`'),
    # 额度项
    ('y7l("Open account dashboard")', 'y7l("打开账户面板")'),
    ('Vug="Open account dashboard"', 'Vug="打开账户面板"'),
    ('"Usage Meter"', '"额度"'),
    # 内置模式
    ('{id:s2r,name:"Default",description:"Use Kiro\'s standard response style."}',
     '{id:s2r,name:"默认",description:"使用 Kiro 的标准回答风格。"}'),
    ('"New Session"', '"新会话"'),
    ('name:"Plan",description:r.description', 'name:"计划",description:r.description'),
    ('Szf="Plan-only mode that helps break ideas down into an implementation plan without making any changes"',
     'Szf="只做计划的模式：把想法拆成实现方案，不改动任何代码"'),
    ('Ezf="Transform any idea into fully working code. What do you want to build today?"',
     'Ezf="把任何想法变成可运行的代码。今天想构建什么？"'),
    ('[{id:"vibe",name:"Default",description:"General coding assistance",mcpServers:t},'
     '{id:"spec",name:"Spec",description:"Structured feature development",mcpServers:t},'
     '{id:"quick-spec",name:"Quick Spec",description:"Fast spec workflow: clarify, then auto-generate '
     'requirements, design, and tasks",mcpServers:t},'
     '{id:"bug-fix",name:"Bug Fix",description:"Structured bug-fix workflow: investigate, diagnose, and '
     'resolve bugs",mcpServers:t},',
     '[{id:"vibe",name:"默认",description:"通用编码协助",mcpServers:t},'
     '{id:"spec",name:"规格",description:"结构化的功能开发流程",mcpServers:t},'
     '{id:"quick-spec",name:"快速规格",description:"快速规格流程：先澄清，再自动生成需求、设计和任务",mcpServers:t},'
     '{id:"bug-fix",name:"缺陷修复",description:"结构化缺陷流程：调查、定位、修复",mcpServers:t},'),
    ('{id:"autonomous",name:"Autonomous",description:"Autonomous agent execution"',
     '{id:"autonomous",name:"自主执行",description:"自主运行的 agent 执行"'),
    ('{id:noe,name:"Default v2",description:"Adaptive agent that plans, delegates, and verifies as the '
     'task demands"',
     '{id:noe,name:"默认 v2",description:"按任务需要自适应地规划、委派和验证的 agent"'),
    # 规格入口
    ('{title:"Fix a Bug",description:"Fix something that\'s broken, crashing, or not working correctly"}',
     '{title:"修一个缺陷",description:"修掉坏掉、崩溃或行为不正确的地方"}'),
    ('{title:"Build a Feature",description:"Implement new functionality or capabilities that don\'t exist yet"}',
     '{title:"做一个功能",description:"实现目前还不存在的新功能或能力"}'),
    ('{title:"Quick Spec",description:"Auto-generate requirements and design without review"}',
     '{title:"快速规格",description:"不经审阅，自动生成需求和设计"}'),
    ('{title:"Requirements",description:"Begin by gathering and documenting requirements"}',
     '{title:"需求",description:"先收集并记录需求"}'),
    ('{title:"Technical Design",description:"Begin with the technical design, then derive requirements from '
     'that design"}',
     '{title:"技术设计",description:"先做技术设计，再从设计推导需求"}'),
    ('{title:"Verify First",description:"Formally verify requirements for consistency and completeness '
     'before generating tasks"}',
     '{title:"先验证",description:"生成任务前，先正式校验需求的一致性和完整性"}'),
    # 状态栏
    ('jug="$(bug) Report issue"', 'jug="$(bug) 报告问题"'),
    ('`Report a bug or submit feedback to the ${V6e} team`',
     '`向 ${V6e} 团队报告缺陷或提交反馈`'),
    ('"$(circle-slash) Autocomplete"', '"$(circle-slash) 自动补全"'),
    ('"$(check) Autocomplete"', '"$(check) 自动补全"'),
    ('"$(debug-pause) Autocomplete"', '"$(debug-pause) 自动补全"'),
    ('"Click to enable tab autocomplete"', '"点击启用 Tab 自动补全"'),
    ('"Tab autocomplete is enabled"', '"Tab 自动补全已启用"'),
    ('"Tab autocomplete is paused"', '"Tab 自动补全已暂停"'),
    # 沙箱
    ('"$(shield) Sandbox: Off"', '"$(shield) 沙箱：关闭"'),
    ('"Commands run with your full permissions. Click to configure."',
     '"命令以你的完整权限运行。点击配置。"'),
    ('"$(sync~spin) Sandbox: Applying\\u2026"', '"$(sync~spin) 沙箱：应用中\\u2026"'),
    ('"$(warning) Sandbox: Error"', '"$(warning) 沙箱：出错"'),
    ('`Sandbox initialization failed: ${this.currentStatus.message}',
     '`沙箱初始化失败：${this.currentStatus.message}'),
]


def patch_extension(app: Path) -> None:
    ext = kiro_agent_dir(app) / "dist" / "extension.js"
    patch_text(ext, [(QUOTA_OLD, QUOTA_NEW)], label="extension.js(额度)")
    patch_text(ext, EXT_LITERALS, label="extension.js")


# ---------------------------------------------------------------- 扩展清单

VIEW_TITLES = {
    "Chat": "聊天",
    "Workflows": "工作流",
    "Memories": "记忆",
    "ACP Debug": "ACP 调试",
    "ACP Inspector": "ACP 检查器",
    "Specs": "规格",
    "Safety Properties": "安全属性",
    "Sandboxes": "沙箱",
    "Workflow Runs": "工作流运行",
    "Recipes": "配方",
}

SETTING_DESC = {
    "kiroAgent.markdownReview.extensionRendering":
        "在「审查 Markdown」中使用已安装的 Markdown 渲染扩展。关闭后改用 Kiro 自带的本地渲染器。",
    "kiroAgent.experiments": "Kiro 实验功能开关状态",
    "kiroAgent.terminalCommandTimeout":
        "agent 运行的终端命令的默认超时（毫秒）。agent 未单独指定超时时使用此值。最小 1000 毫秒，"
        "超过 1800000 的按 1800000 处理。未设置时用 agent 内置默认值（120000），仅对本地会话生效。",
    "kiroAgent.toolCardDisplayMode":
        "控制聊天里的工具卡片在工具执行完毕后的表现：「完成后折叠」自动收起，「始终展开」保持展开。",
    "kiroAgent.artifacts.autoOpenPanel":
        "Kiro 产出产物时自动打开产物面板。关闭后新产物仍会加入面板，但需要自己打开。",
    "kiroAgent.feedback.inlineSurvey": "不定期在聊天里用简短问卷询问使用体验。关闭后不再显示问卷。",
    "kiroAgent.workflows.enabled":
        "允许 agent 在会话中创建并运行多步工作流。关闭后 agent 不会启动新工作流，已有工作流和配方仍可用。",
    "kiroAgent.trust.defaultPattern":
        "对 shell 命令选择「始终允许」/「始终拒绝」时，预选的命令匹配范围。每次询问时仍可更改。",
    "kiroAgent.trust.defaultScope":
        "选择「始终允许」/「始终拒绝」时，预选的作用范围。每次询问时仍可更改。",
    "kiroAgent.editorActions.prompts":
        "Kiro 编辑器右键菜单动作的自定义提示词。每项会替换该动作的内置提示词。",
}

REMOTE_DESC = {
    "kiroRemote.serverDownloadUrlTemplate": "下载远端 Kiro 服务的 URL 模板，覆盖产品默认值。",
    "kiroRemote.httpProxy": "为下载和启动远端 Kiro 服务设置 `http_proxy` 环境变量。需重启执行环境生效。",
    "kiroRemote.httpsProxy": "为下载和启动远端 Kiro 服务设置 `https_proxy` 环境变量。需重启执行环境生效。",
}

ENUM_DESC = {
    "Collapse a tool card automatically once it finishes (default).": "工具卡片执行完毕后自动折叠（默认）。",
    "Keep tool cards expanded after they complete or error.": "工具卡片完成或报错后保持展开。",
    "Trust the exact command (e.g. `npm run test`).": "信任完全相同的命令（如 `npm run test`）。",
    "Trust the command and its first argument (e.g. `npm run *`).": "信任该命令及其第一个参数（如 `npm run *`）。",
    "Trust the base command (e.g. `npm *`).": "信任基础命令（如 `npm *`）。",
    "All workspaces (persisted to your user permissions).": "所有工作区（写入用户级权限）。",
    "This workspace folder only (the folder the request applies to).": "仅当前工作区文件夹。",
    "This session only (not persisted to disk).": "仅当前会话（不写入磁盘）。",
}


def _mutate_agent_manifest(doc) -> int:
    cont = doc.get("contributes", {})
    n = 0
    for group in cont.get("viewsContainers", {}).values():
        for item in group:
            if item.get("title") in VIEW_TITLES:
                item["title"] = VIEW_TITLES[item["title"]]
                n += 1
    for group in cont.get("views", {}).values():
        for item in group:
            if item.get("name") in VIEW_TITLES:
                item["name"] = VIEW_TITLES[item["name"]]
                n += 1
    for cmd in cont.get("commands", []):
        if cmd.get("title") == "Review Markdown":
            cmd["title"] = "审查 Markdown"
            n += 1
    cfg = cont.get("configuration")
    blocks = [cfg] if isinstance(cfg, dict) else (cfg or [])
    for block in blocks:
        for key, zh in SETTING_DESC.items():
            node = (block.get("properties") or {}).get(key)
            if not node:
                continue
            for field in ("markdownDescription", "description"):
                if field in node and node[field] != zh:
                    node[field] = zh
                    n += 1
        for node in (block.get("properties") or {}).values():
            for i, desc in enumerate(node.get("enumDescriptions") or []):
                if desc in ENUM_DESC and desc != ENUM_DESC[desc]:
                    node["enumDescriptions"][i] = ENUM_DESC[desc]
                    n += 1
    return n


def _mutate_remote_manifest(doc) -> int:
    cont = doc.get("contributes", {})
    cfg = cont.get("configuration")
    blocks = [cfg] if isinstance(cfg, dict) else (cfg or [])
    n = 0
    for block in blocks:
        for key, zh in REMOTE_DESC.items():
            node = (block.get("properties") or {}).get(key)
            if not node:
                continue
            for field in ("markdownDescription", "description"):
                if field in node and node[field] != zh:
                    node[field] = zh
                    n += 1
    return n


def patch_manifests(app: Path) -> None:
    patch_json(app / "extensions" / "kiro.kiro-agent" / "package.json", _mutate_agent_manifest,
               label="kiro-agent/package.json")
    patch_json(app / "extensions" / "kiro-remote" / "package.json", _mutate_remote_manifest,
               label="kiro-remote/package.json")


# ---------------------------------------------------------------- 行距/密度

DENSITY_CSS = """
/* ==== kiro-zh-density ==== */
body { line-height: 1.75; }
.agent-message-markdown, .kiro-chat-message-markdown, .agent-message-body { line-height: 1.75; }
.agent-message-markdown p, .kiro-chat-message-markdown p, .agent-message-body p { margin-block: 0; line-height: 1.75; }
.agent-message-markdown > * + *, .kiro-chat-message-markdown > * + * { margin-top: 14px; }
.agent-message-markdown li, .kiro-chat-message-markdown li { margin-block: .35em; }
.agent-message-markdown ul, .agent-message-markdown ol { display: flex; flex-direction: column; gap: .3em; }
"""


def patch_density(app: Path) -> None:
    for css in (chat_dist(app) / "style.css", session_dist(app) / "style.css"):
        if not css.exists():
            REPORT.append(("缺文件", f"{css.parent.name}/style.css", 0, 0))
            continue
        text = io.open(css, encoding="utf-8", errors="surrogateescape").read()
        if "kiro-zh-density" in text:
            REPORT.append(("无变化", f"{css.parent.name}/style.css", 0, 0))
            continue
        _backup(css)
        with io.open(css, "a", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(DENSITY_CSS)
        REPORT.append(("已改", f"{css.parent.name}/style.css", 1, 0))


# ---------------------------------------------------------------- 入口

def run(app: Path, dry_run: bool = False) -> list[tuple[str, str, int, int]]:
    REPORT.clear()
    if dry_run:
        print(f"[dry-run] 目标：{app}")
        for rel in ("out/vs/workbench/workbench.desktop.main.js", "extensions/kiro.kiro-agent/dist/extension.js"):
            print(f"[dry-run] {'找到' if (app / Path(*rel.split('/'))).exists() else '缺失'} {rel}")
        return REPORT
    patch_menus(app)
    patch_chat(app)
    patch_extension(app)
    patch_manifests(app)
    patch_density(app)
    return REPORT


def main() -> None:
    enable_utf8()
    ap = argparse.ArgumentParser(description="Kiro 界面汉化（字面量直替换）")
    ap.add_argument("--app", help="Kiro 的 resources/app 目录，留空自动探测")
    ap.add_argument("--dry-run", action="store_true", help="只检查路径，不写文件")
    args = ap.parse_args()

    app = find_app_root(args.app)
    rows = run(app, args.dry_run)
    if args.dry_run:
        return
    width = max(len(r[1]) for r in rows) if rows else 10
    for status, name, done, miss in rows:
        print(f"{status:<4} {name:<{width}}  替换 {done:>3}  未命中 {miss:>3}")
    quota = next((r for r in rows if r[1] == "extension.js(额度)"), None)
    if quota and quota[3]:
        print("提示：额度百分比补丁未命中（Kiro 版本可能已变），其余汉化不受影响。")


if __name__ == "__main__":
    main()
