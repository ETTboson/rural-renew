"""Offline tests for source selection and the eighteen-indicator contract."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import ValidationError
from PIL import Image

from core.context import CONTEXT_ROOT, prepare_context, read_json
from core.workflow import schema


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.guide = self.root / "guide.json"
        self.document = dict(id="test", title="Test guide", region={"imageProv": "吉林省"},
                             source=dict(url="https://example.org/guide", publisher="Test publisher"),
                             guidance=[dict(id="G1", topic="Walls", text="Test guidance", pages=[3])])
        self.save_guide()

    def save_guide(self):
        self.guide.write_text(json.dumps(self.document, ensure_ascii=False), encoding="utf-8")

    def test_complete_six_aspects_and_eighteen_indicator_contract(self):
        context = prepare_context("rural-renew", {"imageProv": "吉林省"}, self.guide)
        dimensions = context["house_features"]["dimensions"]
        self.assertEqual({d["name"]: [i["name"] for i in d["indicators"]] for d in dimensions}, {
            "立面维度": ["材料构成", "色彩搭配", "建筑形态"],
            "窗口维度": ["开口形态", "窗户类型", "玻璃细节"],
            "门洞维度": ["门体材质", "开启方式", "表面处理"],
            "屋顶维度": ["屋面材料", "屋顶类型", "屋面坡度"],
            "装饰维度": ["结构装饰", "文化装饰", "功能性装饰"],
            "环境维度": ["自然环境", "人文痕迹", "空间组织"],
        })
        ids = [i["id"] for d in dimensions for i in d["indicators"]]
        self.assertEqual(len(set(ids)), 18)
        self.assertEqual(set(schema("initial_proposals")["properties"]["house_observations"]
                             ["items"]["properties"]["id"]["enum"]), set(ids))

    def test_automatic_region_selection_and_explicit_selection_match(self):
        with patch("core.context.BUNDLED_GUIDES", {"吉林省": self.guide}):
            automatic = prepare_context("rural-renew", {"imageProv": "吉林省"})
        explicit = prepare_context("rural-renew", {"imageProv": "吉林省"}, self.guide)
        self.assertEqual(automatic, explicit)

    def test_missing_or_mismatched_region_is_not_guessed(self):
        for metadata in ({}, {"imageProv": "广东省"}):
            with self.subTest(metadata=metadata):
                with self.assertRaisesRegex(ValueError, "requires metadata"):
                    prepare_context("rural-renew", metadata, self.guide)
        with self.assertRaisesRegex(ValueError, "No regional guide"):
            prepare_context("rural-renew", {})
        self.document["region"]["imageCity"] = "长春市"
        self.save_guide()
        with self.assertRaisesRegex(ValueError, "imageCity"):
            prepare_context("rural-renew", {"imageProv": "吉林省"}, self.guide)

    def test_empty_guidance_or_duplicate_ids_rejected(self):
        self.document["guidance"] = []
        self.save_guide()
        with self.assertRaises(ValidationError):
            prepare_context("rural-renew", {"imageProv": "吉林省"}, self.guide)
        self.document["guidance"] = [dict(id="G1", topic="Walls", text="Test guidance", pages=[3])] * 2
        self.save_guide()
        with self.assertRaisesRegex(ValueError, "unique"):
            prepare_context("rural-renew", {"imageProv": "吉林省"}, self.guide)

    def test_cli_context_error_precedes_provider_construction(self):
        import run
        source = self.root / "scene.png"
        Image.new("RGB", (12, 12)).save(source)
        argv = ["run.py", "--image", str(source), "--output", str(self.root / "out")]
        with patch("sys.argv", argv), patch.object(run, "CodexPlanner") as planner, \
                patch.object(run, "QwenImageEditor") as editor, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                run.main()
        self.assertEqual(error.exception.code, 2)
        planner.assert_not_called()
        editor.assert_not_called()
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
