"""Calibration/preprocessing checks and opt-in frozen-image regression."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from eval_model import EvaluationScorer
from eval_model.evaluation import DIMS, percentile
from eval_model.scorer import image_tensor, input_image

ROOT = Path(__file__).resolve().parents[1]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.scorer = EvaluationScorer()

    def output(self, probabilities):
        return {
            "image": "example.png", "model": self.scorer.reference["model"],
            "dimensions": {dimension: {"score_10": float(10 * probabilities[index])} for index, dimension in enumerate(DIMS)},
        }

    def test_reference_mean_and_dimension_tradeoffs(self):
        baseline = self.scorer.from_model_output(self.output(self.scorer.mean))
        self.assertAlmostEqual(baseline["total"], 50)
        for index, weight in enumerate([1 / 15, 1 / 15, 1 / 15, .4, .4]):
            probabilities = self.scorer.mean.copy()
            probabilities[index] += self.scorer.sd[index]
            result = self.scorer.from_model_output(self.output(probabilities))
            self.assertAlmostEqual(result["total"] - baseline["total"], 10 * weight)
            feedback = self.scorer.feedback(baseline, result)
            self.assertAlmostEqual(feedback["total_gain"], 10 * weight)
            self.assertAlmostEqual(feedback["dimension_standard_score_gains"][DIMS[index]], 10)

    def test_no_clipping(self):
        # Exercise valid probabilities outside a narrow reference distribution.
        self.scorer.mean = np.full(5, .5)
        self.scorer.sd = np.full(5, .01)
        low = self.scorer.from_model_output(self.output(np.zeros(5)))
        high = self.scorer.from_model_output(self.output(np.ones(5)))
        self.assertAlmostEqual(low["total"], -450)
        self.assertAlmostEqual(high["total"], 550)

    def test_rejects_mismatched_model_and_invalid_probabilities(self):
        output = self.output(self.scorer.mean)
        output["model"] = "different-model"
        with self.assertRaises(ValueError):
            self.scorer.from_model_output(output)
        for value in [float("nan"), -0.01, 1.01]:
            probabilities = self.scorer.mean.copy()
            probabilities[0] = value
            with self.assertRaises(ValueError):
                self.scorer.from_model_output(self.output(probabilities))

    def test_percentile_ties_and_boundaries(self):
        self.assertEqual(percentile(2, [1, 2, 2, 3]), 50)
        self.assertEqual(percentile(0, [1, 2, 2, 3]), 0)
        self.assertEqual(percentile(4, [1, 2, 2, 3]), 100)


class PreprocessingTests(unittest.TestCase):
    def test_landscape_letterbox_keeps_full_image(self):
        source = Image.new("RGB", (400, 200), (255, 0, 0))
        result = input_image(source)
        self.assertEqual(result.size, (224, 224))
        self.assertEqual(result.getpixel((0, 55)), (124, 116, 104))
        self.assertEqual(result.getpixel((0, 56)), (255, 0, 0))
        self.assertEqual(result.getpixel((223, 167)), (255, 0, 0))
        self.assertEqual(result.getpixel((223, 168)), (124, 116, 104))

    def test_exif_orientation_precedes_letterbox(self):
        source = Image.new("RGB", (400, 200), (255, 0, 0))
        exif = Image.Exif()
        exif[274] = 6  # Rotate the displayed image 90 degrees clockwise.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oriented.png"
            source.save(path, exif=exif)
            tensor = image_tensor(path).numpy()
        red = (np.array([1., 0., 0.]) - [.485, .456, .406]) / [.229, .224, .225]
        padding = (np.array([124., 116., 104.]) / 255 - [.485, .456, .406]) / [.229, .224, .225]
        np.testing.assert_allclose(tensor[:, 0, 112], red, atol=1e-6)
        np.testing.assert_allclose(tensor[:, 112, 0], padding, atol=1e-6)


@unittest.skipUnless(os.environ.get("RURAL_RENEW_MODEL_TESTS") == "1", "Set RURAL_RENEW_MODEL_TESTS=1 for backbone inference")
class FrozenImageRegressionTests(unittest.TestCase):
    def test_recorded_original_images(self):
        # Recorded frozen-model outputs; dimension order is ft, fy, hl, yj, zj.
        fixtures = {
            "F03": ([48.58764766685595, 51.26832709933352, 48.74929346533451, 50.93539980514833, 45.59464828136532], 48.51903711670707),
            "F17": ([48.898627702355476, 49.83801069113674, 45.521410040240674, 43.23293738100327, 44.36773660104298], 44.657472821734025),
            "F37": ([46.53958772385956, 39.69979970202421, 46.33697769203763, 45.429826611838436, 46.8896319086967], 45.76620774940882),
        }
        scorer = EvaluationScorer()
        for case, (dimensions, total) in fixtures.items():
            with self.subTest(case=case):
                result = scorer.score_image(ROOT / "assets" / "original" / f"{case}.png")
                np.testing.assert_allclose([result["dimensions"][dimension]["standard_score"] for dimension in DIMS], dimensions, atol=2e-4, rtol=0)
                self.assertAlmostEqual(result["total"], total, delta=2e-4)


if __name__ == "__main__":
    unittest.main()
