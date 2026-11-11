<p align="center">
  <img src="assets/illustrations/house.png" width="64" alt="rural-renew logo">
</p>

<h1 align="center">rural-renew</h1>

[English](README.md) · [简体中文](README_zh.md)

## Overview

An agent workflow for rural-scene renewal that connects a multimodal planner, an image-editing model, and an independent five-dimensional evaluator. Structured descriptions of rural houses and regional building guidelines inform two initial directions: modernization and preservation of local character. Evaluation feedback guides a third proposal and final selection.

![Overview of the rural-renew workflow](assets/overview.png)

## Contributions

- Domain-informed planning: describe a house through six aspects and eighteen indicators, combine those observations with regional building guidelines, and develop modernization and local-character proposals.
- Feedback-guided renewal: compare both directions against the original and each other, use five-dimensional feedback to guide revisions, and select an evaluated candidate.
- Five-dimensional scoring: build a rural-scene evaluator from pairwise perceptual judgments, covering rural character, prosperity, vitality, livability, and cleanliness to support consistent comparison and refinement.
- Quantitative improvement: across all 40 evaluated scenes, rural-renew achieves a mean weighted evaluation score 2.23 points higher than the single-generation only-prompt baseline.

## Selected examples

Each row shows the original photograph, the single-generation `only-prompt` result, and the result selected by `rural-renew`.

![F03: original | only-prompt | rural-renew](assets/comparisons/F03.png)

![F10: original | only-prompt | rural-renew](assets/comparisons/F10.png)

![F26: original | only-prompt | rural-renew](assets/comparisons/F26.png)

[View all 11 selected comparisons](assets/gallery.md)

## How it works

1. Load the six-aspect house description framework and the applicable regional building guidelines. The multimodal planner records what is visible for each indicator in the original photograph.
2. Plan **P1: modernization** (material renewal, tidier surfaces, functional improvements, and a more orderly appearance) and **P2: local character** (rural identity, traditional elements, regional features, and cultural expression). Both follow the same task scope and domain Context.
3. The image-editing model produces one candidate for each plan. The independent evaluator scores rural character, prosperity, vitality, livability, and cleanliness.
4. The planner reviews the original, both candidates, their scores, and their differences. Using the same Context, it identifies tradeoffs such as loss of rural character or insufficient improvement, then writes a third proposal.
5. Generate and evaluate the third candidate, then select an edited result.

### Domain Context

| House aspect | Description indicators |
|---|---|
| Facade | Material composition, color scheme, architectural form |
| Windows | Opening shape, window type, glazing details |
| Doorways | Door material, opening mechanism, surface treatment |
| Roof | Roofing material, roof type, roof slope |
| Decoration | Structural, cultural, and functional decoration |
| Surroundings | Natural environment, human traces, spatial organization |

These eighteen indicators describe the scene; the five perceptual dimensions evaluate it. Observations distinguish visible evidence from uncertain or hidden details. Regional guidelines supply location-specific guidance on materials, appearance, traditional features, and surrounding spaces. The bundled corpus currently covers Jilin Province; see [Context sources and format](context/README.md).

Modernization and local character are design priorities within the shared exterior-editing scope. All proposals preserve the original building massing, roof form, openings, and productive spaces. Evaluation feedback can combine compatible features from the two directions without changing the evaluator's weights.

Every candidate is edited from the same original photograph. The selection prompt instructs the agent to choose the highest weighted evaluation, with earlier candidates winning ties. The runner preserves the agent's actual valid choice. The original photograph is excluded from the eligible outputs.

| Workflow | Domain Context | Planner calls | Image generations | Evaluation feedback |
|---|---|---:|---:|---|
| `only-prompt` | No house framework or regional guidelines | 1 | 1 | — |
| `rural-renew` | Eighteen indicators and regional guidelines | 3 | 3 | Guides the third proposal and final selection |

