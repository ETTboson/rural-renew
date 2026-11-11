<p align="center">
  <img src="assets/illustrations/house.png" width="64" alt="rural-renew logo">
</p>

<h1 align="center">rural-renew</h1>

[English](README.md) · [简体中文](README_zh.md)

## 概述

面向村景更新的 Agent 流程，结合多模态规划模型、图像编辑模型与独立的五维评价器。通过农房结构化表达和地区建设导则提供领域 Context，先探索现代化更新与本土性更新，再依据评价反馈制定第三个方案，最后选出一张修改图。

![rural-renew 方法概览](assets/overview.png)

## 主要贡献

- 领域 Context 约束下的规划：从六个方面、十八项指标描述农房，结合地区建设导则，制定现代化更新与本土性更新方案。
- 评分驱动的方案优化：比较两个方向相对原图的变化与彼此的差异，利用五维反馈确定修订方向，并依据评价选择最终结果。
- 五维村景评分器：基于成对感知标注，构建覆盖乡土性、富裕、活力、宜居、整洁的评价模型，为方案比较和迭代提供统一反馈。
- 对照结果：在全部 40 个评估场景中，rural-renew 的加权综合评价分数平均比单次生成的 only-prompt 高 2.23 分。

## 精选案例

每行依次展示原图、单次生成的 `only-prompt` 结果，以及 `rural-renew` 流程选出的结果。

![F03：原图 | only-prompt | rural-renew](assets/comparisons/F03.png)

![F10：原图 | only-prompt | rural-renew](assets/comparisons/F10.png)

![F26：原图 | only-prompt | rural-renew](assets/comparisons/F26.png)

[查看全部 11 组精选对照](assets/gallery.md)

## 方法流程

1. 加载农房六方面十八指标及适用地区的建设导则，由多模态规划模型逐项记录原图中的可见依据。
2. 制定两个方向明确的方案。P1 为现代化更新，侧重材料更新、界面整洁、功能提升与外观规整。P2 为本土性更新，侧重保留乡土风貌、延续传统构件、保留地域特色与强化文化表达。两者遵循相同的任务范围和领域 Context。
3. 图像编辑模型分别生成两张候选图，由独立评价器计算乡土性、富裕、活力、宜居和整洁五维分数。
4. 规划模型结合原图、候选图及分数变化，在同一份 Context 下分析乡土风貌损失、更新不足等取舍，制定第三个方案。
5. 生成并评价第三张候选图，再选择最终修改图。

### 领域 Context

| 农房方面 | 描述指标 |
|---|---|
| 立面维度 | 材料构成、色彩搭配、建筑形态 |
| 窗口维度 | 开口形态、窗户类型、玻璃细节 |
| 门洞维度 | 门体材质、开启方式、表面处理 |
| 屋顶维度 | 屋面材料、屋顶类型、屋面坡度 |
| 装饰维度 | 结构装饰、文化装饰、功能性装饰 |
| 环境维度 | 自然环境、人文痕迹、空间组织 |

十八项指标用于描述场景，五维感知分数用于评价场景。原图观察会区分可见依据、无法确认与不可见内容。地区建设导则提供与当地材料、建筑风貌、传统构件和周边空间相关的要求。目前内置吉林省语料，来源与扩展格式见 [Context 说明](context/README.md)。

现代化与本土性是共同外观更新范围内的设计侧重。所有方案均保留建筑体量、屋顶形制、门窗开口和生产种植空间。评价反馈可用于组合两个方向中相容的设计，不改变评价器的权重。

所有候选都从同一张原图编辑。最终选择提示词要求 Agent 选择加权评价最高的候选，并在同分时优先选择较早生成的候选；程序保留 Agent 实际给出的有效选择。原图不属于可选输出。

| 流程 | 领域 Context | 规划模型调用 | 图像生成 | 评价反馈 |
|---|---|---:|---:|---|
| `only-prompt` | 不提供农房指标及地区导则 | 1 次 | 1 次 | — |
| `rural-renew` | 十八项指标与地区导则 | 3 次 | 3 次 | 指导第三个方案和最终选择 |

