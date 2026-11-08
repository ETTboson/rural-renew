"""The released one-edit baseline and three-edit professional workflow.

All edited candidates start from the same original. Model output is retained;
the runner never substitutes an oracle choice or falls back to the original.
"""

import json
import shutil
from pathlib import Path

from jsonschema import validate
from PIL import Image, ImageOps


PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
DIMS = dict(ft="乡土性", fy="富裕", hl="活力", yj="宜居", zj="整洁")
WEIGHTS = dict(ft=1 / 15, fy=1 / 15, hl=1 / 15, yj=.4, zj=.4)
LOCATION_KEYS = ("imageProv", "imageCity", "imageCounty", "imageTown", "imageYear")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def template(name):
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")


def schema(name):
    return json.loads((PROMPTS / "schemas" / f"{name}.json").read_text(encoding="utf-8"))


def canonical_image(source, destination, size=None):
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if size is not None and image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        with Path(destination).open("xb") as stream:
            image.save(stream, format="PNG")
        return image.size


def run_workflow(image, group, output_dir, planner, editor, scorer=None,
                 metadata=None, seed=2026112600):
    """Run one fresh scene; existing output directories are never overwritten.

    planner.plan(stage, prompt, images, schema) returns structured JSON.
    editor.generate(original, prompt, seed, destination) writes one edited image.
    scorer.score_image(path) returns the frozen evaluator's detailed output.
    """
    if group not in {"only-prompt", "rural-renew"}:
        raise ValueError("group must be only-prompt or rural-renew")
    if group == "rural-renew" and scorer is None:
        raise ValueError("rural-renew requires the five-dimensional evaluator")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    original_path = output_dir / "original.png"
    size = canonical_image(image, original_path)
    location = {key: value for key, value in (metadata or {}).items() if key in LOCATION_KEYS}
    location_text = "\n地区记录：" + json.dumps(location, ensure_ascii=False)
    plans = output_dir / "plans"
    plans.mkdir()

    def plan(stage, prompt, images, output_schema):
        write_json(plans / f"{stage}_input.json", dict(prompt=prompt,
                   images=[str(p.relative_to(output_dir)) for p in images], schema=output_schema))
        result = planner.plan(stage, prompt, images, output_schema)
        validate(result, output_schema)
        write_json(plans / f"{stage}_output.json", result)
        return result

    # Initial planning sees only the original and optional location metadata.
    initial_name = "only_prompt" if group == "only-prompt" else "initial_proposals"
    initial = plan("initial", template(initial_name) + location_text,
                   [original_path], schema(initial_name))
    if group == "only-prompt":
        proposals = [initial]
    else:
        by_id = {proposal["id"]: proposal for proposal in initial["proposals"]}
        if set(by_id) != {"P1", "P2"}:
            raise ValueError("Initial proposals must contain distinct P1 and P2 IDs")
        proposals = [by_id["P1"], by_id["P2"]]
    if any(not item["edit_prompt"].strip() for item in proposals):
        raise ValueError("An edit prompt cannot be empty")

    def score(path):
        detailed = scorer.score_image(path)
        return dict(dimensions={dim: detailed["dimensions"][dim]["standard_score"] for dim in DIMS},
                    total=detailed["total"])

    original_score = score(original_path) if group == "rural-renew" else None
    candidates = []

    def generate_candidate(edit_prompt):
        if not edit_prompt.strip():
            raise ValueError("An edit prompt cannot be empty")
        index = len(candidates) + 1
        candidate_id = f"candidate_{index}"
        raw = output_dir / f"{candidate_id}_raw.png"
        destination = output_dir / f"{candidate_id}.png"
        candidate_seed = seed + index - 1
        editor.generate(original_path, edit_prompt, candidate_seed, raw)
        canonical_image(raw, destination, size)
        candidate = dict(id=candidate_id, path=destination.name, edit_prompt=edit_prompt,
                         seed=candidate_seed)
        if group == "rural-renew":
            candidate["score"] = score(destination)
        candidates.append(candidate)
        write_json(output_dir / f"{candidate_id}.json", candidate)

    for proposal in proposals:
        generate_candidate(proposal["edit_prompt"])

    if group == "only-prompt":
        # This baseline has no feedback, revision, or model-based selection call.
        selection = dict(selected_id="candidate_1")
    else:
        first, second = [candidate["score"] for candidate in candidates]
        feedback = dict(dimension_names=DIMS, weights=WEIGHTS,
                        candidate_1=first, candidate_2=second,
                        candidate_2_minus_candidate_1=dict(total=second["total"] - first["total"],
                            dimensions={dim: second["dimensions"][dim] - first["dimensions"][dim]
                                        for dim in DIMS}))
        write_json(output_dir / "feedback.json", feedback)
        revision_prompt = template("feedback_revision") + location_text
        revision_prompt += "\n已有候选对应方案（顺序与候选图一致）：" + json.dumps(
            [dict(id=c["id"], edit_prompt=c["edit_prompt"]) for c in candidates], ensure_ascii=False)
        revision_prompt += "\n图片顺序：原图、" + "、".join(c["id"] for c in candidates) + "。"
        revision_prompt += "\n两张候选的评分反馈：" + json.dumps(feedback, ensure_ascii=False)
        revision = plan("revision", revision_prompt,
                        [original_path] + [output_dir / c["path"] for c in candidates],
                        schema("feedback_revision"))
        generate_candidate(revision["edit_prompt"])

        info = dict(dimension_names=DIMS, weights=WEIGHTS, original=original_score,
                    candidates=[dict(id=c["id"], edit_prompt=c["edit_prompt"], score=c["score"],
                        gain_over_original=c["score"]["total"] - original_score["total"],
                        dimension_gains={dim: c["score"]["dimensions"][dim] -
                                         original_score["dimensions"][dim] for dim in DIMS})
                        for c in candidates])
        selection_prompt = template("selection") + "\n图片顺序：原图、"
        selection_prompt += "、".join(c["id"] for c in candidates) + "。"
        selection_prompt += "\n原图及候选信息：" + json.dumps(info, ensure_ascii=False)
        selection = plan("selection", selection_prompt,
                         [original_path] + [output_dir / c["path"] for c in candidates], schema("selection"))

    by_id = {candidate["id"]: candidate for candidate in candidates}
    if selection["selected_id"] not in by_id:
        raise ValueError("Agent selected an ineligible image; no replacement is permitted")
    chosen = by_id[selection["selected_id"]]
    # Preserve the actual Agent choice, even if it disagrees with the numeric best.
    shutil.copyfile(output_dir / chosen["path"], output_dir / "selected.png")
    result = dict(group=group, original="original.png", candidates=candidates,
                  selection=selection, selected_id=chosen["id"], selected_path="selected.png",
                  generations=len(candidates))
    if original_score is not None:
        result["original_score"] = original_score
    write_json(output_dir / "result.json", result)
    return result
