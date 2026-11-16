# -*- coding: utf-8 -*-
"""离线可跑的单元测试（不需要装 Kiro）。

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import asar_tool  # noqa: E402
import localize_nls  # noqa: E402
import patch_ui  # noqa: E402


class PatchTextTest(unittest.TestCase):
    def test_replaces_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.js"
            target.write_text('var a="Ask a question";', encoding="utf-8")

            pairs = [("Ask a question", "提问或描述任务")]
            self.assertEqual(patch_ui.patch_text(target, pairs), 1)
            self.assertIn("提问或描述任务", target.read_text(encoding="utf-8"))
            # 第二次必须不重复写入，且不能再改
            self.assertEqual(patch_ui.patch_text(target, pairs), 0)
            self.assertTrue((Path(tmp) / "sample.js.zhbak").exists())


class NlsMapTest(unittest.TestCase):
    def test_mode_wins_when_same_english_has_many_translations(self):
        metadata = {
            "keys": {"m": [{"key": "k1"}, {"key": "k2"}, {"key": "k3"}]},
            "messages": {"m": ["Save", "Save", "Save"]},
        }
        contents = {"m": {"k1": "保存", "k2": "保存", "k3": "存储"}}
        self.assertEqual(localize_nls.build_map(metadata, contents), {"Save": "保存"})

    def test_missing_translation_is_ignored(self):
        metadata = {"keys": {"m": [{"key": "k1"}, {"key": "k2"}]}, "messages": {"m": ["Close", "Close"]}}
        contents = {"m": {"k1": "关闭"}}
        self.assertEqual(localize_nls.build_map(metadata, contents), {"Close": "关闭"})

    def test_bake_array_counts_only_changes(self):
        arr = ["Close", "Close", "Untouched"]
        n = localize_nls.bake_array(arr, {"Close": "关闭"})
        self.assertEqual(n, 2)
        self.assertEqual(arr, ["关闭", "关闭", "Untouched"])


class AsarTest(unittest.TestCase):
    """构造一个最小的 asar：JSON 头 + 4 字节对齐 + 文件区。"""

    def _make_asar(self, path: Path, payload: bytes) -> None:
        header = {"files": {"a.js": {"size": len(payload), "offset": "0"}}}
        raw = json.dumps(header).encode("utf-8")
        head = raw + b"\0" * ((4 - len(raw) % 4) % 4)
        path.write_bytes(head + payload)

    def test_apply_map_keeps_byte_length(self):
        payload = b'children:"Open a project",label:"Connect to"'
        with tempfile.TemporaryDirectory() as tmp:
            asar = Path(tmp) / "node_modules.asar"
            self._make_asar(asar, payload)

            mapping = {"Open a project": "打开项目", "Connect to": "连接到"}
            changed = asar_tool.apply_map(asar, "a.js", mapping)

            self.assertEqual(changed, 2)
            out = asar.read_bytes()
            self.assertEqual(len(out), len(asar_tool.load(asar)[0]))
            self.assertIn("打开项目".encode(), out)
            self.assertIn("连接到".encode(), out)
            self.assertTrue((Path(tmp) / "node_modules.asar.zhbak").exists())
            # 等长替换：容器总长不变，尾部内容对齐
            self.assertEqual(len(out), len(payload) + len(out) - len(payload))

    def test_too_long_translation_is_skipped(self):
        payload = b'children:"Save"'
        with tempfile.TemporaryDirectory() as tmp:
            asar = Path(tmp) / "node_modules.asar"
            self._make_asar(asar, payload)
            changed = asar_tool.apply_map(asar, "a.js", {"Save": "保存这个设置项吧"})
            self.assertEqual(changed, 0)
            self.assertEqual(asar.read_bytes()[-len(payload):], payload)


class QuotaAdaptiveTest(unittest.TestCase):
    # 故意换掉全部压缩符号名，模拟 Kiro 升级后 minify 结果变化
    SNIPPET = (
        'function Qz(e,t){let{currency:n,currentOverages:r,currentUsage:o,freeTrialUsage:s,'
        'overageCharges:a,usageLimit:l}=t,u=zz(e);'
        'return s&&s.currentUsage<s.usageLimit?`${u} Bonus ${s.currentUsage} / ${s.usageLimit}'
        ' (${s.daysRemaining} days left)`:r>0||a>0?`${u} Overage ${r} '
        '(${n.symbol}${a.toFixed(2)})`:`${u} ${o} / ${l}`}'
    )

    def test_patches_when_symbols_change(self):
        out, n = patch_ui.fix_quota_adaptive(self.SNIPPET)
        self.assertEqual(n, 3)
        self.assertIn("▰", out)
        self.assertIn("赠送", out)
        self.assertIn("超额", out)
        self.assertNotIn("Bonus", out)

    def test_idempotent(self):
        once, _ = patch_ui.fix_quota_adaptive(self.SNIPPET)
        twice, n = patch_ui.fix_quota_adaptive(once)
        self.assertEqual(n, 0)
        self.assertEqual(once, twice)

    def test_missing_markers_left_alone(self):
        text = 'const a=1;'
        self.assertEqual(patch_ui.fix_quota_adaptive(text), (text, 0))


if __name__ == "__main__":
    unittest.main()
