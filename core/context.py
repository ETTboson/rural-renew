"""Prepare the house vocabulary, renewal directions, and regional guide context."""

import json
from pathlib import Path

from jsonschema import validate


CONTEXT_ROOT = Path(__file__).resolve().parent.parent / "context"
REGION_KEYS = ("imageProv", "imageCity", "imageCounty", "imageTown")
BUNDLED_GUIDES = {"吉林省": CONTEXT_ROOT / "regional" / "jilin.json"}
GUIDE_SCHEMA = {
    "type": "object",
    "required": ["id", "title", "region", "source", "guidance"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "region": {
            "type": "object", "minProperties": 1, "additionalProperties": False,
            "properties": {key: {"type": "string", "minLength": 1} for key in REGION_KEYS},
        },
        "source": {
            "type": "object", "required": ["url", "publisher"],
            "properties": {
                "url": {"type": "string", "pattern": "^https?://"},
                "publisher": {"type": "string", "minLength": 1},
            },
        },
        "guidance": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object", "required": ["id", "topic", "text", "pages"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "topic": {"type": "string", "minLength": 1},
                    "text": {"type": "string", "minLength": 1},
                    "pages": {"type": "array", "minItems": 1,
                              "items": {"type": "integer", "minimum": 1}},
                },
            },
        },
    },
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def prepare_context(group, metadata=None, guidelines=None):
    """Resolve and validate context before constructing providers or making calls.

    An explicit guide selects a document. Its region still has to match the
    image metadata, so selecting a file cannot silently relabel the scene.
    """
    if group not in {"only-prompt", "rural-renew"}:
        raise ValueError("group must be only-prompt or rural-renew")
    if group == "only-prompt":
        if guidelines is not None:
            raise ValueError("only-prompt does not accept regional guidelines")
        return None
    metadata = metadata or {}
    guide_path = Path(guidelines) if guidelines is not None else BUNDLED_GUIDES.get(metadata.get("imageProv"))
    if guide_path is None:
        raise ValueError("No regional guide for this scene; provide matching --metadata and --guidelines")
    guide = read_json(guide_path)
    validate(guide, GUIDE_SCHEMA)
    for key, region in guide["region"].items():
        if metadata.get(key) != region:
            raise ValueError(f"Regional guide requires metadata {key}={region!r}")
    ids = [item["id"] for item in guide["guidance"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Regional guidance IDs must be unique")
    return {
        "house_features": read_json(CONTEXT_ROOT / "house_features.json"),
        "renewal_directions": read_json(CONTEXT_ROOT / "renewal_directions.json"),
        "regional_guidelines": guide,
    }


def validate_observations(observations, context):
    expected = {indicator["id"] for dimension in context["house_features"]["dimensions"]
                for indicator in dimension["indicators"]}
    actual = [observation["id"] for observation in observations]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("House observations must cover each of the eighteen indicators exactly once")
    if any(not observation["evidence"].strip() for observation in observations):
        raise ValueError("Each house observation requires visible evidence or an explanation of uncertainty")


def context_text(context):
    if context is None:
        return ""
    return "\n领域 Context（六方面十八项描述指标、两种更新方向、匹配地区的建设导则）：\n" + json.dumps(
        context, ensure_ascii=False)
