# assets/ — 音频素材

素材文件源自对原 UP 主视频的音源分离，**因版权原因不入 git 库**，
clone 本仓库后需按下述方式自备，管线对缺失素材均有降级策略。

## bgm/ — 背景音乐

- 规则：拼装时取本目录下**按文件名排序的第一个**音频文件（mp3/wav/m4a/flac/aac），
  自动循环、压到 `BGM_VOLUME`（默认 0.20，约比人声低 13dB）、首尾淡入淡出。
- 缺失时：成片无背景音乐（仅旁白 + 片头音效）。
- 当前线上版本使用：《红色高跟鞋》钢琴伴奏（从 UP 主视频 BV1FiL36GEd3 分离），
  重新提取方式：

```bash
# 1. 下载 UP 主视频音轨（见 data/README.md 的抓取说明）
# 2. BS-RoFormer 分离（注意必须 Python 3.11，3.14 有 beartype 兼容问题）
uvx --python 3.11 "audio-separator[cpu]" \
    -m model_bs_roformer_ep_317_sdr_12.9755.ckpt \
    --output_dir sep --output_format wav 视频音轨.wav
# 3. 取 *(Instrumental)* 轨，响度归一后放入本目录
ffmpeg -i "sep/xxx_(Instrumental)_xxx.wav" \
    -af "dynaudnorm=p=0.7,aformat=sample_rates=48000:channel_layouts=stereo" \
    assets/bgm/red_high_heels.wav
```

## sfx/ — 音效

- `intro_gears.*`：片头齿轮/放映机快闪音效。存在则直接使用（自动裁齐+淡出），
  缺失时由 FFmpeg 合成 tick 序列替代（效果略逊）。
- 当前线上版本使用：UP 主原片头的机械音效（分离后的伴奏轨头部 0.2-3.8s）：

```bash
ffmpeg -i "sep/xxx_(Instrumental)_xxx.wav" -ss 0.2 -t 3.6 \
    -af "afade=t=out:st=3.2:d=0.4" assets/sfx/intro_gears.wav
```
