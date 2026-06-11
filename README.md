# AI 读书短视频生产管线

复刻 B站 up 主"七页读书吧"的金句读书短视频（≤60s，竖屏 3:4）：
克隆 UP 主音色的旁白朗读书中金句，配 AI 生成的电影质感动态画面，
三段式片头（入场动画 + 标题卡快闪 + 齿轮声）、镜头渐隐转场、
中英双语字幕 + 书名角标、《红色高跟鞋》BGM 垫底。

## 管线

```
选书 → kimi-k2.6 金句脚本+分镜+片头卡 → 克隆音色逐句旁白(定镜头时长)
     → happyhorse-1.0-t2v 并行生成正文画面 + qwen-image 片头标题卡
     → FFmpeg: 片头动画 + xfade 渐隐 + ASS 字幕 + 三轨混音(旁白/齿轮/BGM)
     → 多模型投票评审（文案/画面/声音）
```

| 环节 | 模型/工具 |
|------|----------|
| 脚本/分镜 | kimi-k2.6（DashScope） |
| 旁白 TTS | qwen3-tts-vc（克隆 UP 主音色）+ rubberband 调速调音 |
| 正文画面 | happyhorse-1.0-t2v（竖屏 3:4，720P ¥0.9/s，1080P ¥1.6/s） |
| 片头标题卡 | qwen-image-2.0-pro |
| 评审团 | kimi-k2.6 / qwen3.7-plus / qwen3.5-omni-plus / qwen3-omni-flash 投票 |
| 拼装 | FFmpeg（ffmpeg-full，需 libass + rubberband） |

## 使用

首次使用（新环境）：

1. `.env` 写入 `DASHSCOPE_API_KEY=sk-xxx`（阿里云百炼，需开通 HappyHorse 调用权限）
2. 安装 `ffmpeg-full`（需 libass + rubberband）：`brew install ffmpeg-full`
3. 克隆旁白音色（音色绑定百炼账号，不随仓库分发）：`uv run python scripts/clone_voice.py <样本音频>`，
   把输出的 voice_id 写入 `src/config.py` 的 `TTS_VOICE`（详见 `scripts/README.md`）
4. 准备 BGM 与片头音效素材（可选，详见 `assets/README.md`）

```bash
uv run python -m src.pipeline                          # 自动从内置书单选书
uv run python -m src.pipeline --book 自渡 --author 墨多先生
uv run python -m src.pipeline --from-up 一生           # 用 UP 主原视频转写文本作素材
uv run python -m src.pipeline --dry-run                # 只出脚本+旁白，不花视频生成费
uv run python -m src.pipeline --no-review              # 跳过出片后的多模型评审

uv run python -m src.evaluate data/output/xxx.mp4 --script data/scripts/xxx.json
uv run python scripts/clone_voice.py <UP主音视频>       # 重新克隆音色
uv run pytest tests/                                   # 纯逻辑单测（不调付费 API）
```

一条 ~40s 成片：1080P 视频生成费约 ¥55-70，全程 6-10 分钟。

## 代码结构

```
src/        管线代码（详见 src/README.md：时序图、模块职责、时间轴模型）
├── config.py     # 全局配置（模型、画幅、语速、节奏、音量）
├── pipeline.py   # CLI 入口 + 选书 + 流程串联
├── llm.py        # 金句脚本 + 分镜 prompt + 片头标题卡素材
├── tts.py        # 克隆音色逐句旁白（rubberband 降速/降调/EQ）
├── videogen.py   # HappyHorse 异步提交/轮询/下载
├── intro.py      # 三段式片头（左右合拢入场 + 快闪 + 定格 + 齿轮声）
├── assemble.py   # xfade 渐隐拼接 + ASS 字幕 + 三轨混音 + loudnorm
└── evaluate.py   # 多模型投票评审（文案/画面/声音三维度）

assets/     音频素材，版权原因不入库，自备方式见 assets/README.md
├── bgm/          # BGM（按文件名序取第一个，循环垫底）
└── sfx/          # intro_gears.* 存在则用作片头音效，否则合成 tick

scripts/    离线工具（声音克隆），见 scripts/README.md
data/       运行时数据 + UP 主转写素材，见 data/README.md
tests/      纯逻辑单测（不调付费 API）
docs/       早期 superpowers 设计/计划文档（v0.1 历史方案）
```

## 对齐原 UP 主的关键参数（实测分析）

- 竖屏 3:4；语速 3.8-4.2 字/秒（`TTS_TEMPO=0.92`，可环境变量覆盖 0.90/0.94）
- 句尾约 70% 轻收 / 30% 平稳带强调（由克隆样本自然习得）
- BGM 比人声低 12-15dB（`BGM_VOLUME=0.20`）
- 片头：第 1 句旁白与片头动画同步，正文从第 2 句起
- 镜头渐隐转场 0.5s（xfade fade）

## 版本

- v0.1 爬虫+生图轮播（已废弃，见 git 历史）
- v0.2 HappyHorse 动态画面直出
- v0.3 克隆音色 + BGM 抽取 + 1080P
- v0.4 竖屏 + 片头复刻 + 渐隐转场 + 多模型评审（当前）
