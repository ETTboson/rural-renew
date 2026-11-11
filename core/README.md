# Running the workflow

`workflow.py` implements the fixed planning, editing, feedback, and selection sequence. `context.py` loads the house description framework, renewal directions, and region-matched guidelines from `../context/`. `providers.py` connects the workflow to the Codex CLI and Qwen image editing endpoint. The text templates and output schemas live in `../prompts/`.

The professional workflow loads its Context before model services are initialized. Initial planning records eighteen house observations and produces P1 (modernization) and P2 (local character). The same Context and observations accompany revision and selection. Feedback includes each candidate's five-dimensional change from the original and the difference between the candidates. The actual Context and model inputs are saved with the run.

The `only-prompt` group receives the original task and optional location metadata, without the house framework or regional guidelines. It makes one planning call and one image edit. The `rural-renew` group makes three planning calls and three image edits; all edits use the same original photograph. The final Agent selection is retained as returned, and the original is never eligible. Its estimated unintended-edit probability is recorded without changing the selection.

Run each scene into a new output directory. Technical errors stop this packaged runner and preserve completed files for inspection; it makes no automatic paid retries and never substitutes the original. This differs from the historical experiment's partial-result handling after an explicit image-service rejection. The released successful examples use the complete workflow.

The planner starts with native tools disabled and receives the prepared images and structured prompt only. The image editor's API key is excluded from the planner subprocess environment. Its Codex authentication environment is retained.
