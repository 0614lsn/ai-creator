# AI 读书短视频生产管线

复刻 B站 up 主"七页读书吧"的金句读书短视频（≤60s）：温暖男声旁白朗读书中金句，
配 AI 生成的电影质感动态画面，中英双语字幕 + 片头大字 + 书名角标。

## 管线

```
选书 → kimi-k2.6 写金句脚本+分镜 → qwen3.5-omni-plus 逐句旁白(定镜头时长)
     → happyhorse-1.0-t2v 并行生成动态画面 → FFmpeg 拼接+字幕+混音 → 成片
```

| 环节 | 模型/工具 |
|------|----------|
| 脚本/分镜 | kimi-k2.6（DashScope） |
| 旁白 TTS | qwen3.5-omni-plus |
| 动态画面 | happyhorse-1.0-t2v（720P ¥0.9/s，1080P ¥1.6/s） |
| 拼装 | FFmpeg（ffmpeg-full，需 libass） |

## 使用

```bash
# .env 配置 DASHSCOPE_API_KEY（需开通百炼 HappyHorse 权限）

uv run python -m src.pipeline                          # 自动从内置书单选书
uv run python -m src.pipeline --book 自渡 --author 墨多先生
uv run python -m src.pipeline --dry-run                # 只出脚本+旁白，不花视频生成费
VIDEO_RESOLUTION=1080P uv run python -m src.pipeline   # 正式出片用 1080P

uv run pytest tests/                                   # 纯逻辑单测（不调付费 API）
```

一条 30-50s 成片：720P 约 ¥30-50、全程 4-6 分钟；正式发布建议 1080P（费用约 1.8 倍）。

## 代码结构

```
src/
├── config.py     # 全局配置（模型、分辨率、节奏、路径）
├── pipeline.py   # CLI 入口 + 选书 + 流程串联
├── llm.py        # 金句脚本 + 分镜 prompt 生成
├── tts.py        # 逐句旁白合成（实测时长决定镜头长度）
├── videogen.py   # HappyHorse 异步提交/轮询/下载
└── assemble.py   # FFmpeg 拼接 + ASS 双语字幕 + 环境音混音

data/
├── scripts/      # 每次生成的脚本 JSON（含分镜与时长）
├── audio/        # 旁白 wav
├── clips/        # HappyHorse 片段
├── output/       # 最终成片
└── history.json  # 已做过的书（去重）
```

## 设计要点

- **音画对齐**：先逐句 TTS 实测时长，再决定每个镜头的生成时长（3-15s 取整 + 余量），
  拼装时裁到"旁白 + 1s 留白"，节奏完全跟随旁白。
- **风格统一**：LLM 先产出全局画面风格描述，每个分镜 prompt 强制以其开头。
- **画面纪律**：prompt 禁止文字/logo/清晰人脸（视频模型渲染文字不可靠，人脸易穿帮）。
- **声音设计**：旁白为主轨，HappyHorse 片段自带的环境音以低音量垫底，
  成片做 loudnorm 响度标准化（-16 LUFS）。
- **成本控制**：默认 720P 测试档；`--dry-run` 可零成本调试脚本与旁白。

## 历史版本

v0.1 的"爬虫 + 生图轮播"方案已废弃（见 git 历史与 `docs/superpowers/`），
v0.2 起改用视频生成模型直出动态画面。
