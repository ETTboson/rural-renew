"""Verify request construction without making any paid model calls."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.providers import CodexPlanner, DISABLED_FEATURES, QwenImageEditor


class ProviderTests(unittest.TestCase):
    def test_planner_attaches_images_and_disables_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            planner = CodexPlanner(dict(command=[sys.executable], model="test-model",
                                        reasoning_effort="medium"), root)
            image = root / "original.png"
            Image.new("RGB", (80, 60)).save(image)

            def run(command, **kwargs):
                self.assertIn("--ignore-user-config", command)
                self.assertIn("--ephemeral", command)
                self.assertEqual(command.count("--disable"), len(DISABLED_FEATURES))
                self.assertEqual(command[command.index("--image") + 1], str(image))
                self.assertEqual(kwargs["input"], "test prompt")
                self.assertNotIn("QWEN_API_KEY", kwargs["env"])
                self.assertEqual(kwargs["env"]["OPENAI_API_KEY"], "planner-auth-placeholder")
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text('{"value":"ok"}', encoding="utf-8")
                kwargs["stdout"].write('{"type":"turn.completed"}\n')
                return type("Result", (), {"returncode": 0})()

            with patch.dict(os.environ, {"QWEN_API_KEY": "editor-placeholder",
                                         "OPENAI_API_KEY": "planner-auth-placeholder"}), \
                    patch("core.providers.subprocess.run", side_effect=run):
                result = planner.plan("initial", "test prompt", [image], {"type": "object"})
            self.assertEqual(result, {"value": "ok"})

    def test_editor_preserves_reference_request_and_does_not_log_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "original.png"
            Image.new("RGB", (80, 60)).save(image)
            image_bytes = io.BytesIO()
            Image.new("RGB", (32, 24)).save(image_bytes, format="PNG")
            calls = []

            class Opener:
                def open(self, request, timeout):
                    calls.append(request)
                    if isinstance(request, str):
                        return io.BytesIO(image_bytes.getvalue())
                    return io.BytesIO(json.dumps(dict(output=dict(choices=[dict(message=dict(
                        content=[dict(image="https://example.com/result.png")]))]))).encode())

            config = dict(model="test-editor", api_key_env="TEST_IMAGE_KEY",
                          endpoint="https://example.com/generate", min_interval_seconds=0)
            with patch.dict(os.environ, {"TEST_IMAGE_KEY": "placeholder-secret"}), \
                    patch("core.providers.urllib.request.build_opener", return_value=Opener()):
                QwenImageEditor(config).generate(image, "修补外墙。", 123, root / "candidate.png")
            payload = json.loads(calls[0].data)
            self.assertEqual(payload["parameters"], dict(n=1, size="1184*880", seed=123,
                                                         prompt_extend=False, watermark=False))
            self.assertTrue(payload["input"]["messages"][0]["content"][0]["image"].startswith(
                "data:image/jpeg;base64,"))
            self.assertIn("共同范围", payload["input"]["messages"][0]["content"][1]["text"])
            self.assertEqual(len(calls), 2)
            for record in root.glob("*.json"):
                self.assertNotIn("placeholder-secret", record.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
