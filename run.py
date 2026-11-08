"""Run Rural-Renew or its single-generation only-prompt baseline."""

import argparse
import json
from pathlib import Path

from core import run_workflow
from core.providers import CodexPlanner, QwenImageEditor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path, help="Input village photograph")
    parser.add_argument("--group", choices=["only-prompt", "rural-renew"], default="rural-renew")
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "config.example.json")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--metadata", type=Path, help="Optional location JSON; see config documentation")
    parser.add_argument("--seed", type=int, default=2026112600, help="First candidate seed")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Input image does not exist")
    if args.output.exists():
        parser.error("Output directory already exists; use a new directory")
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig")) if args.metadata else {}
    if not isinstance(metadata, dict):
        parser.error("Metadata must be a JSON object")
    planner = CodexPlanner(config["planner"], args.output, config["editor"]["api_key_env"])
    editor = QwenImageEditor(config["editor"])
    scorer = None
    if args.group == "rural-renew":
        from eval_model import EvaluationScorer
        scorer = EvaluationScorer()
    result = run_workflow(args.image, args.group, args.output, planner, editor, scorer,
                          metadata=metadata, seed=args.seed)
    print("Selected image:", args.output.resolve() / result["selected_path"])
    if "suspected_error_probability" in result["selection"]:
        print("Agent-estimated unintended-edit probability:",
              result["selection"]["suspected_error_probability"])


if __name__ == "__main__":
    main()
