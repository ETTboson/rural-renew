"""Offline checks of feedback isolation, original-image input, and selection."""

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError
from PIL import Image

from core.workflow import DIMS, run_workflow


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
            return dict(proposals=[
                dict(id="P2", direction="Entrance", edit_prompt="整理入口并修补墙裙。"),
                dict(id="P1", direction="Facade", edit_prompt="修补外墙并整理入口。")],
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

    def run_group(self, group, **kwargs):
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


if __name__ == "__main__":
    unittest.main()
