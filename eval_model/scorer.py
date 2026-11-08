"""Full-frame ResNet50 features and frozen five-dimension preference heads."""

import os
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import torch
from PIL import Image, ImageOps
from scipy.special import expit
from torchvision.models import ResNet50_Weights, resnet50
from torchvision.transforms import InterpolationMode, functional as TF

ROOT = Path(__file__).resolve().parent
DIMS = ["ft", "fy", "hl", "yj", "zj"]
LABELS = dict(ft="乡土性", fy="富裕", hl="活力", yj="宜居", zj="整洁")
# Preserve the identifier bound to the frozen calibration parameters.
MODEL_ID = "full-frame-evaluator-01/letterbox224_robust"


def input_image(image):
    """Fit the entire RGB image into a centered 224-pixel square."""
    width, height = image.size
    new_width = max(1, round(width * 224 / max(width, height)))
    new_height = max(1, round(height * 224 / max(width, height)))
    scaled = TF.resize(image, [new_height, new_width], InterpolationMode.BILINEAR)
    canvas = Image.new("RGB", (224, 224), (124, 116, 104))
    canvas.paste(scaled, ((224 - new_width) // 2, (224 - new_height) // 2))
    return canvas


def image_tensor(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    return TF.normalize(
        TF.to_tensor(input_image(image)),
        [.485, .456, .406],
        [.229, .224, .225],
    )


class FeatureExtractor:
    def __init__(self):
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # torchvision downloads the public backbone once, then uses its cache.
        self.model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2).to(self.device).eval()
        self.model.fc = torch.nn.Identity()

    def extract(self, paths):
        features = np.empty((len(paths), 2048), dtype=np.float32)
        with torch.inference_mode():
            for start in range(0, len(paths), 12):
                batch = torch.stack([image_tensor(path) for path in paths[start:start + 12]])
                features[start:start + len(batch)] = self.model(batch.to(self.device)).cpu().numpy()
        if not np.isfinite(features).all():
            raise ValueError("Nonfinite image features")
        return features


class FullFrameScorer:
    def __init__(self):
        self.extractor = FeatureExtractor()
        with np.load(ROOT / "weights" / "heads.npz") as params:
            self.mean = params["mean"]
            self.scale = params["scale"]
            self.weights = params["weights"]
        with np.load(ROOT / "weights" / "reference_scores.npz") as params:
            self.reference = params["reference_scores"]
        self.dimensions = DIMS

    def score(self, paths):
        features = self.extractor.extract(paths).astype(float)
        return ((features - self.mean) / self.scale) @ self.weights.T

    def to_score_10(self, raw):
        return 10 * expit(np.atleast_2d(raw)[:, None, :] - self.reference[None, :, :]).mean(axis=1)

    def score_image(self, path):
        raw = self.score([path])[0]
        scaled = self.to_score_10(raw)[0]
        return dict(
            image=str(path), model=MODEL_ID,
            scale="fixed_reference_win_probability_0_10",
            reference_images=len(self.reference),
            dimensions={
                dimension: dict(name=LABELS[dimension], score_10=float(scaled[index]), raw_score=float(raw[index]))
                for index, dimension in enumerate(DIMS)
            },
        )
