# Domain context

Rural-Renew combines the six-aspect, eighteen-indicator house description, two renewal directions, and regional housing guidance. The planner receives this context during initial planning, feedback revision, and selection. The `only-prompt` baseline does not receive it.

## Regional guidance

[`regional/jilin.json`](regional/jilin.json) contains ten concise summaries from the *Jilin Province Rural Housing Style Guidelines and Technical Guidance (2026)*, published by the Jilin Provincial Department of Housing and Urban-Rural Development on April 14, 2026. The [official publication page](https://xxgk.jl.gov.cn/zcbm/fgw_98022/xxgkmlqy/202604/t20260414_9508710.html) provides the source PDF. Each summary records its source pages, counted from the first PDF page, including the cover. The original PDF is not bundled.

The summaries retain the guide's eastern, central, and western regional distinctions. Regional and cultural examples are applied using location metadata and visible evidence. With only province-level information, the planner uses province-wide principles rather than assigning a particular local or ethnic style.

The guide includes construction topics as well as appearance guidance. The runner's editing scope remains an exterior-image renewal task: observable surfaces and existing spaces inform proposals; building volume, roof form, opening geometry, and productive spaces follow the common task constraints in `prompts/common_scope.txt`. Photographs do not establish hidden glazing, insulation, or structural specifications.

## Adding a regional guide

Provide a UTF-8 JSON file with this structure and pass its path using `--guidelines`:

```json
{
  "id": "unique-guide-id",
  "title": "Published guide title",
  "region": {"imageProv": "Province name"},
  "source": {
    "url": "https://official-publisher.example/guide",
    "publisher": "Publishing authority",
    "published_at": "YYYY-MM-DD",
    "page_numbering": "1-based PDF pages, including the cover"
  },
  "guidance": [
    {"id": "G01", "topic": "Facade materials", "text": "A source-grounded summary.", "pages": [1]}
  ]
}
```

Use the guide's actual coverage in `region` and retain source references. The bundled guide is selected automatically for `imageProv: 吉林省`; other provinces require their own guide. Each Rural-Renew run saves the loaded context in `context.json` and its planning inputs in `plans/`.
