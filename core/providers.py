"""Adapters for the planner and image editor used in the released examples."""

import base64
import io
import json
import math
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from .workflow import template, write_json


DISABLED_FEATURES = [
    "shell_tool", "apps", "plugins", "remote_plugin", "browser_use", "browser_use_external",
    "computer_use", "in_app_browser", "image_generation", "multi_agent", "multi_agent_v2",
    "memories", "skill_search", "workspace_dependencies", "hooks", "code_mode", "code_mode_host",
]


class CodexPlanner:
    """Ephemeral, image-aware, tool-disabled Codex calls with JSON output."""

    def __init__(self, config, output_dir, image_api_key_env="QWEN_API_KEY"):
        self.config = config
        self.output_dir = Path(output_dir).resolve()
        self.excluded_env = {"QWEN_API_KEY", image_api_key_env.upper()}
        command = config["command"]
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError("planner.command must be a nonempty list of command arguments")
        executable = shutil.which(command[0])
        if executable is None:
            raise RuntimeError("Planner executable not found; install Codex or set planner.command")
        self.command = [executable] + command[1:]

    def plan(self, stage, prompt, images, output_schema):
        folder = self.output_dir / "planner_calls" / stage
        folder.mkdir(parents=True, exist_ok=False)
        schema_path = folder / "schema.json"
        raw_path = folder / "response.json"
        log_path = folder / "events.jsonl"
        neutral = self.output_dir / "empty_runtime"
        neutral.mkdir(exist_ok=True)
        write_json(schema_path, output_schema)
        command = self.command + [
            "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
            "--sandbox", "read-only", "-m", self.config["model"],
            "-c", 'model_reasoning_effort="' + self.config["reasoning_effort"] + '"',
            "-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
            "-c", 'model_provider="research-http"',
            "-c", 'model_providers.research-http={name="OpenAI HTTP",wire_api="responses",'
                  'requires_openai_auth=true,supports_websockets=false}',
            "--output-schema", str(schema_path), "--output-last-message", str(raw_path), "--json",
        ]
        for feature in DISABLED_FEATURES:
            command.extend(["--disable", feature])
        for image in images:
            command.extend(["--image", str(image)])
        command.append("-")
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in self.excluded_env}
        with log_path.open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, input=prompt, text=True, encoding="utf-8",
                                    stdout=stream, stderr=subprocess.STDOUT, cwd=neutral,
                                    env=environment,
                                    timeout=self.config.get("timeout_seconds", 420))
        if result.returncode or not raw_path.exists():
            raise RuntimeError(f"Planner call failed; inspect {log_path}")
        # Ensure a model-side tool invocation did not bypass the fixed workflow.
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("{"):
                continue
            event = json.loads(line)
            if event.get("item", {}).get("type") in {
                "command_execution", "mcp_tool_call", "web_search", "file_change"
            }:
                raise RuntimeError("Unexpected native tool use in planner call")
        return json.loads(raw_path.read_text(encoding="utf-8"))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class QwenImageEditor:
    """One Qwen image-edit request per candidate, with no automatic retries."""

    def __init__(self, config):
        self.config = config
        self.credential = os.environ.get(config["api_key_env"], "").strip()
        if not self.credential:
            raise RuntimeError(f"Set the {config['api_key_env']} environment variable")
        if not config["endpoint"].startswith("https://"):
            raise ValueError("The image endpoint must use HTTPS")
        self.last_request = None

    def generate(self, original, prompt, seed, destination):
        destination = Path(destination)
        with Image.open(original) as image:
            width, height = image.size
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90)
        encoded = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        factor = math.sqrt(1024 * 1024 / (width * height))
        parameters = dict(n=1, size=f"{max(16, round(width * factor / 16) * 16)}*"
                          f"{max(16, round(height * factor / 16) * 16)}", seed=seed,
                          prompt_extend=False, watermark=False)
        payload = dict(model=self.config["model"], input=dict(messages=[dict(role="user", content=[
            dict(image=encoded), dict(text=prompt + "\n共同范围：" + template("common_scope"))])]),
            parameters=parameters)
        # This record contains no credential or full image payload.
        write_json(destination.with_suffix(".request.json"), dict(model=self.config["model"],
                   source=Path(original).name, prompt=prompt, parameters=parameters))
        if self.last_request is not None:
            delay = self.config.get("min_interval_seconds", 15) - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
        request = urllib.request.Request(self.config["endpoint"], data=json.dumps(payload).encode("utf-8"),
                                         headers={"Authorization": "Bearer " + self.credential,
                                                  "Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        self.last_request = time.monotonic()
        try:
            with opener.open(request, timeout=self.config.get("timeout_seconds", 240)) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Image API returned HTTP {error.code}; no automatic retry") from error
        except (TimeoutError, urllib.error.URLError) as error:
            raise RuntimeError("Image request outcome is unknown; no automatic retry") from error
        write_json(destination.with_suffix(".response.json"), data)
        try:
            content = data["output"]["choices"][0]["message"]["content"]
            url = next(item["image"] for item in content if "image" in item)
        except (KeyError, IndexError, StopIteration, TypeError) as error:
            raise RuntimeError("Image API returned no image; inspect the saved response") from error
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError("Image API returned an unsupported image URL")
        with opener.open(url, timeout=90) as response:
            blob = response.read()
        with Image.open(io.BytesIO(blob)) as image:
            image.verify()
        with destination.open("xb") as stream:
            stream.write(blob)
