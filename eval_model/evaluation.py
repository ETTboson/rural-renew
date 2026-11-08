"""Frozen calibration and weighted feedback for exploratory image optimization."""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DIMS = ["ft", "fy", "hl", "yj", "zj"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def percentile(value, ordered):
    return float(50 * (np.searchsorted(ordered, value, "left") + np.searchsorted(ordered, value, "right")) / len(ordered))


class EvaluationScorer:
    def __init__(self):
        self.config = read(ROOT / "evaluation-weights.json")
        self.definition = self.config["score_definition"]
        self.objective = read(ROOT / self.definition["parameters"])
        self.reference = read(ROOT / self.objective["reference"])
        self.weights = np.array([self.config["numerators"][dimension] / self.config["denominator"] for dimension in DIMS])
        if not np.allclose(self.weights, [self.reference["weights"][dimension] for dimension in DIMS]):
            raise ValueError("Configured weights do not match the frozen calibration")
        self.mean = np.array([self.reference["dimensions"][dimension]["mean_probability"] for dimension in DIMS])
        self.sd = np.array([self.reference["dimensions"][dimension]["sd_probability"] for dimension in DIMS])
        self.model = None

    def from_model_output(self, output):
        if output["model"] != self.reference["model"]:
            raise ValueError("Reference parameters belong to a different model")
        probability = np.array([output["dimensions"][dimension]["score_10"] / 10 for dimension in DIMS])
        if not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1)):
            raise ValueError("Expected five finite reference-win probabilities")
        standard = 50 + 10 * (probability - self.mean) / self.sd
        total = float(standard @ self.weights)
        return dict(
            image=output["image"], objective_version=self.objective["version"], underlying_model=output["model"],
            dimensions={
                dimension: dict(
                    name=self.config["dimension_names"][dimension], probability=float(probability[index]),
                    original_score_10=float(10 * probability[index]), standard_score=float(standard[index]),
                    reference_percentile=percentile(probability[index], self.reference["dimensions"][dimension]["sorted_probabilities"]),
                    weight=float(self.weights[index]),
                )
                for index, dimension in enumerate(DIMS)
            },
            total=total, total_definition="Weighted sum of per-dimension 50+10Z scores; higher is better",
            total_reference_percentile=percentile(total, self.objective["sorted_total_reference"]),
            original_weighted_total_10=float(10 * probability @ self.weights), reference_images=self.reference["count"],
            note="50 is the reference mean, not a passing score. No clipping. The weighted total does not necessarily have SD 10.",
        )

    def score_image(self, image):
        if self.model is None:
            from .scorer import FullFrameScorer
            self.model = FullFrameScorer()
        return self.from_model_output(self.model.score_image(Path(image)))

    def feedback(self, before, after):
        if before["objective_version"] != after["objective_version"] or before["objective_version"] != self.objective["version"]:
            raise ValueError("Feedback requires matching objective versions")
        return dict(
            objective_version=self.objective["version"], before_total=before["total"], after_total=after["total"],
            total_gain=after["total"] - before["total"],
            dimension_standard_score_gains={dimension: after["dimensions"][dimension]["standard_score"] - before["dimensions"][dimension]["standard_score"] for dimension in DIMS},
            dimension_percentile_point_gains={dimension: after["dimensions"][dimension]["reference_percentile"] - before["dimensions"][dimension]["reference_percentile"] for dimension in DIMS},
            total_percentile_point_gain=after["total_reference_percentile"] - before["total_reference_percentile"],
            interpretation="Search feedback after execution checks; a gain alone does not establish improvement beyond redraw variation.",
        )
