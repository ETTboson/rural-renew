"""Run with: python -m eval_model IMAGE [--output result.json]."""

import argparse
import json
from pathlib import Path

from .evaluation import EvaluationScorer


def main():
    parser = argparse.ArgumentParser(description="Evaluate a rural-scene image with the frozen five-dimension model.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = EvaluationScorer().score_image(args.image)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
