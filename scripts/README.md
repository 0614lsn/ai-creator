# scripts/ — 离线工具

## clone_voice.py — 重新克隆旁白音色

当需要换克隆样本（如拿到了更干净的 UP 主人声）时使用：

```bash
uv run python scripts/clone_voice.py <UP主音频或视频文件> [--start 5] [--dur 20]
```

流程：demucs 分离人声 → 裁 10-20s 样本 → omni 转写（辅助提升复刻效果）
→ `qwen-voice-enrollment` 创建音色 → 输出 `voice_id`，手动写入 `src/config.py` 的 `TTS_VOICE`。

注意：

- 脚本内置的 demucs 分离质量一般，若样本残留明显，建议先用 BS-RoFormer
  手动分离（命令见 `assets/README.md`），再把干净人声直接喂给本脚本
  （已是纯人声的输入会被再分离一次，无副作用）。
- 样本要求：10-20s、单一说话人、无明显 BGM 残留；尽量选包含
  "轻收句尾"和"平稳句尾"两种语气的段落，克隆声更自然。
- 创建音色免费，但音色与 `target_model`（`src/config.py` 的 `TTS_MODEL`）绑定，
  换合成模型需重新克隆。
