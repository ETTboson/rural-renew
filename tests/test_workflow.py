"""Offline checks of feedback isolation, original-image input, and selection."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import ValidationError
from PIL import Image

from core.workflow import DIMS, run_workflow
from core.context import CONTEXT_ROOT, read_json


class Planner:
    def __init__(self, events, selected="candidate_1"):
        self.events = events
        self.selected = selected
        self.calls = []

    def plan(self, stage, prompt, images, schema):
        self.events.append(stage)
        self.calls.append(dict(stage=stage, prompt=prompt, images=list(images)))
        if stage == "initial":
            if "proposals" not in schema["properties"]:
                return dict(direction="Repair the facade", edit_prompt="修补外墙并整理入口。")
            observations = [dict(id=indicator["id"], visibility="uncertain",
                                 evidence="照片不足以确认具体材质与做法。")
                            for dimension in read_json(CONTEXT_ROOT / "house_features.json")["dimensions"]
                            for indicator in dimension["indicators"]]
            return dict(house_observations=observations, proposals=[
                dict(id="P2", strategy="locality", direction="Entrance", edit_prompt="整理入口并修补墙裙。"),
                dict(id="P1", strategy="modernization", direction="Facade", edit_prompt="修补外墙并整理入口。")],
                difference="更新重点不同。")
        if stage == "revision":
            return dict(observation="Two candidates compared", hypothesis="Combine compatible changes",
                        primary_change="Facade and entrance", edit_prompt="修补外墙、墙裙并整理入口。")
        return dict(selected_id=self.selected, reason="Agent output retained",
                    suspected_error_probability=.25, error_reason="An uncalibrated estimate")


class Editor:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def generate(self, original, prompt, seed, destination):
        self.events.append("edit")
        self.calls.append((original, prompt, seed))
        Image.new("RGB", (40, 32), (len(self.calls) * 50, 90, 100)).save(destination)


class Scorer:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def score_image(self, path):
        self.events.append("score")
        self.calls.append(path.name)
        # All candidates score below the original; selection must still be edited.
        total = 100 if path.name == "original.png" else int(path.stem[-1]) * 10
        return dict(total=total, dimensions={dim: {"standard_score": total} for dim in DIMS})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.jpg"
        Image.new("RGB", (80, 60), (12, 34, 56)).save(self.source)
        self.events = []
        self.planner = Planner(self.events)
        self.editor = Editor(self.events)
        self.scorer = Scorer(self.events)
        self.output = self.root / "run"
        self.guide = self.root / "guide.json"
        self.guide.write_text(json.dumps(dict(
            id="test-guide", title="Test guide", region={"imageProv": "吉林省"},
            source=dict(url="https://example.org/guide", publisher="Test publisher"),
            guidance=[dict(id="G1", topic="Color", text="TEST_GUIDANCE: retain visible colors.", pages=[1])]
        ), ensure_ascii=False), encoding="utf-8")

    def run_group(self, group, **kwargs):
        if group == "rural-renew":
            kwargs.setdefault("metadata", {"imageProv": "吉林省"})
            kwargs.setdefault("guidelines", self.guide)
        return run_workflow(self.source, group, self.output, self.planner, self.editor,
                            self.scorer, **kwargs)

    def test_only_prompt_is_one_edit_without_scoring_or_selection(self):
        result = self.run_group("only-prompt")
        self.assertEqual(self.events, ["initial", "edit"])
        self.assertEqual(len(self.editor.calls), 1)
        self.assertEqual(self.scorer.calls, [])
        self.assertEqual(result["selected_id"], "candidate_1")
        self.assertNotIn("suspected_error_probability", result["selection"])
        self.assertNotIn("score", result["candidates"][0])
        self.assertNotIn("领域 Context", self.planner.calls[0]["prompt"])
        self.assertNotIn("modernization", self.planner.calls[0]["prompt"])
        self.assertNotIn("house_observations", self.planner.calls[0]["prompt"])
        self.assertFalse((self.output / "context.json").exists())

    def test_professional_feedback_flow_and_actual_selection(self):
        result = self.run_group("rural-renew", seed=42,
                                metadata={"imageProv": "吉林省", "private_id": "discard-this"})
        self.assertEqual(self.events, ["initial", "score", "edit", "score", "edit", "score",
                                       "revision", "edit", "score", "selection"])
        self.assertEqual([call[0] for call in self.editor.calls], [self.output / "original.png"] * 3)
        self.assertEqual([call[2] for call in self.editor.calls], [42, 43, 44])
        self.assertTrue(self.editor.calls[0][1].startswith("修补外墙"))  # IDs order P1, P2.
        initial, revision, selection = self.planner.calls
        self.assertEqual(len(initial["images"]), 1)
        self.assertIn("吉林省", initial["prompt"])
        self.assertNotIn("discard-this", initial["prompt"])
        self.assertNotIn("两张候选的评分反馈", initial["prompt"])
        self.assertEqual([p.name for p in revision["images"]],
                         ["original.png", "candidate_1.png", "candidate_2.png"])
        self.assertIn('"candidate_2_minus_candidate_1": {"total": 10', revision["prompt"])
        self.assertEqual(len(selection["images"]), 4)
        self.assertEqual([c["strategy"] for c in result["candidates"]],
                         ["modernization", "locality", "feedback_revision"])
        for call in self.planner.calls:
            self.assertIn("TEST_GUIDANCE", call["prompt"])
            self.assertIn('"name": "功能性装饰"', call["prompt"])
            self.assertIn('"name": "现代化更新"', call["prompt"])
        for call in (revision, selection):
            self.assertIn("原图农房十八项观察", call["prompt"])
            self.assertIn("照片不足以确认具体材质与做法。", call["prompt"])
        feedback = read_json(self.output / "feedback.json")
        self.assertEqual(feedback["original"]["total"], 100)
        self.assertEqual(feedback["gains_over_original"]["candidate_1"]["dimensions"]["ft"], -90)
        self.assertEqual(feedback["gains_over_original"]["candidate_2"]["total"], -80)
        snapshot = read_json(self.output / "context.json")
        self.assertEqual(snapshot["regional_guidelines"]["id"], "test-guide")
        self.assertEqual(result["context_path"], "context.json")
        self.assertEqual(result["selected_id"], "candidate_1")  # Not the highest-scoring candidate.
        self.assertEqual(result["selection"]["suspected_error_probability"], .25)
        self.assertEqual((self.output / "selected.png").read_bytes(),
                         (self.output / "candidate_1.png").read_bytes())
        with Image.open(self.output / "selected.png") as selected:
            self.assertEqual(selected.size, (80, 60))

    def test_original_selection_is_rejected_without_substitution(self):
        self.planner.selected = "original"
        with self.assertRaises(ValidationError):
            self.run_group("rural-renew")
        self.assertFalse((self.output / "selected.png").exists())
        self.assertFalse((self.output / "result.json").exists())

    def test_existing_output_is_preserved_before_model_calls(self):
        self.output.mkdir()
        keep = self.output / "user.txt"
        keep.write_text("user edits", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_group("rural-renew")
        self.assertEqual(keep.read_text(encoding="utf-8"), "user edits")
        self.assertEqual(self.events, [])

    def test_duplicate_observation_stops_before_editing(self):
        original_plan = self.planner.plan
        def duplicate(stage, *args):
            result = original_plan(stage, *args)
            if stage == "initial":
                result["house_observations"][-1] = result["house_observations"][0].copy()
            return result
        with patch.object(self.planner, "plan", side_effect=duplicate):
            with self.assertRaisesRegex(ValueError, "exactly once"):
                self.run_group("rural-renew")
        self.assertEqual(self.editor.calls, [])
        self.assertEqual(self.scorer.calls, [])

    def test_swapped_strategies_stop_before_editing(self):
        original_plan = self.planner.plan
        def swap(stage, *args):
            result = original_plan(stage, *args)
            if stage == "initial":
                result["proposals"][0]["strategy"] = "modernization"
            return result
        with patch.object(self.planner, "plan", side_effect=swap):
            with self.assertRaisesRegex(ValueError, "P1 must"):
                self.run_group("rural-renew")
        self.assertEqual(self.editor.calls, [])

    def test_region_conflict_stops_before_any_model_call(self):
        with self.assertRaisesRegex(ValueError, "imageProv"):
            self.run_group("rural-renew", metadata={"imageProv": "广东省"})
        self.assertEqual(self.events, [])
        self.assertFalse(self.output.exists())

    def test_only_prompt_rejects_domain_context(self):
        with self.assertRaisesRegex(ValueError, "does not accept"):
            self.run_group("only-prompt", guidelines=self.guide)
        self.assertEqual(self.events, [])
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