案例及平均提高 2.23 分的结果比较的是两套完整流程，包含 Context 与生成次数的差异，不能单独归因于评价反馈。规划、修订与选择由同一个规划模型承担，图像编辑模型和评价器分别承担生图与评分。提示词模板使用中文。

## 快速开始

在仓库目录中执行以下命令，安装 Python 依赖和 [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)，然后[登录](https://learn.chatgpt.com/docs/auth)：

```bash
python -m pip install -r requirements.txt
npm install -g @openai/codex@0.146.1
codex login
```

在当前终端设置图像服务密钥：

```bash
export QWEN_API_KEY="your-api-key"
```

PowerShell 对应命令为 `$env:QWEN_API_KEY = "your-api-key"`。程序直接读取环境变量，不会自动加载 `.env` 文件。

运行前检查 [config.example.json](config.example.json)。示例配置保留了案例使用的规划模型 `gpt-5.6-sol`、medium 推理设置，以及图像编辑模型 `qwen-image-3.0-pro`。请根据账户可访问的模型填写模型标识和兼容的图像服务地址；自定义配置通过 `--config path/to/config.json` 指定。规划适配器已按 Codex CLI 0.146.1 检查。

在吉林省的照片上运行 rural-renew，通过示例省份信息匹配内置导则。若已知拍摄地的市、县、镇，可将实际信息补充到地区文件中：

```bash
python run.py --image path/to/jilin-scene.png --metadata examples/jilin-location.json --group rural-renew --output outputs/jilin-rural-renew
```

其他地区通过 `--guidelines path/to/guidelines.json` 提供相应导则，并使用对应的 `--metadata`。缺少导则或地区信息冲突时，程序在初始化模型服务前报错。运行时不会联网搜索导则。

运行单次通用流程：

```bash
python run.py --image assets/original/F03.png --group only-prompt --output outputs/F03-only-prompt
```

每次运行会在新目录中保存 `selected.png`、候选图、规划记录和 `result.json`。rural-renew 还会保存实际加载的 `context.json`，并在初次规划中记录结构化农房观察。每次运行请指定尚不存在的输出目录。这些命令会调用配置中的模型服务。服务出错时会停止并保留已完成文件，不自动重试。

可选参数：`--seed` 设置首次生成的随机种子；`--metadata` 接收地区信息 JSON 文件，可包含 `imageProv`、`imageCity`、`imageCounty`、`imageTown` 和 `imageYear`。

离线流程与接口测试使用模拟模型，不调用模型服务：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

骨干网络推理回归测试需另行设置 `RURAL_RENEW_MODEL_TESTS=1`。

## 仓库内容

| 目录 | 内容 |
|---|---|
| [`assets/`](assets/) | 40 张原图、11 个精选场景的生成结果、对照图和方法概览图 |
| [`prompts/`](prompts/) | 单次规划、初始双方案、反馈修订、最终选择模板及结构化输出格式 |
| [`context/`](context/) | 农房六方面十八指标、两个更新方向与有来源的地区导则 |
| [`core/`](core/) | 工作流实现与规划、图像编辑服务接口 |
| [`eval_model/`](eval_model/) | 五维评价推理、自有预测头、固定参考数据和标准化参数 |

## 评价模型

![村景五维评价模型的构建流程](assets/evaluator-construction.png)

本项目的研究背景来自中国地质大学（武汉）UrbanComp 团队与中山大学相关团队开展的村景评价研究。该项工作依托 2023 年全国乡村建设评价行动，将“村村拍”平台的众包照片与人工成对感知标注结合起来，详见 [UrbanComp 项目介绍](https://urbancomp.net/archives/intelligent-interpretation-of-chinese-village)。本项目的成对感知标注方式借鉴了 [MIT Place Pulse](https://www.media.mit.edu/projects/place-pulse-new/overview/)。

当前使用的五维标签在富裕、活力、宜居、整洁之外，还包含乡土性。评价器冻结 [ResNet50 骨干](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet50.html)，训练五个线性偏好预测头，再通过固定训练参考集和逐维标准化形成评价反馈。仓库包含自有预测头、参考数据和预处理；首次使用时，若没有缓存，torchvision 会下载固定的 ImageNet 骨干权重。构建过程和推理定义见[评价模型说明](eval_model/README.md)。