The gallery and the reported 2.23-point mean improvement compare these complete workflows, including their different Context and generation budgets. They do not isolate the effect of evaluation feedback alone. The planner performs the planning, revision, and selection calls; the image editor and evaluator have separate roles. Prompt templates are provided in Chinese.

## Quick start

Run these commands from the repository directory. Install the Python dependencies and [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), then [sign in](https://learn.chatgpt.com/docs/auth):

```bash
python -m pip install -r requirements.txt
npm install -g @openai/codex@0.146.1
codex login
```

Set the image service credential in your shell:

```bash
export QWEN_API_KEY="your-api-key"
```

In PowerShell, use `$env:QWEN_API_KEY = "your-api-key"`. The runner reads the environment variable directly; it does not automatically load a `.env` file.

Review [config.example.json](config.example.json) before running. The example configuration records `gpt-5.6-sol` with medium reasoning for planning and `qwen-image-3.0-pro` for image editing. Set model IDs available to your account and a compatible image-service endpoint. Use `--config path/to/config.json` for your own configuration. The planner adapter was checked against Codex CLI 0.146.1.

Run rural-renew on a photograph from Jilin, using the example province metadata to select the bundled guideline. Add the photograph's actual city, county, or town to the metadata when available:

```bash
python run.py --image path/to/jilin-scene.png --metadata examples/jilin-location.json --group rural-renew --output outputs/jilin-rural-renew
```

For another region, supply its own guideline JSON with `--guidelines path/to/guidelines.json` and the corresponding `--metadata`. Missing guidelines and conflicting region metadata are reported before model services are initialized. The runner does not search the web for guidelines.

Run the single-generation baseline:

```bash
python run.py --image assets/original/F03.png --group only-prompt --output outputs/F03-only-prompt
```

Each run writes `selected.png`, its candidate images, plans, and `result.json` to a new output directory. Rural-renew also saves the loaded `context.json` and the structured house observations in the initial plan. Choose an unused directory for each run. These commands call the configured model services. A service error stops the run and preserves completed files; it does not trigger an automatic retry.

Optional arguments: `--seed` sets the first generation seed; `--metadata` accepts a JSON file with `imageProv`, `imageCity`, `imageCounty`, `imageTown`, and `imageYear` for location context.

Offline workflow and adapter checks use test doubles and make no model-service calls:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Backbone inference regression tests are opt-in via `RURAL_RENEW_MODEL_TESTS=1`.

## Repository

| Directory | Contents |
|---|---|
| [`assets/`](assets/) | 40 original photographs, generated results for the 11 selected scenes, comparison panels, and the overview |
| [`prompts/`](prompts/) | Single-generation planning, dual proposals, feedback revision, selection, and structured output schemas |
| [`context/`](context/) | Six aspects, eighteen indicators, two renewal directions, and sourced regional guidelines |
| [`core/`](core/) | Workflow orchestration and the planner/image-editor adapters |
| [`eval_model/`](eval_model/) | Five-dimensional inference, learned heads, fixed reference data, and normalization |

## Evaluation model

![Construction of the five-dimensional rural-scene evaluator](assets/evaluator-construction.png)

The research background is the village-scene evaluation work of the UrbanComp team at China University of Geosciences (Wuhan) and collaborators at Sun Yat-sen University. Their work, undertaken in connection with the 2023 national rural construction evaluation initiative, combined crowdsourced photographs from the Cuncunpai platform with human pairwise judgments. See the [UrbanComp project introduction](https://urbancomp.net/archives/intelligent-interpretation-of-chinese-village). Our pairwise perceptual annotation approach draws on [MIT Place Pulse](https://www.media.mit.edu/projects/place-pulse-new/overview/).

The available five-dimensional labels include rural character alongside prosperity, vitality, livability, and cleanliness. The current evaluator keeps the [ResNet50 backbone](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet50.html) frozen and trains five linear preference heads, then uses fixed training references and per-dimension standardization to produce feedback. The learned heads, reference data, and preprocessing are included; torchvision downloads the fixed ImageNet backbone on first use if needed. See the [construction and inference documentation](eval_model/README.md) for details.

