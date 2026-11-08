# Running the workflow

`workflow.py` implements the fixed planning, editing, feedback, and selection sequence. `providers.py` connects it to the Codex CLI and Qwen image editing endpoint. The text templates and output schemas live in `../prompts/`.

The `only-prompt` group makes one planning call and one image edit. The `rural-renew` group makes three planning calls and three image edits; all edits use the same original photograph. The final Agent selection is retained as returned, and the original is never eligible. Its estimated unintended-edit probability is recorded without changing the selection.

Run each scene into a new output directory. Technical errors stop this packaged runner and preserve completed files for inspection; it makes no automatic paid retries and never substitutes the original. This differs from the historical experiment's partial-result handling after an explicit image-service rejection. The released successful examples use the complete workflow.

The planner starts with native tools disabled and receives the prepared images and structured prompt only. The image editor's API key is excluded from the planner subprocess environment. Its Codex authentication environment is retained.
