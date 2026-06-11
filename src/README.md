# src/ — 管线代码

一条命令把"书名"变成 ≤60s 的竖屏读书短视频。无 agent 框架，纯顺序管线。

## 管线时序

```
pipeline.run()
│
├─ 1. 选书           pipeline.pick_book()        内置书单 + data/history.json 去重
├─ 2. 脚本/分镜      llm.generate_script()       kimi-k2.6 → 旁白×6-7 + 双语字幕
│                                                + 每镜 video_prompt + 片头标题卡素材
├─ 3. 旁白合成       tts.synthesize_shots()      克隆音色逐句合成，实测每句时长
│        └─ 由旁白时长反推：每镜净时长 / HappyHorse 生成时长 / 片头定格时长
├─ 4. 正文画面       videogen.generate_clips()   happyhorse-1.0-t2v 异步并行（shots[1:]）
├─ 5. 片头           intro.generate_intro()      qwen-image 标题卡 + 合拢动画 + 齿轮声
├─ 6. 拼装           assemble.assemble()         xfade 渐隐 + ASS 字幕 + 三轨混音
└─ 7. 评审           evaluate.evaluate_video()   多模型投票（文案/画面/声音）
```

## 模块职责

| 文件 | 职责 | 关键点 |
|------|------|--------|
| `config.py` | 全部可调参数 | 模型名、画幅 3:4、语速 `TTS_TEMPO`、`BGM_VOLUME`、转场时长等，支持环境变量覆盖 |
| `pipeline.py` | CLI 入口与流程编排 | `--from-up` 用 UP 主转写文本作素材；`--dry-run` 零成本调试 |
| `llm.py` | 脚本生成 | 校验片头句必含"今天分享的是"；全局风格 style 强制注入每镜 prompt |
| `tts.py` | 旁白 | qwen3-tts-vc（克隆音色）→ rubberband 降速/降调 + 暖色 EQ + 静音修剪 |
| `videogen.py` | 文生视频 | HappyHorse 异步提交 → 15s 间隔轮询 → 即时下载（URL 24h 失效） |
| `intro.py` | 三段式片头 | 左右合拢入场 + 快闪标题卡 + 定格；音效优先 `assets/sfx/intro_gears.*` |
| `assemble.py` | 成片拼装 | 见下方"时间轴模型"；ASS 字幕竖屏排版；loudnorm -16 LUFS |
| `evaluate.py` | 质量评审 | 每维度多评委独立打分取中位数，失效评委自动跳过 |

## 时间轴模型（assemble.py 核心设计）

采用**净时长制**，让字幕/旁白时间轴与渐隐转场解耦：

- 第 1 句旁白（片头句）与片头动画同步，片头净长 `I = max(片头动画长, 旁白0 + 留白)`
- 正文每镜净长 `V_i = 旁白时长 + SHOT_GAP_SECONDS`
- 相邻段 xfade 渐隐 `D=0.5s`：每段渲染时多给 D 秒余量（末帧 clone 补齐），
  转场吃掉的是余量而非净时长，因此第 i 镜的字幕区间恒为 `[Σ净长_{<i}, Σ净长_{<=i}]`
- 音轨三层：旁白（主）+ 片头齿轮音效（前 I 秒）+ BGM 循环（全程，音量 0.20）

## 与原 UP 主对齐的实测参数

来自对"七页读书吧"多条视频的拆解（见 `data/up_transcripts.json`）：

- 竖屏 3:4（1080×1440）
- 语速 3.8-4.2 字/秒 → `TTS_TEMPO=0.92`
- 句尾 ~70% 轻收 / ~30% 平稳带强调（由克隆样本自然习得，不做后处理干预）
- BGM 比人声低 12-15dB → `BGM_VOLUME=0.20`
- 片头 0-1s 入场动画、1-2.5s 标题卡快闪（配齿轮声）、之后定格本期书
