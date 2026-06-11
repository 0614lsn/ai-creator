#!/usr/bin/env python3
"""从 UP 主音/视频文件克隆旁白音色（一次性工具）

用法:
    uv run python scripts/clone_voice.py <音频或视频文件> [--start 5] [--dur 20]

流程: demucs 分离人声 → 裁 10-20s 干净样本 → omni 转写辅助文本
     → qwen-voice-enrollment 创建音色 → 打印 voice_id（手动写入 src/config.py 的 TTS_VOICE）
"""
import argparse
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from openai import OpenAI
from src.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, TTS_MODEL, FFMPEG_BIN

ENROLL_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"


def separate_vocals(src: Path, workdir: Path) -> Path:
    """demucs htdemucs_ft 分离人声轨"""
    print("[1/4] demucs 分离人声（约 2-3 分钟）...")
    subprocess.run(
        ["uvx", "--python", "3.11", "--with", "torchcodec", "demucs",
         "-n", "htdemucs_ft", "--shifts=2", "--two-stems=vocals",
         "-o", str(workdir), str(src)],
        check=True, capture_output=True, text=True,
    )
    return workdir / "htdemucs_ft" / src.stem / "vocals.wav"


def cut_sample(vocals: Path, start: float, dur: float, out: Path) -> Path:
    subprocess.run(
        [FFMPEG_BIN, "-y", "-v", "error", "-i", str(vocals),
         "-ss", str(start), "-t", str(dur),
         "-ac", "1", "-ar", "24000", "-b:a", "96k", str(out)],
        check=True,
    )
    return out


def transcribe(sample: Path) -> str:
    print("[2/4] omni 转写样本文本（辅助提升复刻效果）...")
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    b64 = base64.b64encode(sample.read_bytes()).decode()
    resp = client.chat.completions.create(
        model="qwen3.5-omni-plus",
        messages=[{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": f"data:;base64,{b64}", "format": "mp3"}},
            {"type": "text", "text": "逐字转写这段音频，只输出转写文本。"},
        ]}],
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()


def create_voice(sample: Path, text: str) -> str:
    print("[3/4] 创建克隆音色...")
    b64 = base64.b64encode(sample.read_bytes()).decode()
    resp = requests.post(
        ENROLL_URL,
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                 "Content-Type": "application/json"},
        json={
            "model": "qwen-voice-enrollment",
            "input": {
                "action": "create",
                "target_model": TTS_MODEL,
                "preferred_name": "qiye_reader",
                "audio": {"data": f"data:audio/mpeg;base64,{b64}"},
                "text": text,
            },
        },
        timeout=120,
    )
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"创建音色失败: {resp.status_code} {data}")
    out = data["output"]
    if out.get("fallback_mode"):
        print(f"  警告: 降级模式创建（样本质量欠佳）: {out.get('fallback_reason')}")
    return out["voice"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="UP 主音频或视频文件")
    parser.add_argument("--start", type=float, default=5, help="样本起始秒")
    parser.add_argument("--dur", type=float, default=20, help="样本时长（10-20s 为宜）")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        vocals = separate_vocals(Path(args.source), workdir)
        sample = cut_sample(vocals, args.start, args.dur, workdir / "sample.mp3")
        text = transcribe(sample)
        print(f"  转写: {text[:60]}...")
        voice_id = create_voice(sample, text)

    print("[4/4] 完成")
    print(f"\nvoice_id: {voice_id}")
    print("请将其写入 src/config.py 的 TTS_VOICE。")


if __name__ == "__main__":
    main()
